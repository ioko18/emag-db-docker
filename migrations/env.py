# migrations/env.py
from __future__ import annotations

import importlib
import logging
import os
import re
from logging.config import fileConfig
from typing import Any, Dict, Optional, Sequence, Set, Tuple, List

import sqlalchemy as sa
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import URL, make_url

# ------------------------------------------------------------
# Alembic config & logging
# ------------------------------------------------------------
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
log = logging.getLogger("alembic.env")

# ------------------------------------------------------------
# .env (opțional)
# ------------------------------------------------------------
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    load_dotenv(find_dotenv(filename=".env", usecwd=True), override=False)
except Exception:
    pass

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "t", "yes", "y", "on"}

def _csv_env(name: str) -> Sequence[str]:
    raw = os.getenv(name, "") or ""
    return tuple(s.strip() for s in raw.split(",") if s.strip())

def _csv_env_extensions(name: str) -> Sequence[str]:
    raw = os.getenv(name, "") or ""
    if not raw:
        return ()
    out: list[str] = []
    for token in raw.split(","):
        t = token.strip()
        if not t:
            continue
        if "#" in t:
            t = t.split("#", 1)[0].strip()
        if not t:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_]+", t):
            log.warning("Ignoring invalid PostgreSQL extension name %r from %s", t, name)
            continue
        if t not in out:
            out.append(t)
    return tuple(out)

def _mask_url(url: str) -> str:
    try:
        u = make_url(url)
        if u.password:
            u = u.set(password="***")
        return str(u)
    except Exception:
        return url

def _quote_ident(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'

def _build_url_from_parts() -> Optional[str]:
    driver = (os.getenv("DB_DRIVER") or "").strip()
    host = (os.getenv("DB_HOST") or "").strip()
    port = os.getenv("DB_PORT")
    user = (os.getenv("DB_USER") or "").strip()
    password = (os.getenv("DB_PASSWORD") or "").strip()
    dbname = (os.getenv("DB_NAME") or "").strip()
    if not (driver and host and dbname):
        return None
    try:
        url = URL.create(
            drivername=driver,
            username=user or None,
            password=password or None,
            host=host,
            port=int(port) if port else None,
            database=dbname,
        )
        return str(url)
    except Exception:
        return None

def _get_database_url() -> str:
    env_url = (os.getenv("DATABASE_URL") or "").strip()
    if env_url and "driver://user:pass@localhost/dbname" not in env_url:
        return env_url
    ini_url = (config.get_main_option("sqlalchemy.url") or "").strip()
    if ini_url and "driver://user:pass@localhost/dbname" not in ini_url:
        return ini_url
    built = _build_url_from_parts()
    if built:
        return built
    raise RuntimeError(
        "Nu am găsit URL-ul DB. Setează DATABASE_URL sau sqlalchemy.url în alembic.ini "
        "sau folosește DB_DRIVER/DB_HOST/DB_NAME (+ opțional DB_USER/DB_PASSWORD/DB_PORT)."
    )

# ------------------------------------------------------------
# Config general
# ------------------------------------------------------------
DEFAULT_SCHEMA = (os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app").strip()
VERSION_TABLE = (os.getenv("ALEMBIC_VERSION_TABLE") or "alembic_version").strip()
VERSION_TABLE_SCHEMA = (os.getenv("ALEMBIC_VERSION_TABLE_SCHEMA") or DEFAULT_SCHEMA).strip()

AUTO_CREATE_SCHEMA = _env_bool("AUTO_CREATE_SCHEMA", True)
USE_SCHEMA_TRANSLATE = _env_bool("ALEMBIC_USE_SCHEMA_TRANSLATE", True)
MAP_PUBLIC_TO_DEFAULT = _env_bool("ALEMBIC_MAP_PUBLIC_TO_DEFAULT_SCHEMA", False)
ONLY_DEFAULT_SCHEMA = _env_bool("ALEMBIC_ONLY_DEFAULT_SCHEMA", False)
FORCE_BATCH_SQLITE = _env_bool("ALEMBIC_RENDER_AS_BATCH", False)
TX_PER_MIGRATION = _env_bool("ALEMBIC_TRANSACTION_PER_MIGRATION", False)
SKIP_EMPTY_MIGRATIONS = _env_bool("ALEMBIC_SKIP_EMPTY", True)

# ✔ verificări/diag suplimentare
ASSERT_TABLES: Sequence[str] = _csv_env("ALEMBIC_ASSERT_TABLES")
FAIL_IF_PUBLIC_VERSION_TABLE = _env_bool("ALEMBIC_FAIL_IF_PUBLIC_VERSION_TABLE", False)
VERIFY_WITH_NEW_CONN = _env_bool("ALEMBIC_VERIFY_WITH_NEW_CONNECTION", True)
SQL_ECHO = _env_bool("ALEMBIC_SQL_ECHO", False)

EXCLUDE_TABLES: Set[str] = set(_csv_env("ALEMBIC_EXCLUDE_TABLES"))
EXCLUDE_SCHEMAS: Set[str] = set(_csv_env("ALEMBIC_EXCLUDE_SCHEMAS"))

PG_EXTENSIONS: Sequence[str] = _csv_env_extensions("DB_EXTENSIONS")
PG_EXTENSIONS_STRICT = _env_bool("DB_EXTENSIONS_STRICT", False)

# Import modele pentru autogenerate
# poți trece pachete suplimentare prin ALEMBIC_MODEL_PACKAGES=app.models,app.models.emag
MODEL_PACKAGES: Sequence[str] = _csv_env("ALEMBIC_MODEL_PACKAGES") or ("app.models", "app.models.emag")

# ------------------------------------------------------------
# Import metadata + modele (rezilient, agregăm mai multe MetaData)
# ------------------------------------------------------------
metadatas: List[sa.MetaData] = []

def _try_collect_metadata(import_path: str) -> None:
    try:
        mod = importlib.import_module(import_path)
        # Convenții uzuale:
        candidates = [
            getattr(mod, "Base", None),
            getattr(mod, "metadata", None),
        ]
        added = False
        for cand in candidates:
            md = getattr(cand, "metadata", None) if cand is not None else None
            if isinstance(md, sa.MetaData) and md not in metadatas:
                metadatas.append(md)
                added = True
        if added:
            log.info("Loaded metadata from %s", import_path)
        else:
            log.info("Imported %s (no direct metadata found; relying on side effects)", import_path)
    except Exception as exc:
        log.warning("Could not import %r: %s", import_path, exc)

# încearcă întâi câteva căi comune
for path in ("app.database", "app.models", "app.models.emag"):
    _try_collect_metadata(path)

# apoi pachetele declarate în env
for pkg in MODEL_PACKAGES:
    _try_collect_metadata(pkg)

# Fallback dacă nu am găsit nimic
if not metadatas:
    log.warning("No metadata collected; using empty MetaData().")
    metadatas = [sa.MetaData()]

# Alembic acceptă o listă de MetaData în target_metadata
target_metadata: Sequence[sa.MetaData] = metadatas

# ------------------------------------------------------------
# Tx helpers
# ------------------------------------------------------------
def _end_open_tx(conn: sa.engine.Connection, tag: str) -> None:
    """Închide curat o tranzacție implicită dacă există (commit sau rollback)."""
    try:
        in_tx = conn.in_transaction()
    except Exception:
        in_tx = False
    if in_tx:
        try:
            conn.commit()
            log.info("[tx:%s] committed", tag)
        except Exception as exc:
            log.warning("[tx:%s] commit failed: %s; rolling back", tag, exc)
            conn.rollback()

# ------------------------------------------------------------
# Bootstrap PG: schema + extensii
# ------------------------------------------------------------
def _ensure_schema_and_extensions(connection: sa.engine.Connection, schema: str) -> None:
    """Creează schema/extension-urile în aceeași conexiune gestionată de Alembic."""
    if connection.dialect.name != "postgresql" or not schema:
        return
    if AUTO_CREATE_SCHEMA:
        connection.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(schema)}")
    for ext in PG_EXTENSIONS:
        try:
            connection.exec_driver_sql(f"CREATE EXTENSION IF NOT EXISTS {_quote_ident(ext)}")
        except Exception as exc:
            if PG_EXTENSIONS_STRICT:
                raise
            log.warning(
                "Skipping unavailable PostgreSQL extension %r (error: %s). "
                "Set DB_EXTENSIONS_STRICT=1 to fail hard.",
                ext, exc,
            )

def _set_session_search_path(connection: sa.engine.Connection, schema: str) -> None:
    if connection.dialect.name != "postgresql" or not schema:
        return
    connection.exec_driver_sql(f"SET search_path = {_quote_ident(schema)}, public")
    sp = connection.exec_driver_sql("SHOW search_path").scalar()
    log.info("Using SESSION search_path for migrations: %s", sp)

def _diag_connection(connection: sa.engine.Connection, tag: str) -> None:
    try:
        row = connection.exec_driver_sql(
            "select current_database(), current_user, "
            "inet_server_addr()::text, inet_server_port(), "
            "version();"
        ).first()
        sp = connection.exec_driver_sql("show search_path").scalar()
        log.info(
            "[diag:%s] db=%s user=%s addr=%s port=%s sp=%s",
            tag, row[0], row[1], row[2], row[3], sp
        )
    except Exception as exc:
        log.warning("[diag:%s] failed: %s", tag, exc)

def _log_version_tables(connection: sa.engine.Connection, when: str) -> Tuple[bool, bool]:
    if connection.dialect.name != "postgresql":
        return (False, False)
    res = connection.exec_driver_sql(
        """
        SELECT
          to_regclass(%(app)s) AS app_ver,
          to_regclass(%(pub)s) AS public_ver
        """,
        {"app": f'{_quote_ident(VERSION_TABLE_SCHEMA)}.{_quote_ident(VERSION_TABLE)}',
         "pub": f'public.{_quote_ident(VERSION_TABLE)}'},
    ).first()
    app_ver = bool(res[0]) if res else False
    public_ver = bool(res[1]) if res else False
    log.info("[%s] alembic_version in %s=%s, public=%s", when, VERSION_TABLE_SCHEMA, app_ver, public_ver)
    if FAIL_IF_PUBLIC_VERSION_TABLE and public_ver and not app_ver:
        raise RuntimeError(
            f"Found {VERSION_TABLE!r} in public but not in {VERSION_TABLE_SCHEMA!r}. "
            "Probabil migrațiile au rulat cu search_path greșit."
        )
    return (app_ver, public_ver)

# ------------------------------------------------------------
# Verificări post-migrare
# ------------------------------------------------------------
_VALID_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _split_table_name(name: str) -> Tuple[str, str]:
    if "." in name:
        s, t = name.split(".", 1)
        s, t = s.strip() or VERSION_TABLE_SCHEMA, t.strip()
    else:
        s, t = VERSION_TABLE_SCHEMA, name.strip()
    if not (_VALID_IDENT.fullmatch(s) and _VALID_IDENT.fullmatch(t)):
        raise ValueError(f"Nume invalid de tabel pentru verificare: {name!r}")
    return s, t

def _assert_tables_exist_url(url: str, schema: str, tables: Sequence[str]) -> None:
    """Verifică existența tabelelor pe o conexiune NOUĂ (după commit)."""
    if not tables:
        return
    eng = sa.create_engine(url, poolclass=pool.NullPool)
    try:
        with eng.connect() as conn:
            _set_session_search_path(conn, schema)
            missing: list[str] = []
            for raw in tables:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    s, t = _split_table_name(raw)
                except ValueError as exc:
                    log.warning("%s", exc)
                    continue
                qn = f"{_quote_ident(s)}.{_quote_ident(t)}"
                ok = bool(conn.exec_driver_sql(
                    "SELECT to_regclass(%(qn)s) IS NOT NULL", {"qn": qn}
                ).scalar())
                if not ok:
                    missing.append(f"{s}.{t}")
            if missing:
                raise RuntimeError("După migrare lipsesc tabelele așteptate: " + ", ".join(missing))
    finally:
        eng.dispose()

# ------------------------------------------------------------
# Filtrări autogenerate
# ------------------------------------------------------------
def include_name(name: str, type_: str, parent_names: Dict[str, Optional[str]]) -> bool:
    if type_ == "schema":
        if not ONLY_DEFAULT_SCHEMA:
            return name not in EXCLUDE_SCHEMAS
        allowed = {VERSION_TABLE_SCHEMA, "public"} if VERSION_TABLE_SCHEMA != "public" else {"public"}
        return (name in allowed) and (name not in EXCLUDE_SCHEMAS)

    schema = parent_names.get("schema_name") or parent_names.get("schema")
    if schema and schema in EXCLUDE_SCHEMAS:
        return False
    if ONLY_DEFAULT_SCHEMA and schema and schema not in {VERSION_TABLE_SCHEMA, "public"}:
        return False
    return True

def include_object(object_: Any, name: str, type_: str, reflected: bool, compare_to: Any) -> bool:
    if type_ == "table":
        if name == VERSION_TABLE or name in EXCLUDE_TABLES:
            return False
        obj_schema = getattr(object_, "schema", None)
        if ONLY_DEFAULT_SCHEMA and obj_schema and obj_schema not in {VERSION_TABLE_SCHEMA, "public"}:
            return False
    return True

def process_revision_directives(context_, revision, directives):
    if not SKIP_EMPTY_MIGRATIONS:
        return
    autogen = bool(getattr(getattr(config, "cmd_opts", object()), "autogenerate", False))
    if autogen and directives:
        script = directives[0]
        if getattr(script, "upgrade_ops", None) and script.upgrade_ops.is_empty():
            directives[:] = []
            log.info("No schema changes detected; skipping empty migration.")

# ------------------------------------------------------------
# Offline migrations
# ------------------------------------------------------------
def run_migrations_offline() -> None:
    url = _get_database_url()
    log.info(
        "[alembic] offline url=%s | schema=%s | version_table=%s (%s) | extensions=%s",
        _mask_url(url), DEFAULT_SCHEMA, VERSION_TABLE, VERSION_TABLE_SCHEMA, ", ".join(PG_EXTENSIONS) or "-",
    )

    configure_kwargs: Dict[str, Any] = dict(
        url=url,
        target_metadata=target_metadata,
        include_name=include_name,
        include_object=include_object,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        version_table=VERSION_TABLE,
        version_table_schema=VERSION_TABLE_SCHEMA,
        process_revision_directives=process_revision_directives,
        transaction_per_migration=TX_PER_MIGRATION,
    )

    if USE_SCHEMA_TRANSLATE and DEFAULT_SCHEMA:
        schema_map: Dict[Optional[str], Optional[str]] = {None: DEFAULT_SCHEMA}
        if MAP_PUBLIC_TO_DEFAULT and DEFAULT_SCHEMA:
            schema_map["public"] = DEFAULT_SCHEMA
        configure_kwargs["schema_translate_map"] = schema_map

    context.configure(**configure_kwargs)

    with context.begin_transaction():
        context.run_migrations()

# ------------------------------------------------------------
# Online migrations
# ------------------------------------------------------------
def run_migrations_online() -> None:
    url = _get_database_url()
    log.info(
        "[alembic] online url=%s | schema=%s | version_table=%s (%s) | extensions=%s",
        _mask_url(url), DEFAULT_SCHEMA, VERSION_TABLE, VERSION_TABLE_SCHEMA, ", ".join(PG_EXTENSIONS) or "-",
    )

    engine = sa.create_engine(url, poolclass=pool.NullPool, echo=SQL_ECHO)

    with engine.connect() as connection:
        _diag_connection(connection, "pre")

        _ensure_schema_and_extensions(connection, DEFAULT_SCHEMA)
        _set_session_search_path(connection, DEFAULT_SCHEMA)
        _log_version_tables(connection, when="before")

        # ★ Închide BEGIN(implicit) creat de apelurile anterioare
        _end_open_tx(connection, "pre")

        render_as_batch = FORCE_BATCH_SQLITE or (connection.dialect.name == "sqlite")

        configure_kwargs: Dict[str, Any] = dict(
            connection=connection,
            target_metadata=target_metadata,
            include_name=include_name,
            include_object=include_object,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            render_as_batch=render_as_batch,
            version_table=VERSION_TABLE,
            version_table_schema=VERSION_TABLE_SCHEMA,
            process_revision_directives=process_revision_directives,
            transaction_per_migration=TX_PER_MIGRATION,
        )

        if USE_SCHEMA_TRANSLATE and DEFAULT_SCHEMA:
            schema_map: Dict[Optional[str], Optional[str]] = {None: DEFAULT_SCHEMA}
            if MAP_PUBLIC_TO_DEFAULT and DEFAULT_SCHEMA:
                schema_map["public"] = DEFAULT_SCHEMA
            configure_kwargs["schema_translate_map"] = schema_map

        context.configure(**configure_kwargs)

        with context.begin_transaction():
            context.run_migrations()

        _end_open_tx(connection, "alembic")

        _log_version_tables(connection, when="after")
        _diag_connection(connection, "post")

        # curățăm orice tranzacție implicită deschisă de diag
        try:
            connection.rollback()
        except Exception:
            pass

    # ✅ verificăm DOAR DUPĂ ce s-a închis conexiunea de migrare
    if VERIFY_WITH_NEW_CONN and ASSERT_TABLES:
        _assert_tables_exist_url(url, DEFAULT_SCHEMA, ASSERT_TABLES)

# ------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
