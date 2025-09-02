"""Add indexes for products (price, lower(name)).

- ix_products_price: btree on (price), all dialects
- ix_products_name_lower: functional index on lower(name), PostgreSQL only
"""

from __future__ import annotations

import os
from typing import Optional
from alembic import op
import sqlalchemy as sa

revision = "a1f2e3d4c5f6"
down_revision = "c98b7cf3c0cf"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"
TABLE = "products"
IDX_PRICE = "ix_products_price"
IDX_NAME_LOWER = "ix_products_name_lower"


def _qi(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _qt(schema: str | None, table: str) -> str:
    return f'{_qi(schema)}.{_qi(table)}' if schema else _qi(table)


def _index_exists(bind, schema: Optional[str], table: str, name: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return name in {ix["name"] for ix in insp.get_indexes(table, schema=schema)}
    except NotImplementedError:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    schema = (SCHEMA or "").strip() or None

    # price index
    if dialect == "postgresql":
        if not _index_exists(bind, schema, TABLE, IDX_PRICE):
            op.execute(sa.text(f'CREATE INDEX IF NOT EXISTS "{IDX_PRICE}" ON {_qt(schema, TABLE)} (price)'))
        # lower(name) functional index
        if not _index_exists(bind, schema, TABLE, IDX_NAME_LOWER):
            op.execute(sa.text(f'CREATE INDEX IF NOT EXISTS "{IDX_NAME_LOWER}" ON {_qt(schema, TABLE)} (lower(name))'))
    else:
        if not _index_exists(bind, schema, TABLE, IDX_PRICE):
            op.create_index(IDX_PRICE, TABLE, ["price"], schema=schema, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    schema = (SCHEMA or "").strip() or None

    if dialect == "postgresql":
        # drop functional index first, then price
        op.execute(sa.text(f'DROP INDEX IF EXISTS {(_qi(schema) + ".") if schema else ""}"{IDX_NAME_LOWER}"'))
        op.execute(sa.text(f'DROP INDEX IF EXISTS {(_qi(schema) + ".") if schema else ""}"{IDX_PRICE}"'))
    else:
        if _index_exists(bind, schema, TABLE, IDX_PRICE):
            op.drop_index(IDX_PRICE, table_name=TABLE, schema=schema)
