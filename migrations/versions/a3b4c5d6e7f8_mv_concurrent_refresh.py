# migrations/versions/a3b4c5d6e7f8_mv_concurrent_refresh.py
"""Enable concurrent refresh for eMAG MVs"""
from alembic import op
import os

revision = "a3b4c5d6e7f8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None

def upgrade():
    schema = op.get_context().version_table_schema or os.getenv("DB_SCHEMA", "app")
    # Indexuri UNICE necesare pentru CONCURRENTLY
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_emag_stock_summary_offer ON "{schema}".mv_emag_stock_summary (offer_id);')
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_emag_best_offer_offer  ON "{schema}".mv_emag_best_offer (offer_id);')

    # Primul refresh concurent (în afara tranzacției)
    with op.get_context().autocommit_block():
        op.execute(f'REFRESH MATERIALIZED VIEW CONCURRENTLY "{schema}".mv_emag_stock_summary;')
        op.execute(f'REFRESH MATERIALIZED VIEW CONCURRENTLY "{schema}".mv_emag_best_offer;')

def downgrade():
    schema = op.get_context().version_table_schema or os.getenv("DB_SCHEMA", "app")
    op.execute(f'DROP INDEX IF EXISTS "{schema}".ux_mv_emag_best_offer_offer;')
    op.execute(f'DROP INDEX IF EXISTS "{schema}".ux_mv_emag_stock_summary_offer;')
