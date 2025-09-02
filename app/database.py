# app/database.py
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, List

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

# Încarcă variabilele din .env (pe host). În Docker vin din env_file/environment.
load_dotenv()

# -----------------------------
# Helpers
# -----------------------------
def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}

def _mask_url(url: str) -> str:
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest or ":" not in rest.split("@", 1)[0]:
        return url
    creds, tail = rest.split("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{tail}"

_IDENT_RE = r"[A-Za-z_][A-Za-z0-9_]*"

def _sanitize_search_path(raw: str, fallback: str) -> str:
    """
    Acceptă doar identificatori ne-citați separați prin virgulă.
    Ex. 'app,public'. Dacă nu trece validarea, întoarce fallback.
    """
    if not raw:
        return fallback
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return fallback
    for p in parts:
        # nu permitem ghilimele duble sau caractere exotice
        # (dacă ai nevoie de identifer quoted, mai bine setezi prin config DSN)
        import re
        if not re.fullmatch(_IDENT_RE, p):
            return fallback
    # elimină duplicate păstrând ordinea
    seen = set()
    uniq: List[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return ",".join(uniq)

# -----------------------------
# Config din environment
# -----------------------------
DATABASE_URL = (os.getenv("DATABASE_URL", "sqlite:///./app.db") or "").strip()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL este gol. Setează o valoare validă.")

DEFAULT_SCHEMA = (os.getenv("DB_SCHEMA", "app") or "app").strip()

# Logs SQL la nevoie: DB_ECHO=1 / true / yes / on
ECHO_SQL = _env_bool("DB_ECHO", False)

# Postgres: setări opționale
_raw_search_path = (os.getenv("DB_SEARCH_PATH", f"{DEFAULT_SCHEMA},public") or "").strip()
PG_SEARCH_PATH = _sanitize_search_path(_raw_search_path, f"{DEFAULT_SCHEMA},public")

PG_STATEMENT_TIMEOUT_MS = (os.getenv("DB_STATEMENT_TIMEOUT_MS") or "").strip()  # ex: "30000"
PG_APP_NAME = (os.getenv("DB_APPLICATION_NAME") or "").strip()

# Pooling
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # sec (30 min)
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))    # sec
POOL_USE_LIFO = _env_bool("DB_POOL_LIFO", True)

# Dacă rulezi prin pgbouncer (transaction pooling), de obicei vrei NullPool:
USE_NULLPOOL = _env_bool("DB_USE_NULLPOOL", False)

# Dezactivează pre_ping dacă e nevoie (ex. anumite setup-uri pgbouncer)
DISABLE_PRE_PING = _env_bool("DB_DISABLE_PRE_PING", False)

# Creează schema la pornire, dacă lipsește (util în dev/CI)
CREATE_SCHEMA_IF_MISSING = _env_bool("DB_CREATE_SCHEMA_IF_MISSING", False)

# -----------------------------
# Naming convention pentru Alembic/op.f()
# -----------------------------
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(schema=DEFAULT_SCHEMA, naming_convention=NAMING_CONVENTION)
Base = declarative_base(metadata=metadata)  # schema implicită pentru toate modelele

# -----------------------------
# Engine factory
# -----------------------------
def _build_engine_kwargs() -> dict:
    kwargs: dict = {
        "echo": ECHO_SQL,
        "pool_pre_ping": not DISABLE_PRE_PING,
        "pool_use_lifo": POOL_USE_LIFO,
    }

    if DATABASE_URL.startswith("sqlite"):
        # SQLite: single-thread în driver → dezactivează check_same_thread
        kwargs["connect_args"] = {"check_same_thread": False}
        # In-memory → StaticPool (altfel fiecare conexiune are DB separat)
        if DATABASE_URL in {"sqlite://", "sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}:
            kwargs["poolclass"] = StaticPool
        else:
            # Pentru fișiere, NullPool e ok (pooling are beneficii reduse la SQLite)
            kwargs["poolclass"] = NullPool
    else:
        # Postgres / MySQL
        if USE_NULLPOOL:
            kwargs["poolclass"] = NullPool
        else:
            kwargs.update(
                {
                    "pool_size": POOL_SIZE,
                    "max_overflow": MAX_OVERFLOW,
                    "pool_recycle": POOL_RECYCLE,
                    "pool_timeout": POOL_TIMEOUT,
                }
            )

        # ---- Postgres: libpq options (NU ca statements) ----
        pg_options = []
        if PG_SEARCH_PATH:
            pg_options.append(f"-c search_path={PG_SEARCH_PATH}")
        if PG_STATEMENT_TIMEOUT_MS.isdigit():
            pg_options.append(f"-c statement_timeout={PG_STATEMENT_TIMEOUT_MS}")

        if pg_options or PG_APP_NAME:
            kwargs.setdefault("connect_args", {})

        # Parametrii -c merg prin 'options' (nu apar în pg_stat_statements)
        if pg_options:
            existing_options = kwargs["connect_args"].get("options")
            opts = " ".join(pg_options)
            kwargs["connect_args"]["options"] = (
                f"{existing_options} {opts}".strip() if existing_options else opts
            )

        # application_name → parametru de conexiune (nu ca SET)
        if PG_APP_NAME:
            # atât psycopg2 cât și psycopg3 acceptă application_name în conninfo
            kwargs["connect_args"]["application_name"] = PG_APP_NAME

    return kwargs

engine: Engine = create_engine(DATABASE_URL, **_build_engine_kwargs())

# -----------------------------
# Session factory
# -----------------------------
# expire_on_commit=False → obiectele rămân utilizabile după commit (evită re-load imediat)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency pentru o sesiune SQLAlchemy închisă garantat.
    Face rollback automat dacă apare o excepție în request handler.
    """
    db: Session = SessionLocal()
    try:
        yield db
        # commit-ul e responsabilitatea endpoint-ului/serviciului;
        # dacă vrei auto-commit la finalul fiecărui request, îl poți face aici.
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Context manager util în scripturi/servicii (non-FastAPI).
    Exemplu:
        with session_scope() as db:
            db.add(obj)
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def _ensure_schema() -> None:
    """
    Creează schema DEFAULT_SCHEMA dacă lipsește (doar dacă DB_CREATE_SCHEMA_IF_MISSING=1).
    Alembic o poate crea și el; activarea acestui hook e utilă în dev/CI.
    """
    if CREATE_SCHEMA_IF_MISSING and DEFAULT_SCHEMA:
        with engine.begin() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{DEFAULT_SCHEMA}"')

def init_db_if_requested() -> None:
    """
    Opțional: creează tabelele din modele când SQLALCHEMY_CREATE_ALL=1.
    Util în prototip/demo; în producție folosește Alembic.
    """
    _ensure_schema()
    if _env_bool("SQLALCHEMY_CREATE_ALL", False):
        from app import models  # noqa: F401
        Base.metadata.create_all(bind=engine)

__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "get_db",
    "session_scope",
    "init_db_if_requested",
]
