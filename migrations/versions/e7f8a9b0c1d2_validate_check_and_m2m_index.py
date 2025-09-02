"""validate CHECK(price>=0) and add composite index on product_categories

Revision ID: e7f8a9b0c1d2
Revises: d2c3b4a5f6e7
Create Date: 2025-08-31
"""
from alembic import op
import os
import re

# Alembic identifiers
revision = "e7f8a9b0c1d2"
down_revision = "d2c3b4a5f6e7"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DB_SCHEMA", "app")

_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _assert_safe_schema(schema: str) -> None:
    if not _SAFE_IDENT.match(schema):
        raise ValueError(f"Unsafe schema name: {schema!r}")


def upgrade() -> None:
    _assert_safe_schema(SCHEMA)

    # 1) Asigură existența și VALIDATE pentru CHECK (price >= 0) pe app.products
    op.execute(
        f"""
        DO $$
        DECLARE
          v_exists boolean;
          v_convalidated boolean;
        BEGIN
          -- există deja constraint-ul?
          SELECT EXISTS (
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = '{SCHEMA}'
              AND t.relname = 'products'
              AND c.conname = 'ck_products_price_nonnegative'
          ) INTO v_exists;

          -- dacă nu există, îl adăugăm NOT VALID (idempotent)
          IF NOT v_exists THEN
            EXECUTE format(
              'ALTER TABLE %I.products ADD CONSTRAINT ck_products_price_nonnegative CHECK (price >= 0) NOT VALID',
              '{SCHEMA}'
            );
          END IF;

          -- validăm dacă încă e NOT VALID
          SELECT c.convalidated
          INTO v_convalidated
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          JOIN pg_namespace n ON n.oid = t.relnamespace
          WHERE n.nspname = '{SCHEMA}'
            AND t.relname = 'products'
            AND c.conname = 'ck_products_price_nonnegative';

          IF NOT v_convalidated THEN
            EXECUTE format(
              'ALTER TABLE %I.products VALIDATE CONSTRAINT ck_products_price_nonnegative',
              '{SCHEMA}'
            );
          END IF;
        END$$;
        """
    )

    # 2) Index compus pe M2M pentru interogări inverse category->products
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS ix_product_categories_category_id_product_id
        ON "{SCHEMA}".product_categories (category_id, product_id);
        """
    )


def downgrade() -> None:
    _assert_safe_schema(SCHEMA)
    # Nu "de-validăm" constraint-ul; doar eliminăm indexul (idempotent)
    op.execute(
        f"""
        DROP INDEX IF EXISTS "{SCHEMA}".ix_product_categories_category_id_product_id;
        """
    )
