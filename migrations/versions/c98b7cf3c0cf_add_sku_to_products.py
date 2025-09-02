"""add sku column to products + partial unique index (PG)"""

from __future__ import annotations

import os
from alembic import op
import sqlalchemy as sa

revision = "c98b7cf3c0cf"
down_revision = "7786bc4a4177"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"
TABLE = "products"
COL = "sku"
IDX = "ix_products_sku"


def _qi(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _qt(schema: str | None, table: str) -> str:
    return f'{_qi(schema)}.{_qi(table)}' if schema else _qi(table)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    insp = sa.inspect(bind)

    # 1) add column if missing
    cols = {c["name"] for c in insp.get_columns(TABLE, schema=SCHEMA)}
    if COL not in cols:
        with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
            batch_op.add_column(sa.Column(COL, sa.String(64), nullable=True))

    # 2) index
    idx_names = {ix["name"] for ix in insp.get_indexes(TABLE, schema=SCHEMA)}
    if IDX not in idx_names:
        if dialect == "postgresql":
            op.execute(
                sa.text(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS "{IDX}" '
                    f"ON {_qt(SCHEMA, TABLE)} ({_qi(COL)}) WHERE {_qi(COL)} IS NOT NULL"
                )
            )
        else:
            op.create_index(IDX, TABLE, [COL], unique=False, schema=SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if IDX in {ix["name"] for ix in insp.get_indexes(TABLE, schema=SCHEMA)}:
        op.drop_index(IDX, table_name=TABLE, schema=SCHEMA)

    if COL in {c["name"] for c in insp.get_columns(TABLE, schema=SCHEMA)}:
        with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
            batch_op.drop_column(COL)
