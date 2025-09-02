# app/routers/observability.py
from __future__ import annotations

import os
from fastapi import APIRouter, HTTPException, Query, Depends, Header
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db


# -----------------------------------------------------------------------------
# Helpers & constants
# -----------------------------------------------------------------------------
_DDL_DCL_UTILITY = (
    "begin,commit,rollback,start,savepoint,release,"
    "prepare,deallocate,"
    "set,reset,show,"
    "explain,analyze,vacuum,checkpoint,refresh,discard,"
    "listen,unlisten,notify,lock,copy,security,cluster,"
    "create,alter,drop,grant,revoke,truncate,comment,"
    "call,do,declare,fetch,close"
)
_DDL_LIST = [x.strip().lower() for x in _DDL_DCL_UTILITY.split(",") if x.strip()]
# regex de început de linie (după normalizare) pentru utilitare/DDL.
# Folosim operatorul ~* (case-insensitive), deci nu mai punem (?i) în pattern.
DDL_BOL_RX = r"^\s*(?:" + "|".join(_DDL_LIST) + r")\b"

# regex robust pentru referințe la pg_stat_statements
_SELF_RX = r"(?is)\bpg_stat_statements(?:_info|_reset)?\b"


def _sql_quote_list_csv(csv_values: str) -> str:
    """
    Transformă 'a, b, a' -> 'a','b'
    (lowercase, unic, escaped pentru Postgres)
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in csv_values.split(","):
        v = raw.strip().lower()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append("'" + v.replace("'", "''") + "'")
    return ", ".join(out)


def _pgss_installed(db: Session) -> bool:
    return bool(
        db.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pg_stat_statements')")
        ).scalar_one()
    )


def _pgss_view_present(db: Session) -> bool:
    return bool(
        db.execute(
            text(
                """
                SELECT EXISTS (
                  SELECT 1
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                   WHERE c.relname = 'pg_stat_statements'
                     AND c.relkind IN ('v','m')
                )
                """
            )
        ).scalar_one()
    )


def _ensure_pgss(db: Session) -> None:
    if not _pgss_installed(db) or not _pgss_view_present(db):
        raise HTTPException(
            status_code=503,
            detail=(
                "pg_stat_statements not available. "
                "Pornește Postgres cu shared_preload_libraries=pg_stat_statements, "
                "apoi rulează: CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
            ),
        )


def _obs_guard(x_obs_key: str | None = Header(default=None, alias="X-Obs-Key")) -> None:
    expected = os.getenv("OBS_API_KEY")
    if expected and x_obs_key != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Obs-Key")


# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------
router = APIRouter(
    prefix="/observability",
    tags=["observability"],
    dependencies=[Depends(_obs_guard)],
)


# -----------------------------------------------------------------------------
# Endpoints generale
# -----------------------------------------------------------------------------
@router.get("/extensions")
def list_extensions(db: Session = Depends(get_db)):
    rows = (
        db.execute(
            text(
                """
                SELECT e.extname, n.nspname AS schema
                  FROM pg_extension e
                  JOIN pg_namespace n ON n.oid = e.extnamespace
                 WHERE e.extname IN ('pg_stat_statements','pg_trgm')
                 ORDER BY e.extname;
                """
            )
        )
        .mappings()
        .all()
    )
    return {"extensions": [dict(r) for r in rows]}


@router.get("/pgss/available")
def pgss_available(db: Session = Depends(get_db)):
    installed = _pgss_installed(db)
    view_present = _pgss_view_present(db)
    return {
        "pg_stat_statements_installed": installed,
        "pg_stat_statements_view_present": view_present,
        "pg_stat_statements_available": installed and view_present,
    }


@router.get("/pgss/info")
def pgss_info(db: Session = Depends(get_db)):
    _ensure_pgss(db)
    row = db.execute(text("SELECT * FROM pg_stat_statements_info()")).mappings().one()
    return {"info": dict(row)}


@router.get("/settings")
def pg_settings(db: Session = Depends(get_db)):
    rows = (
        db.execute(
            text(
                """
                SELECT name, setting
                  FROM pg_settings
                 WHERE name IN (
                   'pg_stat_statements.max',
                   'pg_stat_statements.save',
                   'pg_stat_statements.track',
                   'pg_stat_statements.track_utility',
                   'shared_preload_libraries',
                   'track_activity_query_size'
                 )
                 ORDER BY name;
                """
            )
        )
        .mappings()
        .all()
    )
    return {"settings": [dict(r) for r in rows]}


# -----------------------------------------------------------------------------
# Activitate curentă
# -----------------------------------------------------------------------------
@router.get("/active")
def active(
    min_ms: int = Query(1000, ge=0, description="Durată minimă a query-ului activ, în ms"),
    state: str = Query(
        "active",
        pattern=r"^(active|idle in transaction|idle in transaction \(aborted\))$",
    ),
    limit: int = Query(50, ge=1, le=200),
    qlen: int = Query(500, ge=1, le=2000),
    application_name: str | None = Query(None, description="Filtru exact pe application_name"),
    db: Session = Depends(get_db),
):
    where = [
        "pid <> pg_backend_pid()",
        "state = :state",
        "now() - query_start >= (:min_ms || ' milliseconds')::interval",
    ]
    params: dict[str, object] = {"min_ms": min_ms, "state": state, "limit": limit, "qlen": qlen}

    if application_name:
        where.append("application_name = :appname")
        params["appname"] = application_name

    sql = f"""
        SELECT pid,
               now() - query_start                  AS duration,
               backend_type,
               client_addr::text                    AS client_addr,
               xact_start,
               query_start,
               wait_event_type,
               wait_event,
               state,
               left(query, :qlen)                   AS query,
               application_name,
               usename                               AS username,
               datname                               AS dbname
          FROM pg_stat_activity
         WHERE {' AND '.join(where)}
      ORDER BY duration DESC
         LIMIT :limit
    """
    rows = db.execute(text(sql), params).mappings().all()
    return {"count": len(rows), "items": [dict(r) for r in rows]}


# -----------------------------------------------------------------------------
# Top queries din pg_stat_statements
# -----------------------------------------------------------------------------
@router.get("/top-queries")
def top_queries(
    limit: int = Query(20, ge=1, le=200),
    order_by: str = Query(
        "total_exec_time",
        pattern=r"^(total_exec_time|mean_exec_time|min_exec_time|max_exec_time|stddev_exec_time|calls|rows|rows_per_call)$",
    ),
    order_dir: str = Query("desc", pattern=r"^(asc|desc)$"),
    offset: int = Query(0, ge=0),
    decimals: int = Query(2, ge=0, le=6),
    min_calls: int = Query(1, ge=1),
    min_mean_ms: float | None = Query(None, ge=0),
    min_total_ms: float | None = Query(None, ge=0),
    exclude_ddl: bool = Query(False, description="Exclude DDL/DCL/utility (best-effort)"),
    exclude_self: bool = Query(True, description="Exclude interogările de observabilitate (self)"),
    search: str | None = Query(None, description="Filtru ILIKE în textul query-ului"),
    username: str | None = Query(None, description="Filtrează după rol (pg_roles.rolname)"),
    dbname: str | None = Query(None, description="Filtrează după baza de date (pg_database.datname)"),
    include_query_text: bool = Query(True, description="Dacă false, nu include textul query-ului"),
    qlen: int = Query(500, ge=1, le=2000, description="Lungime maximă query în răspuns"),
    db: Session = Depends(get_db),
):
    _ensure_pgss(db)

    order_by_map = {
        "total_exec_time":  "total_ms",
        "mean_exec_time":   "mean_ms",
        "min_exec_time":    "min_ms",
        "max_exec_time":    "max_ms",
        "stddev_exec_time": "stddev_ms",
        "calls":            "calls",
        "rows":             "rows",
        "rows_per_call":    "rows_per_call",
    }
    order_sql = order_by_map[order_by]
    order_dir_sql = "ASC" if order_dir.lower() == "asc" else "DESC"

    where = ["s.calls >= :min_calls"]
    params: dict[str, object] = {
        "min_calls": min_calls,
        # IMPORTANT: ddl_bol_rx e folosit în CTE → îl legăm întotdeauna
        "ddl_bol_rx": DDL_BOL_RX,
    }

    if min_mean_ms is not None:
        where.append("s.mean_exec_time >= :min_mean_ms")
        params["min_mean_ms"] = min_mean_ms
    if min_total_ms is not None:
        where.append("s.total_exec_time >= :min_total_ms")
        params["min_total_ms"] = min_total_ms

    if search:
        where.append("COALESCE(s.query,'') ILIKE ('%' || :search || '%')")
        params["search"] = search

    if exclude_ddl:
        # folosim marcajul calculat în CTE
        where.append("NOT s.is_utility")

    if exclude_self:
        params["self_rx"] = _SELF_RX
        where.append("COALESCE(s.norm,'') !~* :self_rx")

    if username:
        where.append("r.rolname = :username")
        params["username"] = username
    if dbname:
        where.append("d.datname = :dbname")
        params["dbname"] = dbname

    query_col = "left(s.query, :qlen) AS query" if include_query_text else "NULL::text AS query"

    sql = f"""
        WITH s AS (
            SELECT
                queryid,
                dbid,
                userid,
                calls,
                total_exec_time,
                min_exec_time,
                max_exec_time,
                stddev_exec_time,
                mean_exec_time,
                rows,
                CASE WHEN calls > 0 THEN rows::numeric / calls ELSE 0 END AS rows_per_call,
                query,
                -- normalizez: scot comentariile și tai spațiile la stânga
                ltrim(
                    regexp_replace(
                        regexp_replace(COALESCE(query, ''), '/\\*.*?\\*/', '', 'gs'),
                        '--[^\\n]*', '', 'g'
                    )
                ) AS norm,
                -- primul cuvânt (lowercased) din query-ul normalizat
                COALESCE(
                    lower(substring(
                        ltrim(
                            regexp_replace(
                                regexp_replace(COALESCE(query, ''), '/\\*.*?\\*/', '', 'gs'),
                                '--[^\\n]*', '', 'g'
                            )
                        )
                        from '^([a-z]+)'
                    )),
                    ''
                ) AS first_kw,
                -- marcaj utility/DDL: fie primul cuvânt e în listă, fie începe cu acel cuvânt (regex)
                (
                  COALESCE(
                    lower(substring(
                        ltrim(
                            regexp_replace(
                                regexp_replace(COALESCE(query, ''), '/\\*.*?\\*/', '', 'gs'),
                                '--[^\\n]*', '', 'g'
                            )
                        )
                        from '^([a-z]+)'
                    )),
                    ''
                  ) IN ({_sql_quote_list_csv(_DDL_DCL_UTILITY)})
                  OR
                  ltrim(
                    regexp_replace(
                        regexp_replace(COALESCE(query, ''), '/\\*.*?\\*/', '', 'gs'),
                        '--[^\\n]*', '', 'g'
                    )
                  ) ~* :ddl_bol_rx
                ) AS is_utility
            FROM pg_stat_statements
        )
        SELECT
            s.queryid,
            s.calls,
            round(s.total_exec_time::numeric,  :d) AS total_ms,
            round(s.mean_exec_time::numeric,   :d) AS mean_ms,
            round(s.min_exec_time::numeric,    :d) AS min_ms,
            round(s.max_exec_time::numeric,    :d) AS max_ms,
            round(s.stddev_exec_time::numeric, :d) AS stddev_ms,
            s.rows,
            round(s.rows_per_call::numeric,    :d) AS rows_per_call,
            {query_col},
            r.rolname AS username,
            d.datname AS dbname
          FROM s
          JOIN pg_roles    r ON r.oid = s.userid
          JOIN pg_database d ON d.oid = s.dbid
         WHERE {' AND '.join(where)}
      ORDER BY {order_sql} {order_dir_sql}, s.queryid ASC
         LIMIT :limit
        OFFSET :offset
    """

    params.update({
        "d": decimals,
        "limit": limit,
        "offset": offset,
        "qlen": qlen,
    })

    rows = db.execute(text(sql), params).mappings().all()
    return {
        "count": len(rows),
        "order_by": order_by,
        "order_dir": order_dir_sql,
        "items": [dict(r) for r in rows],
    }


@router.post("/pgss/reset", status_code=204)
def pgss_reset(db: Session = Depends(get_db)):
    _ensure_pgss(db)
    db.execute(text("SELECT pg_stat_statements_reset()"))
    return None


# -----------------------------------------------------------------------------
# Waiters ↔ Blockers (locks)
# -----------------------------------------------------------------------------
@router.get("/locks")
def locks(
    min_wait_ms: int = Query(0, ge=0, description="Durata minimă a așteptării (ms)"),
    only_blocked: bool = Query(True, description="Afișează doar procese efectiv blocate"),
    qlen: int = Query(300, ge=1, le=2000),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    base_where = []
    if only_blocked:
        base_where.append("w.wait_event_type = 'Lock'")
    if min_wait_ms > 0:
        base_where.append("now() - w.query_start >= (:min_wait_ms || ' milliseconds')::interval")
    if not base_where:
        base_where.append("TRUE")

    sql = f"""
    WITH waiting AS (
      SELECT l.*,
             a.query_start,
             a.usename,
             a.datname,
             a.application_name,
             a.client_addr::text AS client_addr,
             a.state,
             a.wait_event_type,
             a.query
        FROM pg_locks l
        JOIN pg_stat_activity a ON a.pid = l.pid
       WHERE NOT l.granted
    ),
    blocking AS (
      SELECT l.*,
             a.query_start,
             a.usename,
             a.datname,
             a.application_name,
             a.client_addr::text AS client_addr,
             a.state,
             a.query
        FROM pg_locks l
        JOIN pg_stat_activity a ON a.pid = l.pid
       WHERE l.granted
    )
    SELECT
      w.pid                               AS waiting_pid,
      now() - w.query_start               AS waiting_duration,
      w.state                             AS waiting_state,
      left(w.query, :qlen)                AS waiting_query,
      w.usename                           AS waiting_username,
      w.datname                           AS waiting_dbname,
      w.application_name                  AS waiting_app,
      w.client_addr                       AS waiting_client,
      b.pid                               AS blocking_pid,
      b.state                             AS blocking_state,
      left(b.query, :qlen)                AS blocking_query,
      b.usename                           AS blocking_username,
      b.datname                           AS blocking_dbname,
      b.application_name                  AS blocking_app,
      b.client_addr                       AS blocking_client,
      w.locktype,
      w.mode                              AS waiting_mode,
      b.mode                              AS blocking_mode
    FROM waiting w
    JOIN blocking b
      ON b.locktype = w.locktype
     AND b.database IS NOT DISTINCT FROM w.database
     AND b.relation IS NOT DISTINCT FROM w.relation
     AND b.page     IS NOT DISTINCT FROM w.page
     AND b.tuple    IS NOT DISTINCT FROM w.tuple
     AND b.classid  IS NOT DISTINCT FROM w.classid
     AND b.objid    IS NOT DISTINCT FROM w.objid
     AND b.objsubid IS NOT DISTINCT FROM w.objsubid
     AND b.transactionid IS NOT DISTINCT FROM w.transactionid
    WHERE {" AND ".join(base_where)}
    ORDER BY waiting_duration DESC
    LIMIT :limit
    """
    params = {"qlen": qlen, "limit": limit, "min_wait_ms": min_wait_ms}
    rows = db.execute(text(sql), params).mappings().all()
    return {"count": len(rows), "items": [dict(r) for r in rows]}


# -----------------------------------------------------------------------------
# Generator simplu de trafic (dev utility)
# -----------------------------------------------------------------------------
@router.post("/sample-load")
def sample_load(
    n: int = Query(200, ge=1, le=10_000, description="Număr de interogări generate"),
    search: str | None = Query(None, description="Pattern pentru ILIKE pe products.name"),
    db: Session = Depends(get_db),
):
    _ensure_pgss(db)
    pat = f"%{(search or '').lower()}%"
    for i in range(n):
        db.execute(text("SELECT current_schema()"))
        db.execute(text("SELECT pg_catalog.version()"))
        try:
            db.execute(
                text(
                    "SELECT count(*) FROM app.products "
                    "WHERE (:s) IS NULL OR lower(name) ILIKE :pat"
                ),
                {"s": search, "pat": pat},
            )
        except Exception:
            # tabela poate lipsi; ignorăm
            pass
        if (i + 1) % 200 == 0:
            db.flush()
    return {"generated": n}
