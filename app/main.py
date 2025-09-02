# app/main.py
from __future__ import annotations

import os
import re
import time
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Sequence, cast, List, Tuple, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

from app.database import get_db, SessionLocal
from app.routers.product import router as products_router           # required
from app.routers.category import router as categories_router        # required

# --- Config din ENV ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_TITLE = os.getenv("APP_TITLE", "emag-db-api")
ROOT_PATH = (os.getenv("ROOT_PATH", "").strip() or None)
DB_SCHEMA = os.getenv("DB_SCHEMA", "app")
ALEMBIC_VERSION_TABLE = os.getenv("ALEMBIC_VERSION_TABLE", "alembic_version")
ALEMBIC_INI = os.getenv("ALEMBIC_CONFIG", "/app/alembic.ini")
DISABLE_DOCS = os.getenv("DISABLE_DOCS", "").strip().lower() in {"1", "true", "yes", "on"}
BUILD_SHA = os.getenv("GIT_SHA", "") or os.getenv("BUILD_SHA", "")

# Docs/OpenAPI URL overrides (opțional)
OPENAPI_URL = None if DISABLE_DOCS else os.getenv("OPENAPI_URL", "/openapi.json")
DOCS_URL = None if DISABLE_DOCS else os.getenv("DOCS_URL", "/docs")
REDOC_URL = None if DISABLE_DOCS else os.getenv("REDOC_URL", "/redoc")
OPENAPI_ADD_ROOT_SERVER = os.getenv("OPENAPI_ADD_ROOT_SERVER", "1").strip().lower() in {"1", "true", "yes", "on"}

# Securitate
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "").strip().lower() in {"1", "true", "yes", "on"}
OBS_KEY = os.getenv("OBS_KEY", "")  # dacă e setat, protejează prefixele de mai jos
OBS_PROTECT_PREFIXES = [p.strip() for p in os.getenv("OBS_PROTECT_PREFIXES", "/observability,/observability/v2").split(",") if p.strip()]

# Limitare body (bazată pe Content-Length, non-intruzivă)
try:
    MAX_BODY_SIZE_BYTES = int(os.getenv("MAX_BODY_SIZE_BYTES", "0"))  # 0 = dezactivat
except Exception:
    MAX_BODY_SIZE_BYTES = 0

APP_STARTED_MONO = time.monotonic()
APP_STARTED_TS = int(time.time())

# --- Logging ---
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("emag-db-api")
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(_name).setLevel(LOG_LEVEL)

tags_metadata = [
    {"name": "health", "description": "Liveness/Readiness checks"},
    {"name": "products", "description": "Product CRUD & search"},
    {"name": "categories", "description": "Category CRUD & linking"},
    {"name": "observability", "description": "DB & performance insights (pg_stat_statements)"},
    {"name": "integrations", "description": "Integrări externe (eMAG etc.)"},
]

# Observability: opțional (nu blocăm aplicația dacă fișierul lipsește)
observability_router = None
try:
    from app.routers.observability import router as observability_router  # type: ignore
except Exception as e:
    observability_router = None
    logger.warning("Observability router not loaded: %s", e)

# Observability v2 extins – opțional
observability_ext_router = None
try:
    from app.routers.observability_ext import router as observability_ext_router  # type: ignore
except Exception as e:
    observability_ext_router = None
    logger.info("Observability v2 router not loaded: %s", e)

# Integrare eMAG – opțional (prefixul este stabilit în app/routers/emag/__init__.py)
emag_router = None
try:
    from app.routers.emag import router as emag_router  # type: ignore
except Exception as e:
    emag_router = None
    logger.info("eMAG router not loaded: %s", e)

# Pentru mapare 409 la duplicate (SKU/nume categorie)
try:
    from app.crud.product import DuplicateSKUError  # type: ignore
except Exception:  # pragma: no cover
    class DuplicateSKUError(Exception):
        ...

try:
    from app.crud.category import DuplicateCategoryNameError  # type: ignore
except Exception:  # pragma: no cover
    class DuplicateCategoryNameError(Exception):
        ...

# --- Utilitare ---
_ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _safe_ident(name: str, fallback: str) -> str:
    if _ident_re.fullmatch(name or ""):
        return name
    logger.warning("Invalid SQL identifier from env: %r. Using fallback: %r", name, fallback)
    return fallback

DB_SCHEMA = _safe_ident(DB_SCHEMA, "app")
ALEMBIC_VERSION_TABLE = _safe_ident(ALEMBIC_VERSION_TABLE, "alembic_version")

def _get_req_id_from_headers(request: Request) -> str:
    # Prefer X-Request-ID, apoi X-Correlation-ID; dacă lipsesc, generează unul.
    return (
        request.headers.get("x-request-id")
        or request.headers.get("x-correlation-id")
        or uuid.uuid4().hex[:12]
    )

# --- Middleware func (registered after app is created) ---
async def request_context_mw(request: Request, call_next):
    """
    - Generează/propagă X-Request-ID
    - Aplică headers de securitate + HSTS (opțional)
    - Limitează mărimea corpului când Content-Length e disponibil
    - Server-Timing / X-Process-Time
    - (opțional) Protejează prefixe cu X-Obs-Key (ține cont de ROOT_PATH)
    """
    req_id = _get_req_id_from_headers(request)

    # Body-size guard (non-intruziv, pe Content-Length)
    if MAX_BODY_SIZE_BYTES > 0:
        cl = request.headers.get("content-length")
        try:
            if cl is not None and int(cl) > MAX_BODY_SIZE_BYTES:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "Payload too large", "max_bytes": MAX_BODY_SIZE_BYTES},
                    headers={"X-Request-ID": req_id},
                )
        except Exception:
            pass

    # Protecție X-Obs-Key (dacă OBS_KEY e setat). Ține cont de ROOT_PATH.
    if OBS_KEY:
        path = request.url.path
        root_prefix = ROOT_PATH or ""
        def _is_protected(p: str) -> bool:
            return path.startswith(p) or (root_prefix and path.startswith(f"{root_prefix.rstrip('/')}{p}"))
        if any(_is_protected(p) for p in OBS_PROTECT_PREFIXES):
            if request.headers.get("x-obs-key") != OBS_KEY:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Missing or invalid X-Obs-Key"},
                    headers={"X-Request-ID": req_id},
                )

    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    # Security + perf headers
    response.headers.setdefault("X-Request-ID", req_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    # CSP minim care nu rupe API (și nici /docs când sunt activate)
    response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
    response.headers.setdefault("X-App-Version", APP_VERSION)
    if ENABLE_HSTS:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")

    response.headers.setdefault("Server-Timing", f"app;dur={duration_ms:.1f}")
    response.headers.setdefault("X-Process-Time", f"{duration_ms:.1f}ms")
    return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: sanity check DB și configurație de migrații / search_path
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            sp = db.execute(text("SHOW search_path")).scalar_one()
            in_public = db.execute(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            ).scalar_one()
            if in_public:
                logger.error("alembic_version prezent în schema PUBLIC! Verifică env.py și ALEMBIC_VERSION_TABLE_SCHEMA.")
            else:
                logger.info("alembic_version NU este în public (ok).")
            try:
                shared_libs = db.execute(text("SHOW shared_preload_libraries")).scalar_one()
                taqs = db.execute(text("SHOW track_activity_query_size")).scalar_one()
                logger.info(
                    "DB startup check OK (search_path=%s, schema=%s, version_table=%s, shared_preload_libraries=%s, track_activity_query_size=%s)",
                    sp, DB_SCHEMA, ALEMBIC_VERSION_TABLE, shared_libs, taqs
                )
            except Exception:
                logger.info("DB startup check OK (search_path=%s, schema=%s, version_table=%s)", sp, DB_SCHEMA, ALEMBIC_VERSION_TABLE)
            try:
                cfg = AlembicConfig(ALEMBIC_INI)
                script = ScriptDirectory.from_config(cfg)
                heads = list(script.get_heads())
                logger.info("Alembic heads: %s", heads or [])
            except Exception as e:
                logger.warning("Nu pot obține Alembic heads (%s): %s", ALEMBIC_INI, e)
    except Exception:
        logger.exception("DB startup check FAILED")

    if observability_router is None and observability_ext_router is None:
        logger.warning("Observability routers absente. Creează app/routers/observability*.py pentru /observability endpoints.")

    # Ready to serve
    yield

    # Shutdown: închide clienții eMAG cache-uiți (dacă există)
    try:
        from app.routers.emag.deps import close_emag_clients  # import lazy
        await close_emag_clients()
    except Exception as e:  # pragma: no cover
        logger.warning("While closing Emag clients on shutdown: %s", e)

# --- App factory (create app BEFORE registering middleware) ---
app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    root_path=ROOT_PATH,
    docs_url=DOCS_URL,
    redoc_url=REDOC_URL,
    openapi_url=OPENAPI_URL,
)

# Register middleware now that app exists
app.middleware("http")(request_context_mw)
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Trusted hosts (opțional): TRUSTED_HOSTS="localhost,127.0.0.1,.example.com"
_trusted = [h.strip() for h in os.getenv("TRUSTED_HOSTS", "").split(",") if h.strip()]
if _trusted:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=cast(Sequence[str], _trusted))  # type: ignore[arg-type]

# CORS din env: CORS_ORIGINS="http://localhost:3000,https://example.com"
_cors = os.getenv("CORS_ORIGINS")
if _cors:
    origins = [o.strip() for o in _cors.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Total-Count",
            "X-Request-ID",
            "Server-Timing",
            "X-Process-Time",
            "Content-Disposition",  # pt. download CSV/NDJSON
            "X-App-Version",
        ],
    )

# --- OpenAPI customization & caching ---
def _custom_openapi():
    """
    Generează schema OpenAPI on-demand și o cache-uiește.
    Opțional adaugă ROOT_PATH ca server → ajută tooling-ul din spatele unui reverse proxy.
    """
    if getattr(app, "openapi_schema", None):
        return app.openapi_schema
    schema = get_openapi(
        title=APP_TITLE,
        version=APP_VERSION,
        routes=app.routes,
        description=None,
    )
    if OPENAPI_ADD_ROOT_SERVER:
        rp = ROOT_PATH or ""
        if rp and rp != "/":
            schema["servers"] = [{"url": rp}]
    # Include build SHA în info.x-build-sha (dacă există)
    if BUILD_SHA:
        schema.setdefault("info", {})["x-build-sha"] = BUILD_SHA
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = _custom_openapi  # type: ignore[assignment]

# Alias stabil pentru /api/openapi.json (folosit în tool-urile tale)
if not DISABLE_DOCS and OPENAPI_URL != "/api/openapi.json":
    @app.get("/api/openapi.json", include_in_schema=False)
    def _openapi_alias():
        return JSONResponse(app.openapi())

# --- Exception handlers (ops-friendly) ---
@app.exception_handler(DuplicateSKUError)
async def _dup_sku_handler(request: Request, exc: DuplicateSKUError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
        headers={"X-Request-ID": _get_req_id_from_headers(request)},
    )

@app.exception_handler(DuplicateCategoryNameError)
async def _dup_category_handler(request: Request, exc: DuplicateCategoryNameError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
        headers={"X-Request-ID": _get_req_id_from_headers(request)},
    )

try:
    from sqlalchemy.exc import IntegrityError  # type: ignore
except Exception:  # pragma: no cover
    IntegrityError = Exception  # type: ignore[misc]

@app.exception_handler(IntegrityError)
async def _integrity_handler(request: Request, exc: IntegrityError):
    orig = getattr(exc, "orig", None)
    pgcode = getattr(orig, "pgcode", None)
    mapping = {
        "23505": (status.HTTP_409_CONFLICT, "Unique constraint violated."),
        "23503": (status.HTTP_409_CONFLICT, "Foreign key violation."),
        "23514": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Check constraint violated."),
        "23502": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Not-null constraint violated."),
        "22P02": (status.HTTP_400_BAD_REQUEST, "Invalid text representation."),
    }
    if pgcode in mapping:
        code, msg = mapping[pgcode]
        return JSONResponse(
            status_code=code,
            content={"detail": msg, "pgcode": pgcode},
            headers={"X-Request-ID": _get_req_id_from_headers(request)},
        )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Integrity error."},
        headers={"X-Request-ID": _get_req_id_from_headers(request)},
    )

@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
        headers={"X-Request-ID": _get_req_id_from_headers(request)},
    )

# Prinde 404/405 Starlette și răspunde JSON unitar
@app.exception_handler(StarletteHTTPException)
async def _starlette_http_exc_handler(request: Request, exc: StarletteHTTPException):
    headers = dict(exc.headers or {})
    headers.setdefault("X-Request-ID", _get_req_id_from_headers(request))
    detail = exc.detail
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        detail = {"message": "Not Found", "path": str(request.url.path)}
    elif exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        detail = {"message": "Method Not Allowed", "path": str(request.url.path)}
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=headers)

@app.exception_handler(HTTPException)
async def _http_exc_handler(request: Request, exc: HTTPException):
    headers = dict(exc.headers or {})
    headers.setdefault("X-Request-ID", _get_req_id_from_headers(request))
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)

@app.exception_handler(Exception)
async def _unhandled_exc_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
        headers={"X-Request-ID": _get_req_id_from_headers(request)},
    )

# --- Helpers Alembic/health ---
def _get_db_alembic_version(db: Session) -> Tuple[Optional[str], bool]:
    try:
        version = db.execute(
            text(f'SELECT version_num FROM "{DB_SCHEMA}"."{ALEMBIC_VERSION_TABLE}"')
        ).scalar_one_or_none()
        return version, True
    except Exception:
        return None, False

def _get_pkg_alembic_heads() -> List[str]:
    cfg = AlembicConfig(ALEMBIC_INI)
    script = ScriptDirectory.from_config(cfg)
    return list(script.get_heads())

# --- Routes: health ---
@app.get("/", tags=["health"])
def root():
    payload = {"name": APP_TITLE, "version": APP_VERSION}
    if BUILD_SHA:
        payload["build_sha"] = BUILD_SHA
    return payload

@app.get("/__version__", tags=["health"])
def version_meta():
    payload = {"app_version": APP_VERSION, "started_at": APP_STARTED_TS}
    if BUILD_SHA:
        payload["build_sha"] = BUILD_SHA
    return payload

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

@app.get("/health/uptime", tags=["health"])
def health_uptime():
    return {"uptime_seconds": round(time.monotonic() - APP_STARTED_MONO, 3), "started_at": APP_STARTED_TS}

@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)):
    try:
        search_path = db.execute(text("SHOW search_path")).scalar_one()
        version = db.execute(text("SHOW server_version")).scalar_one()
        current_db = db.execute(text("SELECT current_database()")).scalar_one()
        current_user = db.execute(text("SELECT current_user")).scalar_one()
        application_name = db.execute(text("SHOW application_name")).scalar_one()
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "db": "up",
            "search_path": search_path,
            "server_version": version,
            "database": current_db,
            "user": current_user,
            "application_name": application_name,
        }
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DB not ready")

@app.get("/health/migrations", tags=["health"])
def health_migrations(db: Session = Depends(get_db)):
    version, present = _get_db_alembic_version(db)
    return {"alembic_version": version, "present": present}

@app.get("/health/migrations/status", tags=["health"])
def health_migrations_status(db: Session = Depends(get_db)):
    db_version, present = _get_db_alembic_version(db)
    try:
        heads = _get_pkg_alembic_heads()
    except Exception as e:  # pragma: no cover
        return {"db_version": db_version, "present": present, "pkg_heads_error": str(e), "in_sync": False if present else None}
    head = heads[0] if heads else None
    return {"db_version": db_version, "present": present, "pkg_heads": heads, "pkg_head": head, "in_sync": bool(db_version and head and db_version == head)}

@app.get("/health/ready", tags=["health"])
def health_ready(db: Session = Depends(get_db)):
    """
    Consideră aplicația ready dacă:
      - DB răspunde
      - tabelul alembic_version există în schema configurată
    """
    try:
        db.execute(text("SELECT 1"))
        present = db.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema=:s AND table_name=:t)"
            ),
            {"s": DB_SCHEMA, "t": ALEMBIC_VERSION_TABLE},
        ).scalar_one()
        if not present:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Not ready (migrations table missing)")
        return {"ready": True}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Not ready")

@app.get("/health/pg", tags=["health"])
def health_pg(db: Session = Depends(get_db)):
    tz = db.execute(text("SHOW TimeZone")).scalar_one()
    sv = db.execute(text("SHOW server_version")).scalar_one()
    sp = db.execute(text("SHOW search_path")).scalar_one()
    return {"server_version": sv, "timezone": tz, "search_path": sp}

@app.get("/health/extensions", tags=["health"])
def health_extensions(db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT e.extname, n.nspname AS schema
              FROM pg_extension e
              JOIN pg_namespace n ON n.oid = e.extnamespace
             WHERE e.extname IN ('pg_stat_statements','pg_trgm')
             ORDER BY e.extname;
        """)
    ).mappings().all()
    return {"extensions": [dict(r) for r in rows]}

@app.get("/health/settings", tags=["health"])
def health_settings(db: Session = Depends(get_db)):
    """Expune rapid setările cheie pentru observability."""
    settings = {}
    for key in (
        "shared_preload_libraries",
        "pg_stat_statements.max",
        "pg_stat_statements.save",
        "pg_stat_statements.track",
        "pg_stat_statements.track_utility",
        "track_activity_query_size",
    ):
        try:
            val = db.execute(text(f"SHOW {key}")).scalar_one()
            settings[key] = val
        except Exception:
            settings[key] = None
    return {"settings": settings}

@app.get("/health/schema", tags=["health"])
def health_schema(db: Session = Depends(get_db)):
    public_has = db.execute(text("SELECT to_regclass('public.alembic_version') IS NOT NULL")).scalar_one()
    sp = db.execute(text("SHOW search_path")).scalar_one()
    ok_sp = sp.replace(" ", "").lower().startswith(f"{DB_SCHEMA},")
    return {"public_alembic_version_present": bool(public_has), "search_path": sp, "search_path_ok": ok_sp}

@app.get("/health/version", tags=["health"])
def health_version(db: Session = Depends(get_db)):
    v, present = _get_db_alembic_version(db)
    payload = {"app_version": APP_VERSION, "db_alembic_version": v, "version_table_present": present}
    if BUILD_SHA:
        payload["build_sha"] = BUILD_SHA
    return payload

# --- Routers ---
app.include_router(products_router)
app.include_router(categories_router)
if observability_router is not None:
    app.include_router(observability_router)
if observability_ext_router is not None:
    app.include_router(observability_ext_router)
if emag_router is not None:
    # IMPORTANT: emag_router are deja prefix intern "/integrations/emag" (în app/routers/emag/__init__.py).
    # Nu adăuga prefix aici ca să eviți dublarea!
    app.include_router(emag_router)

# asigură-te că schema OpenAPI se regenerează dacă a fost accesată prematur
app.openapi_schema = None  # invalidare cache, util dacă /openapi.json a fost cerut înainte de include_router

# dev-reload marker
# Tue Sep 2 09:00:00 EEST 2025
