# migrations/versions/a3b4c5d6e7f9_perf_indexes.py
"""Perf indexes for eMAG tables"""
from alembic import op
import os

revision = "a3b4c5d6e7f9"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None

def upgrade():
    schema = op.get_context().version_table_schema or os.getenv("DB_SCHEMA", "app")
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_emag_offers_acc_country ON "{schema}".emag_offers (account_id, country);')
    op.execute(f'CREATE INDEX IF NOT EXISTS ix_emag_product_map_acc_country ON "{schema}".emag_product_map (account_id, country);')

def downgrade():
    schema = op.get_context().version_table_schema or os.getenv("DB_SCHEMA", "app")
    op.execute(f'DROP INDEX IF EXISTS "{schema}".ix_emag_product_map_acc_country;')
    op.execute(f'DROP INDEX IF EXISTS "{schema}".ix_emag_offers_acc_country;')
