from alembic import op, context
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f0e1d2c3b4a5"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def _set_search_path():
    op.execute("SET LOCAL search_path TO app, public;")


def upgrade():
    _set_search_path()

    # 1) Extensia trgm în schema app (relocatable, sigur să fie IF NOT EXISTS)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA app;")

    # 2) Coloane audit + backfill + default + check validate (fără rewrite)
    tables = ["products", "categories", "product_categories"]
    for t in tables:
        op.execute(f"ALTER TABLE app.{t} ADD COLUMN IF NOT EXISTS created_at timestamptz;")
        op.execute(f"ALTER TABLE app.{t} ADD COLUMN IF NOT EXISTS updated_at timestamptz;")
        # backfill sigur
        op.execute(
            f"""
            UPDATE app.{t}
               SET created_at = COALESCE(created_at, now()),
                   updated_at = COALESCE(updated_at, now())
             WHERE created_at IS NULL OR updated_at IS NULL;
            """
        )
        # default-uri pentru noi rânduri
        op.execute(f"ALTER TABLE app.{t} ALTER COLUMN created_at SET DEFAULT now();")
        op.execute(f"ALTER TABLE app.{t} ALTER COLUMN updated_at SET DEFAULT now();")

        # NOT NULL ca CHECK VALIDATED (evită lock puternic al SET NOT NULL)
        op.execute(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_{t}_created_at_nn'
              ) THEN
                ALTER TABLE app.{t}
                  ADD CONSTRAINT ck_{t}_created_at_nn CHECK (created_at IS NOT NULL) NOT VALID;
                ALTER TABLE app.{t} VALIDATE CONSTRAINT ck_{t}_created_at_nn;
              END IF;
            END$$;
            """
        )
        op.execute(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_{t}_updated_at_nn'
              ) THEN
                ALTER TABLE app.{t}
                  ADD CONSTRAINT ck_{t}_updated_at_nn CHECK (updated_at IS NOT NULL) NOT VALID;
                ALTER TABLE app.{t} VALIDATE CONSTRAINT ck_{t}_updated_at_nn;
              END IF;
            END$$;
            """
        )

    # 3) Trigger generic pentru audit
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.tg_set_timestamps()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          NEW.updated_at = now();
          IF NEW.created_at IS NULL THEN
            NEW.created_at = now();
          END IF;
          RETURN NEW;
        END$$;
        """
    )

    for t in tables:
        tg = f"tg_{t}_set_timestamps"
        op.execute(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1
                  FROM pg_trigger
                 WHERE tgname = '{tg}'
                   AND tgrelid = 'app.{t}'::regclass
              ) THEN
                CREATE TRIGGER {tg}
                BEFORE INSERT OR UPDATE ON app.{t}
                FOR EACH ROW EXECUTE FUNCTION app.tg_set_timestamps();
              END IF;
            END$$;
            """
        )

    # 4) Comentarii utile (documentare în catalog)
    op.execute("COMMENT ON TABLE app.products IS 'Catalog products. Time columns are UTC (timestamptz).';")
    op.execute("COMMENT ON COLUMN app.products.created_at IS 'UTC creation timestamp.';")
    op.execute("COMMENT ON COLUMN app.products.updated_at IS 'UTC last update timestamp.';")
    op.execute("COMMENT ON TABLE app.categories IS 'Product categories.';")
    op.execute("COMMENT ON TABLE app.product_categories IS 'M2M between products and categories.';")

    # 5) Indexuri GIN trigram pentru căutare (CONCURRENTLY + IF NOT EXISTS)
    #    Notă: gin_trgm_ops este creat în schema app (pentru că am pus extensia în app).
    with context.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_products_name_trgm
            ON app.products
            USING gin ((lower(name)) app.gin_trgm_ops);
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_products_sku_trgm
            ON app.products
            USING gin ((lower(sku)) app.gin_trgm_ops)
            WHERE sku IS NOT NULL;
            """
        )


def downgrade():
    _set_search_path()

    # 1) Drop indexuri (CONCURRENTLY)
    with context.get_context().autocommit_block():
        op.execute("DROP INDEX IF EXISTS app.ix_products_name_trgm;")
        op.execute("DROP INDEX IF EXISTS app.ix_products_sku_trgm;")

    # 2) Drop triggere & funcție
    for t in ["products", "categories", "product_categories"]:
        tg = f"tg_{t}_set_timestamps"
        op.execute(f"DROP TRIGGER IF EXISTS {tg} ON app.{t};")
    op.execute("DROP FUNCTION IF EXISTS app.tg_set_timestamps();")

    # 3) Drop default/check/coloane
    for t in ["products", "categories", "product_categories"]:
        op.execute(f"ALTER TABLE app.{t} ALTER COLUMN created_at DROP DEFAULT;")
        op.execute(f"ALTER TABLE app.{t} ALTER COLUMN updated_at DROP DEFAULT;")
        op.execute(f"ALTER TABLE app.{t} DROP CONSTRAINT IF EXISTS ck_{t}_created_at_nn;")
        op.execute(f"ALTER TABLE app.{t} DROP CONSTRAINT IF EXISTS ck_{t}_updated_at_nn;")
        op.execute(f"ALTER TABLE app.{t} DROP COLUMN IF EXISTS created_at;")
        op.execute(f"ALTER TABLE app.{t} DROP COLUMN IF EXISTS updated_at;")

    # Extensia pg_trgm rămâne instalată (nerecomandat să o ștergem implicit).
