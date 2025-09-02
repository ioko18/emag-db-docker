# scripts/seed_demo_offer.sh
#!/usr/bin/env bash
set -euo pipefail

echo "[$(date '+%F %T %Z')] Seeding demo offer data..."

docker compose exec -T db psql -v ON_ERROR_STOP=1 -U appuser -d appdb <<'SQL'
-- lucrăm pe schema app
SET search_path TO app, public;

DO $$
DECLARE
  -- coloane posibile (tolerăm diferențe de schemă)
  has_code    boolean;
  has_country boolean;
  has_active  boolean;
  has_created boolean;
  has_updated boolean;

  has_sku     boolean;
  has_price   boolean;

  v_prod_id   int    := 1;
  v_offer_id  bigint := 900000001;

  v_today     timestamptz := date_trunc('day', now());               -- ora 00:00 a zilei curente
  v_tomorrow  timestamptz := date_trunc('day', now() + interval '1 day'); -- ora 00:00 a zilei de mâine
BEGIN
  --------------------------------------------------------------------
  -- 1) Asigură contul (id=1), tolerând diferențe de schemă
  --------------------------------------------------------------------
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='emag_account' AND column_name='code')       INTO has_code;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='emag_account' AND column_name='country')    INTO has_country;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='emag_account' AND column_name='active')     INTO has_active;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='emag_account' AND column_name='created_at') INTO has_created;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='emag_account' AND column_name='updated_at') INTO has_updated;

  IF NOT EXISTS (SELECT 1 FROM app.emag_account WHERE id=1) THEN
    IF has_code AND has_country AND has_active AND has_created AND has_updated THEN
      INSERT INTO app.emag_account (id, code, name, country, active, created_at, updated_at)
      VALUES (1, 'demo', 'demo', 'RO', true, now(), now());
    ELSIF has_code AND has_country AND has_active THEN
      INSERT INTO app.emag_account (id, code, name, country, active)
      VALUES (1, 'demo', 'demo', 'RO', true);
    ELSIF has_code THEN
      INSERT INTO app.emag_account (id, code, name)
      VALUES (1, 'demo', 'demo');
    ELSE
      -- dacă schema cere "code" NOT NULL, inserarea asta ar eșua; în schema ta actuală e OK
      INSERT INTO app.emag_account (id, name)
      VALUES (1, 'demo');
    END IF;
  END IF;

  --------------------------------------------------------------------
  -- 2) Asigură un produs demo (id=1), tolerând diferențe de schemă
  --------------------------------------------------------------------
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='products' AND column_name='sku')   INTO has_sku;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns
                WHERE table_schema='app' AND table_name='products' AND column_name='price') INTO has_price;

  IF NOT EXISTS (SELECT 1 FROM app.products WHERE id=v_prod_id) THEN
    IF has_sku AND has_price THEN
      INSERT INTO app.products (id, name, sku, price, created_at, updated_at)
      VALUES (v_prod_id, 'Prod demo', 'SKU-DEMO', 19.99, now(), now());
    ELSIF has_sku THEN
      INSERT INTO app.products (id, name, sku, created_at, updated_at)
      VALUES (v_prod_id, 'Prod demo', 'SKU-DEMO', now(), now());
    ELSE
      INSERT INTO app.products (id, name, created_at, updated_at)
      VALUES (v_prod_id, 'Prod demo', now(), now());
    END IF;
  END IF;

  --------------------------------------------------------------------
  -- 3) Asigură oferta demo (id=900000001) – fallback dacă lipsesc coloane
  --------------------------------------------------------------------
  IF NOT EXISTS (SELECT 1 FROM app.emag_offers WHERE id=v_offer_id) THEN
    BEGIN
      INSERT INTO app.emag_offers (id, product_id, account_id, country, currency, sale_price, stock_total, updated_at)
      VALUES (v_offer_id, v_prod_id, 1, 'RO', 'RON', 19.99, 0, now());
    EXCEPTION WHEN undefined_column THEN
      INSERT INTO app.emag_offers (id, product_id, account_id)
      VALUES (v_offer_id, v_prod_id, 1)
      ON CONFLICT (id) DO NOTHING;
    END;
  END IF;

  --------------------------------------------------------------------
  -- 4) Stoc curent pe depozit, upsert pe (offer_id, warehouse_code)
  --------------------------------------------------------------------
  INSERT INTO app.emag_offer_stock_by_wh (offer_id, warehouse_code, updated_at, stock, reserved, incoming)
  VALUES (v_offer_id, 'WH-TEST', now(), 7, 1, 0)
  ON CONFLICT (offer_id, warehouse_code)
  DO UPDATE SET
    updated_at = EXCLUDED.updated_at,
    stock      = EXCLUDED.stock,
    reserved   = EXCLUDED.reserved,
    incoming   = EXCLUDED.incoming;

  --------------------------------------------------------------------
  -- 5) Istorice „pe zi” (azi și mâine), idempotent pe PK
  --    NOTĂ: folosim orele 00:00 (date_trunc('day', ...)) ca să fie stabil pentru ON CONFLICT.
  --------------------------------------------------------------------
  INSERT INTO app.emag_offer_prices_hist (offer_id, recorded_at, currency, sale_price)
  VALUES
    (v_offer_id, v_today,    'RON', 19.99),
    (v_offer_id, v_tomorrow, 'RON', 21.99)
  ON CONFLICT (offer_id, recorded_at)
  DO UPDATE SET
    currency   = EXCLUDED.currency,
    sale_price = EXCLUDED.sale_price;

  INSERT INTO app.emag_offer_stock_hist (offer_id, warehouse_code, recorded_at, stock, reserved, incoming)
  VALUES
    (v_offer_id, 'WH-TEST', v_today,    5, 0, 0),
    (v_offer_id, 'WH-TEST', v_tomorrow, 6, 1, 0)
  ON CONFLICT (offer_id, warehouse_code, recorded_at)
  DO UPDATE SET
    stock    = EXCLUDED.stock,
    reserved = EXCLUDED.reserved,
    incoming = EXCLUDED.incoming;
END
$$;

-- 6) REFRESH MVs cu timeouts (în tranzacție pentru SET LOCAL)
BEGIN;
  SET LOCAL lock_timeout = '3s';
  SET LOCAL statement_timeout = '2min';
  REFRESH MATERIALIZED VIEW app.mv_emag_stock_summary;
  REFRESH MATERIALIZED VIEW app.mv_emag_best_offer;
COMMIT;
SQL

# sumar după seed
docker compose exec -T db psql -U appuser -d appdb -c "
SELECT 'by_wh' src, count(*) FROM app.emag_offer_stock_by_wh
UNION ALL
SELECT 'offers',      count(*) FROM app.emag_offers
UNION ALL
SELECT 'prices_hist', count(*) FROM app.emag_offer_prices_hist
UNION ALL
SELECT 'stock_hist',  count(*) FROM app.emag_offer_stock_hist
UNION ALL
SELECT 'mv_stock',    count(*) FROM app.mv_emag_stock_summary
UNION ALL
SELECT 'mv_best',     count(*) FROM app.mv_emag_best_offer;
"

echo "[$(date '+%F %T %Z')] Seed done."
