# migrations/versions/a3b4c5d6e7f8_mv_concurrent_refresh.py
"""Enable concurrent refresh for eMAG MVs"""
from alembic import op, context
from sqlalchemy import text
import os

# Alembic identifiers
revision = "a3b4c5d6e7f8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None

# Materialized views we manage here
MVS = ("mv_emag_stock_summary", "mv_emag_best_offer")


def _schema() -> str:
    """Allow overriding with `alembic -x schema=...`; else use alembic/env/DEFAULT."""
    return (
        context.get_x_argument(as_dictionary=True).get("schema")
        or op.get_context().version_table_schema
        or os.getenv("DB_SCHEMA", "app")
    )


def _is_populated(conn, schema: str, mv: str) -> bool:
    q = text(
        """
        SELECT ispopulated
        FROM pg_matviews
        WHERE schemaname = :schema AND matviewname = :mv
        """
    )
    return bool(conn.execute(q, {"schema": schema, "mv": mv}).scalar())


def _has_unique_index(conn, schema: str, mv: str) -> bool:
    # CONCURRENTLY requires a UNIQUE, non-partial index on the MV
    q = text(
        """
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
        """
    )
    return bool(conn.execute(q, {"schema": schema, "mv": mv}).scalar())


def _ensure_unique_indexes(schema: str) -> None:
    # Create the required UNIQUE indexes (regular create is fine inside txn)
    op.execute(
        text(
            f'CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_emag_stock_summary_offer '
            f'ON "{schema}".mv_emag_stock_summary (offer_id);'
        )
    )
    op.execute(
        text(
            f'CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_emag_best_offer_offer '
            f'ON "{schema}".mv_emag_best_offer (offer_id);'
        )
    )


def _refresh_mv(schema: str, mv: str) -> None:
    conn = op.get_bind()
    populated = _is_populated(conn, schema, mv)
    has_uq = _has_unique_index(conn, schema, mv)

    if populated and has_uq:
        # CONCURRENTLY must be outside the migration txn
        with op.get_context().autocommit_block():
            op.execute(text(f'REFRESH MATERIALIZED VIEW CONCURRENTLY "{schema}".{mv};'))
    else:
        # First population (or missing UNIQUE) -> plain refresh in txn
        op.execute(text(f'REFRESH MATERIALIZED VIEW "{schema}".{mv};'))


def upgrade() -> None:
    schema = _schema()
    _ensure_unique_indexes(schema)
    for mv in MVS:
        _refresh_mv(schema, mv)


def downgrade() -> None:
    schema = _schema()
    # Drop indexes created in this migration
    op.execute(text(f'DROP INDEX IF EXISTS "{schema}".ux_mv_emag_best_offer_offer;'))
    op.execute(text(f'DROP INDEX IF EXISTS "{schema}".ux_mv_emag_stock_summary_offer;'))
