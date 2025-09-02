"""Add categories and product_categories tables with indexes and FK CASCADE."""

from __future__ import annotations

import os
from alembic import op
import sqlalchemy as sa

# Alembic identifiers
revision = "d2c3b4a5f6e7"
down_revision = "cc1e2f3a4b5c"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DEFAULT_SCHEMA") or os.getenv("DB_SCHEMA") or "app"

T_CAT = "categories"
T_PC = "product_categories"
IX_CAT_NAME_LOWER = "ix_categories_name_lower"
IX_PC_CAT = "ix_product_categories_category_id"


def _qi(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _qt(schema: str | None, table: str) -> str:
    return f'{_qi(schema)}.{_qi(table)}' if schema else _qi(table)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    dialect = bind.dialect.name

    tables = set(insp.get_table_names(schema=SCHEMA))

    # 1) categories
    if T_CAT not in tables:
        op.create_table(
            T_CAT,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            schema=SCHEMA,
        )

    # Unique pe nume: functional (PG) sau constraint clasic pe alte dialecte
    idx_cat = {ix["name"] for ix in insp.get_indexes(T_CAT, schema=SCHEMA)}
    if dialect == "postgresql":
        if IX_CAT_NAME_LOWER not in idx_cat:
            op.execute(sa.text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS "{IX_CAT_NAME_LOWER}" '
                f"ON {_qt(SCHEMA, T_CAT)} (lower(name))"
            ))
    else:
        uqs = {uc["name"] for uc in insp.get_unique_constraints(T_CAT, schema=SCHEMA)}
        if "uq_categories_name" not in uqs:
            with op.batch_alter_table(T_CAT, schema=SCHEMA) as batch_op:
                batch_op.create_unique_constraint("uq_categories_name", ["name"])

    # 2) product_categories (M2M)
    if T_PC not in tables:
        op.create_table(
            T_PC,
            sa.Column("product_id", sa.Integer, nullable=False),
            sa.Column("category_id", sa.Integer, nullable=False),
            sa.PrimaryKeyConstraint("product_id", "category_id", name="pk_product_categories"),
            sa.ForeignKeyConstraint(
                ["product_id"],
                [f"{SCHEMA}.products.id"],
                ondelete="CASCADE",
                name="fk_product_categories_product_id_products",
            ),
            sa.ForeignKeyConstraint(
                ["category_id"],
                [f"{SCHEMA}.categories.id"],
                ondelete="CASCADE",
                name="fk_product_categories_category_id_categories",
            ),
            schema=SCHEMA,
        )

    # index util pentru filtrări după categorii
    idx_pc = {ix["name"] for ix in insp.get_indexes(T_PC, schema=SCHEMA)}
    if IX_PC_CAT not in idx_pc:
        op.create_index(IX_PC_CAT, T_PC, ["category_id"], schema=SCHEMA)


def downgrade() -> None:
    # Drop în ordinea inversă a dependențelor
    op.drop_index(IX_PC_CAT, table_name=T_PC, schema=SCHEMA)
    op.drop_table(T_PC, schema=SCHEMA)

    # PG: functional unique index
    op.execute(sa.text(f'DROP INDEX IF EXISTS {(_qi(SCHEMA) + ".") if SCHEMA else ""}"{IX_CAT_NAME_LOWER}"'))
    # non-PG: unique constraint clasic (dacă a fost creat)
    try:
        with op.batch_alter_table(T_CAT, schema=SCHEMA) as batch_op:
            batch_op.drop_constraint("uq_categories_name", type_="unique")
    except Exception:
        pass

    op.drop_table(T_CAT, schema=SCHEMA)
