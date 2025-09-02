"""Add CHECK constraint for non-negative price on products (NOT VALID first)."""

from __future__ import annotations

import os
from alembic import op
import sqlalchemy as sa

# Alembic revision identifiers
revision = "cc1e2f3a4b5c"
down_revision = "a1f2e3d4c5f6"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"
TABLE = "products"
CK_NAME = "ck_products_price_nonnegative"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # Add NOT VALID if missing, then best-effort VALIDATE
        op.execute(
            f"""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE c.conname = '{CK_NAME}'
          AND n.nspname = '{SCHEMA}'
          AND t.relname = '{TABLE}'
    ) THEN
        EXECUTE 'ALTER TABLE "{SCHEMA}"."{TABLE}" '
                'ADD CONSTRAINT "{CK_NAME}" CHECK (price IS NULL OR price >= 0) NOT VALID';
        BEGIN
            EXECUTE 'ALTER TABLE "{SCHEMA}"."{TABLE}" VALIDATE CONSTRAINT "{CK_NAME}"';
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
    END IF;
END$$;
"""
        )
    else:
        # generic path for non-PG
        insp = sa.inspect(bind)
        existing = {ck["name"] for ck in insp.get_check_constraints(TABLE, schema=SCHEMA)}
        if CK_NAME not in existing:
            with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
                batch_op.create_check_constraint(CK_NAME, "price IS NULL OR price >= 0")


def downgrade() -> None:
    op.execute(f'ALTER TABLE "{SCHEMA}"."{TABLE}" DROP CONSTRAINT IF EXISTS "{CK_NAME}";')
