"""baseline models: create products (if missing)"""

from __future__ import annotations

import os
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers ---
revision: str = "7786bc4a4177"
down_revision: Union[str, Sequence[str], None] = "89a0ef6bfc2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"
TABLE = "products"
IDX_NAME = "ix_products_name"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # create table if missing
    if TABLE not in set(insp.get_table_names(schema=SCHEMA)):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("price", sa.Numeric(12, 2), nullable=True),
            schema=SCHEMA,
        )

    # non-unique index on name
    idx_names = {ix["name"] for ix in insp.get_indexes(TABLE, schema=SCHEMA)}
    if IDX_NAME not in idx_names:
        op.create_index(IDX_NAME, TABLE, ["name"], schema=SCHEMA, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    idx_names = {ix["name"] for ix in insp.get_indexes(TABLE, schema=SCHEMA)}
    if IDX_NAME in idx_names:
        op.drop_index(IDX_NAME, table_name=TABLE, schema=SCHEMA)

    if TABLE in set(insp.get_table_names(schema=SCHEMA)):
        op.drop_table(TABLE, schema=SCHEMA)
