"""Enable concurrent refresh for eMAG MVs"""
from alembic import op
from alembic import context
from sqlalchemy import text
import os

revision = "a3b4c5d6e7f8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None

MVS = ("mv_emag_stock_summary", "mv_emag_best_offer")


def _schema() -> str:
    # Permite -x schema=... , altfel ia din Alembic sau env, default "app"
    return (
        context.get_x_argument(as_dictionary=True).get("schema")
        or op.get_context().version_table_schema
        or os.getenv("DB_SCHEMA", "app")
    )


def _is_populated(conn, schema: str, mv: str) -> bool:
    q = text("""
        SELECT ispopulated
        FROM pg_matviews
        WHERE schemaname = :schema AND matviewname = :mv
    """)
    return bool(conn.execute(q, {"schema": schema, "mv": mv}).scalar())


def _has_unique_index(conn, schema: str, mv: str) -> bool:
    # Pentru CONCURRENTLY e necesar un index UNIC (neparțial) pe MV
    q = text("""
        SELECT EXISTS (
          SELECT 1
          FROM pg_index i
          JOIN pg_class c ON c.oid = i.indrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          WHERE n.nspname = :schema
            AND c.relname  = :mv
            AND i.indisunique
            AND i.indpred IS NULL
        )
    """)
    return bool(conn.execute(q, {"schema": schema, "mv": mv}).scalar())


def _ensure_unique_indexes(schema: str):
    op.execute(text(
        f'CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_emag_stock_summary_offer '
        f'ON "{schema}".mv_emag_stock_summary (offer_id);'
    ))
    op.execute(text(
        f'CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_emag_best_offer_offer '
        f'ON "{schema}".mv_emag_best_offer (offer_id);'
    ))


def _refresh_mv(schema: str, mv: str):
    conn = op.get_bind()
    populated = _is_populated(conn, schema, mv)
    has_uq = _has_unique_index(conn, schema, mv)

    if populated and has_uq:
        # CONCURRENTLY trebuie în afara tranzacției
        with op.get_context().autocommit_block():
            op.execute(text(f'REFRESH MATERIALIZED VIEW CONCURRENTLY "{schema}".{mv};'))
    else:
        # Prima populare (sau lipsă index unic) -> refresh simplu
        op.execute(text(f'REFRESH MATERIALIZED VIEW "{schema}".{mv};'))


def upgrade():
    schema = _schema()
    _ensure_unique_indexes(schema)
    for mv in MVS:
        _refresh_mv(schema, mv)


def downgrade():
    schema = _schema()
    op.execute(text(f'DROP INDEX IF EXISTS "{schema}".ux_mv_emag_best_offer_offer;'))
    op.execute(text(f'DROP INDEX IF EXISTS "{schema}".ux_mv_emag_stock_summary_offer;'))
