# migrations/versions/a2b3c4d5e6f7_emag_core_schema.py
"""eMAG core schema (accounts, map, offers, stock/price history, images, mviews)

Revision ID: a2b3c4d5e6f7
Revises: f0e1d2c3b4a5
Create Date: 2025-09-02
"""
from __future__ import annotations

import os
from alembic import op
import sqlalchemy as sa


# Alembic identifiers
revision = "a2b3c4d5e6f7"
down_revision = "f0e1d2c3b4a5"
branch_labels = None
depends_on = None


# --------------------------- Helpers ---------------------------

def _qi(s: str) -> str:
    """Quote identifier."""
    return '"' + s.replace('"', '""') + '"'


def _qn(schema: str, name: str) -> str:
    """Qualified name schema.name (or just name for public)."""
    return f"{_qi(schema)}.{_qi(name)}" if schema and schema != "public" else _qi(name)


def _set_local_search_path(schema: str) -> None:
    op.execute(f"SET LOCAL search_path TO {_qi(schema)}, public")


def _ensure_country_code_enum(schema: str) -> None:
    """Create ENUM schema.country_code and ensure values exist (idempotent)."""
    # NOTE: use EXECUTE format with %I (identifier) / %L (literal) to avoid quoting bugs
    op.execute(f"""
    DO $$
    DECLARE typ_oid oid;
    BEGIN
      SELECT t.oid
        INTO typ_oid
      FROM pg_type t
      JOIN pg_namespace n ON n.oid = t.typnamespace
      WHERE t.typname = 'country_code' AND n.nspname = '{schema}';

      IF typ_oid IS NULL THEN
        EXECUTE format('CREATE TYPE %I.%I AS ENUM (%L, %L, %L)',
                       '{schema}', 'country_code', 'RO', 'BG', 'HU');
      END IF;

      -- add values defensively, in case type exists but values differ
      EXECUTE format('ALTER TYPE %I.%I ADD VALUE IF NOT EXISTS %L', '{schema}','country_code','RO');
      EXECUTE format('ALTER TYPE %I.%I ADD VALUE IF NOT EXISTS %L', '{schema}','country_code','BG');
      EXECUTE format('ALTER TYPE %I.%I ADD VALUE IF NOT EXISTS %L', '{schema}','country_code','HU');
    END$$;
    """)


def _cast_country_to_enum(schema: str, table: str, default: str = "RO") -> None:
    """Cast TEXT country -> schema.country_code, keeping DEFAULT."""
    tbl = _qn(schema, table)
    enum_t = _qn(schema, "country_code")
    op.execute(f"ALTER TABLE {tbl} ALTER COLUMN country DROP DEFAULT;")
    op.execute(f"ALTER TABLE {tbl} ALTER COLUMN country TYPE {enum_t} USING country::text::{enum_t};")
    op.execute(f"ALTER TABLE {tbl} ALTER COLUMN country SET DEFAULT '{default}'::{enum_t};")


def _drop_enum_if_unused(schema: str, name: str) -> None:
    """Drop ENUM schema.name iff no columns still use it."""
    op.execute(f"""
    DO $$
    DECLARE typ_oid oid;
    DECLARE cnt int;
    BEGIN
      SELECT t.oid
        INTO typ_oid
      FROM pg_type t
      JOIN pg_namespace n ON n.oid = t.typnamespace
      WHERE t.typname = '{name}' AND n.nspname = '{schema}';

      IF typ_oid IS NOT NULL THEN
        SELECT count(*) INTO cnt
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE a.atttypid = typ_oid AND a.attnum > 0 AND NOT a.attisdropped;

        IF cnt = 0 THEN
          EXECUTE format('DROP TYPE %I.%I', '{schema}', '{name}');
        END IF;
      END IF;
    END$$;
    """)


# -------------------------------- Upgrade --------------------------------

def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Determine target schema at runtime (safe: no op.get_context() at module import)
    ctx = op.get_context()
    schema = ctx.version_table_schema or os.getenv("DB_SCHEMA", "app")

    if dialect == "postgresql":
        _set_local_search_path(schema)
        _ensure_country_code_enum(schema)

    # emag_account
    op.create_table(
        "emag_account",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=schema,
        comment="Conturi eMAG (MAIN/FBE).",
    )

    # trigger utilitar: set_updated_at()
    if dialect == "postgresql":
        op.execute(f"""
        CREATE OR REPLACE FUNCTION {_qn(schema, "set_updated_at")}() RETURNS trigger AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

    # emag_product_map (country ca TEXT, apoi CAST la ENUM pentru a evita CREATE TYPE implicit)
    op.create_table(
        "emag_product_map",
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey(f"{schema}.products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.SmallInteger(), sa.ForeignKey(f"{schema}.emag_account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country", sa.Text(), nullable=False, server_default=sa.text("'RO'")),
        sa.Column("emag_sku", sa.Text(), nullable=False),
        sa.Column("ean", sa.Text(), nullable=True),
        sa.Column("ean_list", sa.ARRAY(sa.Text()), nullable=True) if dialect == "postgresql" else sa.Column("ean_list", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("account_id", "country", "emag_sku", name="pk_emag_product_map"),
        schema=schema,
    )
    op.create_unique_constraint(
        "ux_emag_product_map_acc_country_product",
        "emag_product_map",
        ["account_id", "country", "product_id"],
        schema=schema,
    )
    op.create_index("ix_emag_product_map_product_id", "emag_product_map", ["product_id"], schema=schema)
    if dialect == "postgresql":
        op.create_index(
            "ix_emag_product_map_emag_sku_lower",
            "emag_product_map",
            [sa.text("lower(emag_sku)")],
            schema=schema,
        )
        op.execute(f"""
        CREATE TRIGGER trg_emag_product_map_updated_at
          BEFORE UPDATE ON {_qn(schema, "emag_product_map")}
          FOR EACH ROW EXECUTE FUNCTION {_qn(schema, "set_updated_at")}();
        """)
        _cast_country_to_enum(schema, "emag_product_map")
    else:
        op.create_index("ix_emag_product_map_emag_sku", "emag_product_map", ["emag_sku"], schema=schema)

    # emag_offers (country ca TEXT, apoi CAST la ENUM)
    op.create_table(
        "emag_offers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("account_id", sa.SmallInteger(), sa.ForeignKey(f"{schema}.emag_account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country", sa.Text(), nullable=False, server_default=sa.text("'RO'")),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey(f"{schema}.products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=True),
        sa.Column("sale_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("handling_time", sa.Integer(), nullable=True),
        sa.Column("supply_lead_time", sa.Integer(), nullable=True),
        sa.Column("validation_status_value", sa.SmallInteger(), nullable=True),
        sa.Column("validation_status_text", sa.Text(), nullable=True),
        sa.Column("images_count", sa.Integer(), nullable=True),
        sa.Column("stock_total", sa.Integer(), nullable=True),
        sa.Column("general_stock", sa.Integer(), nullable=True),
        sa.Column("estimated_stock", sa.Integer(), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=True),
        sa.Column("ean", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("account_id", "country", "product_id", name="ux_emag_offers_acc_country_product"),
        schema=schema,
    )
    op.create_index(
        "ix_emag_offers_acc_country_prod",
        "emag_offers",
        ["account_id", "country", "product_id"],
        schema=schema,
    )
    op.create_index(
        "ix_emag_offers_acc_country_price",
        "emag_offers",
        ["account_id", "country", "sale_price", "product_id"],
        schema=schema,
    )
    op.create_index(
        "ix_emag_offers_stock_total",
        "emag_offers",
        ["stock_total"],
        schema=schema,
    )
    if dialect == "postgresql":
        op.execute(f"""
        CREATE TRIGGER trg_emag_offers_updated_at
          BEFORE UPDATE ON {_qn(schema, "emag_offers")}
          FOR EACH ROW EXECUTE FUNCTION {_qn(schema, "set_updated_at")}();
        """)
        _cast_country_to_enum(schema, "emag_offers")

    # stoc curent pe depozit
    op.create_table(
        "emag_offer_stock_by_wh",
        sa.Column("offer_id", sa.BigInteger(), sa.ForeignKey(f"{schema}.emag_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_code", sa.Text(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("incoming", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("offer_id", "warehouse_code", name="pk_emag_offer_stock_by_wh"),
        schema=schema,
    )
    op.create_index(
        "ix_emag_offer_stock_by_wh_offer",
        "emag_offer_stock_by_wh",
        ["offer_id"],
        schema=schema,
    )
    if dialect == "postgresql":
        op.execute(f"""
        CREATE TRIGGER trg_emag_offer_stock_by_wh_updated_at
          BEFORE UPDATE ON {_qn(schema, "emag_offer_stock_by_wh")}
          FOR EACH ROW EXECUTE FUNCTION {_qn(schema, "set_updated_at")}();
        """)

    # istorice (partitioned, PG only)
    if dialect == "postgresql":
        op.execute(f"""
        CREATE TABLE IF NOT EXISTS {_qn(schema, "emag_offer_prices_hist")} (
          offer_id    BIGINT NOT NULL REFERENCES {_qn(schema, "emag_offers")}(id) ON DELETE CASCADE,
          recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          currency    CHAR(3) NOT NULL,
          sale_price  NUMERIC(12,2) NOT NULL CHECK (sale_price >= 0),
          PRIMARY KEY (offer_id, recorded_at)
        ) PARTITION BY RANGE (recorded_at);

        CREATE TABLE IF NOT EXISTS {_qn(schema, "emag_offer_stock_hist")} (
          offer_id       BIGINT NOT NULL REFERENCES {_qn(schema, "emag_offers")}(id) ON DELETE CASCADE,
          warehouse_code TEXT NOT NULL,
          recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
          stock          INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
          reserved       INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
          incoming       INTEGER NOT NULL DEFAULT 0 CHECK (incoming >= 0),
          PRIMARY KEY (offer_id, warehouse_code, recorded_at)
        ) PARTITION BY RANGE (recorded_at);
        """)

        # creează două partiții: luna curentă și luna următoare
        op.execute(f"""
        DO $$
        DECLARE
          start_curr date := date_trunc('month', now())::date;
          start_next date := (date_trunc('month', now()) + interval '1 month')::date;
          start_next2 date := (date_trunc('month', now()) + interval '2 month')::date;
          nm text;
        BEGIN
          nm := to_char(start_curr, '"p_y"YYYY"m"MM');
          EXECUTE format('CREATE TABLE IF NOT EXISTS {_qi(schema)}.%s PARTITION OF {_qi(schema)}.emag_offer_prices_hist FOR VALUES FROM (%L) TO (%L);',
                        nm, start_curr, start_next);
          nm := to_char(start_next, '"p_y"YYYY"m"MM');
          EXECUTE format('CREATE TABLE IF NOT EXISTS {_qi(schema)}.%s PARTITION OF {_qi(schema)}.emag_offer_prices_hist FOR VALUES FROM (%L) TO (%L);',
                        nm, start_next, start_next2);

          nm := to_char(start_curr, '"s_y"YYYY"m"MM');
          EXECUTE format('CREATE TABLE IF NOT EXISTS {_qi(schema)}.%s PARTITION OF {_qi(schema)}.emag_offer_stock_hist FOR VALUES FROM (%L) TO (%L);',
                        nm, start_curr, start_next);
          nm := to_char(start_next, '"s_y"YYYY"m"MM');
          EXECUTE format('CREATE TABLE IF NOT EXISTS {_qi(schema)}.%s PARTITION OF {_qi(schema)}.emag_offer_stock_hist FOR VALUES FROM (%L) TO (%L);',
                        nm, start_next, start_next2);
        END$$;
        """)

    # imagini & istoric validare
    op.create_table(
        "emag_images",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey(f"{schema}.products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("is_main", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=schema,
    )
    op.create_unique_constraint(
        "ux_emag_images_product_url",
        "emag_images",
        ["product_id", "url"],
        schema=schema,
    )
    if dialect == "postgresql":
        op.create_index(
            "ix_emag_images_main",
            "emag_images",
            ["product_id"],
            schema=schema,
            postgresql_where=sa.text("is_main"),
        )
    else:
        op.create_index("ix_emag_images_product", "emag_images", ["product_id"], schema=schema)

    op.create_table(
        "emag_validation_status_hist",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("offer_id", sa.BigInteger(), sa.ForeignKey(f"{schema}.emag_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=schema,
    )
    op.create_index(
        "ix_emag_validation_status_hist_offer_time",
        "emag_validation_status_hist",
        ["offer_id", "occurred_at"],
        unique=False,
        schema=schema,
    )

    # materialized views
    if dialect == "postgresql":
        op.execute(f"""
        CREATE MATERIALIZED VIEW IF NOT EXISTS {_qn(schema, "mv_emag_stock_summary")} AS
        SELECT
          offer_id,
          SUM(stock)    AS stock_total,
          SUM(reserved) AS reserved_total,
          MAX(updated_at) AS last_update
        FROM {_qn(schema, "emag_offer_stock_by_wh")}
        GROUP BY offer_id
        WITH NO DATA;

        CREATE MATERIALIZED VIEW IF NOT EXISTS {_qn(schema, "mv_emag_best_offer")} AS
        SELECT
          o.id AS offer_id,
          o.account_id,
          o.country,
          o.product_id,
          o.currency,
          o.sale_price,
          COALESCE(s.stock_total, o.stock_total) AS stock_total,
          GREATEST(o.updated_at, COALESCE(s.last_update, o.updated_at)) AS as_of
        FROM {_qn(schema, "emag_offers")} o
        LEFT JOIN {_qn(schema, "mv_emag_stock_summary")} s ON s.offer_id = o.id
        WITH NO DATA;
        """)


# -------------------------------- Downgrade -------------------------------

def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    ctx = op.get_context()
    schema = ctx.version_table_schema or os.getenv("DB_SCHEMA", "app")

    if dialect == "postgresql":
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {_qn(schema, 'mv_emag_best_offer')};")
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {_qn(schema, 'mv_emag_stock_summary')};")

    op.drop_index("ix_emag_validation_status_hist_offer_time", table_name="emag_validation_status_hist", schema=schema)
    op.drop_table("emag_validation_status_hist", schema=schema)

    if dialect == "postgresql":
        op.drop_index("ix_emag_images_main", table_name="emag_images", schema=schema)
    else:
        op.drop_index("ix_emag_images_product", table_name="emag_images", schema=schema)

    op.drop_constraint("ux_emag_images_product_url", "emag_images", type_="unique", schema=schema)
    op.drop_table("emag_images", schema=schema)

    if dialect == "postgresql":
        op.execute(f"DROP TABLE IF EXISTS {_qn(schema, 'emag_offer_stock_hist')} CASCADE;")
        op.execute(f"DROP TABLE IF EXISTS {_qn(schema, 'emag_offer_prices_hist')} CASCADE;")

    op.drop_index("ix_emag_offer_stock_by_wh_offer", table_name="emag_offer_stock_by_wh", schema=schema)
    op.drop_table("emag_offer_stock_by_wh", schema=schema)

    if dialect == "postgresql":
        op.execute(f"DROP TRIGGER IF EXISTS trg_emag_offers_updated_at ON {_qn(schema, 'emag_offers')};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_emag_product_map_updated_at ON {_qn(schema, 'emag_product_map')};")

    op.drop_index("ix_emag_offers_stock_total", table_name="emag_offers", schema=schema)
    op.drop_index("ix_emag_offers_acc_country_price", table_name="emag_offers", schema=schema)
    op.drop_index("ix_emag_offers_acc_country_prod", table_name="emag_offers", schema=schema)
    op.drop_table("emag_offers", schema=schema)

    if dialect == "postgresql":
        op.drop_index("ix_emag_product_map_emag_sku_lower", table_name="emag_product_map", schema=schema)
    else:
        op.drop_index("ix_emag_product_map_emag_sku", table_name="emag_product_map", schema=schema)

    op.drop_index("ix_emag_product_map_product_id", table_name="emag_product_map", schema=schema)
    op.drop_constraint("ux_emag_product_map_acc_country_product", "emag_product_map", type_="unique", schema=schema)
    op.drop_table("emag_product_map", schema=schema)

    op.drop_table("emag_account", schema=schema)

    if dialect == "postgresql":
        op.execute(f"DROP FUNCTION IF EXISTS {_qn(schema, 'set_updated_at')}();")
        _drop_enum_if_unused(schema, "country_code")
