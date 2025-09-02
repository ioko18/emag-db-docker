-- scripts/smoke.sql
-- Smoke test idempotent pentru schema "app".
-- Rulabil de oricâte ori; pregătit pentru rulare în CI.

\pset pager off
\set ON_ERROR_STOP on
\timing off

SET application_name = 'smoke.sql';
SET client_min_messages = warning;
SET statement_timeout = '30s';
SET lock_timeout = '2s';
SET search_path TO app, public;

-- ─────────────────────────────────────────────────────────────────────────────
-- 0) Context: versiuni, search_path, extensii, alembic_version
-- ─────────────────────────────────────────────────────────────────────────────
SELECT now() AT TIME ZONE 'UTC' AS utc_now;

SHOW search_path;
SHOW server_version;

-- extensii critice și schema lor
SELECT e.extname, n.nspname AS schema
FROM pg_extension e
JOIN pg_namespace n ON n.oid = e.extnamespace
WHERE e.extname IN ('pg_stat_statements','pg_trgm')
ORDER BY e.extname;

-- alembic_version: trebuie să fie în schema app și NU în public
SELECT to_regclass('app.alembic_version')    IS NOT NULL AS app_version_table_present,
       to_regclass('public.alembic_version') IS NULL     AS public_version_table_absent;

-- info conexă
SELECT current_database() AS db, current_schema;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) Date de probă idempotente (fără ON CONFLICT)
-- ─────────────────────────────────────────────────────────────────────────────

-- categorie fixă (cu ID stabil)
INSERT INTO app.categories (id, name, description)
SELECT 9001, 'Teste Electronica', 'Smoke category'
WHERE NOT EXISTS (SELECT 1 FROM app.categories WHERE id = 9001);

-- categorie "Arduino" (case-insensitive, fără ID fix)
INSERT INTO app.categories (name, description)
SELECT 'Arduino', 'MCU boards'
WHERE NOT EXISTS (
  SELECT 1 FROM app.categories WHERE lower(name) = lower('Arduino')
);

-- products
INSERT INTO app.products (id, name, description, price, sku)
SELECT 9101, 'Amplificator audio TPA3116', '2x50W', 129.90, 'SKU-SMOKE-TPA3116'
WHERE NOT EXISTS (SELECT 1 FROM app.products WHERE id = 9101);

INSERT INTO app.products (name, description, price, sku)
SELECT 'Senzor DS18B20', 'temperatura', 19.90, 'SKU-SMOKE-DS18B20'
WHERE NOT EXISTS (SELECT 1 FROM app.products WHERE sku = 'SKU-SMOKE-DS18B20');

-- un produs cu "Arduino" în nume pentru testul de căutare trigram
INSERT INTO app.products (name, description, price, sku)
SELECT 'Arduino UNO R3 compatibil', 'placa MCU compatibila', 89.90, 'SKU-SMOKE-ARDUINO'
WHERE NOT EXISTS (SELECT 1 FROM app.products WHERE sku = 'SKU-SMOKE-ARDUINO');

-- atașări M2M idempotente
-- 9101 -> 9001
INSERT INTO app.product_categories (product_id, category_id)
SELECT p.id, 9001
FROM app.products p
WHERE p.sku = 'SKU-SMOKE-TPA3116'
  AND NOT EXISTS (
    SELECT 1 FROM app.product_categories pc
    WHERE pc.product_id = p.id AND pc.category_id = 9001
  );

-- 'Arduino UNO R3 compatibil' -> categoria "Arduino"
INSERT INTO app.product_categories (product_id, category_id)
SELECT p.id, c.id
FROM app.products p
JOIN app.categories c ON lower(c.name) = 'arduino'
WHERE p.sku = 'SKU-SMOKE-ARDUINO'
  AND NOT EXISTS (
    SELECT 1 FROM app.product_categories pc
    WHERE pc.product_id = p.id AND pc.category_id = c.id
  );

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) Ajustează secvențele (dacă ID-urile au fost inserate manual)
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  seq text;
  max_id bigint;
BEGIN
  SELECT pg_get_serial_sequence('app.products','id') INTO seq;
  IF seq IS NOT NULL THEN
    SELECT COALESCE(MAX(id), 0) INTO max_id FROM app.products;
    EXECUTE format('SELECT setval(%L, %s, true);', seq, max_id);
  END IF;

  SELECT pg_get_serial_sequence('app.categories','id') INTO seq;
  IF seq IS NOT NULL THEN
    SELECT COALESCE(MAX(id), 0) INTO max_id FROM app.categories;
    EXECUTE format('SELECT setval(%L, %s, true);', seq, max_id);
  END IF;
END$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3) Verificări audit & trigger – existență coloane și trigger
-- ─────────────────────────────────────────────────────────────────────────────
-- coloane audit
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='app'
  AND table_name IN ('products','categories','product_categories')
  AND column_name IN ('created_at','updated_at')
ORDER BY table_name, column_name;

-- trigger prezent?
SELECT relname AS table, tgname AS trigger_name
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname='app' AND tgname IN (
  'tg_products_set_timestamps',
  'tg_categories_set_timestamps',
  'tg_product_categories_set_timestamps'
)
ORDER BY relname;

-- toate rândurile au created_at/updated_at populate?
SELECT 'products' AS tbl,
       SUM((created_at IS NULL)::int) AS created_at_nulls,
       SUM((updated_at IS NULL)::int) AS updated_at_nulls
FROM app.products
UNION ALL
SELECT 'categories',
       SUM((created_at IS NULL)::int),
       SUM((updated_at IS NULL)::int)
FROM app.categories
UNION ALL
SELECT 'product_categories',
       SUM((created_at IS NULL)::int),
       SUM((updated_at IS NULL)::int)
FROM app.product_categories;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4) Indexuri relevante (inclusiv trigram) – existență
-- ─────────────────────────────────────────────────────────────────────────────
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname='app' AND tablename='products'
  AND indexname IN ('ix_products_name_trgm','ix_products_sku_trgm',
                    'ix_products_name','ix_products_name_lower','ix_products_price')
ORDER BY indexname;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5) EXPLAIN ANALYZE – demonstrează folosirea indexurilor trigram
--    (Setările LOCAL trebuie să fie într-o tranzacție.)
-- ─────────────────────────────────────────────────────────────────────────────

-- a) name CONTAINS 'arduino' (trigram)
BEGIN;
  SET LOCAL enable_seqscan = off;
  EXPLAIN (ANALYZE, COSTS, SUMMARY)
  SELECT id, name
  FROM app.products
  WHERE lower(name) LIKE '%arduino%';
ROLLBACK;

-- b) sku prefix 'SKU-SMOKE-A%' (trigram cu WHERE sku IS NOT NULL)
BEGIN;
  SET LOCAL enable_seqscan = off;
  EXPLAIN (ANALYZE, COSTS, SUMMARY)
  SELECT id, sku
  FROM app.products
  WHERE sku IS NOT NULL
    AND lower(sku) LIKE 'sku-smoke-a%';
ROLLBACK;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6) Agregări/rapoarte rapide
-- ─────────────────────────────────────────────────────────────────────────────
SELECT COUNT(*) AS products_total FROM app.products;
SELECT COUNT(*) AS categories_total FROM app.categories;

SELECT c.id, c.name, COUNT(pc.product_id) AS products_in_cat
FROM app.categories c
LEFT JOIN app.product_categories pc ON pc.category_id = c.id
GROUP BY c.id, c.name
ORDER BY c.name;

-- Mostră produse (ultimele 5)
SELECT id, name, sku, price, created_at, updated_at
FROM app.products
ORDER BY id DESC
LIMIT 5;

-- ─────────────────────────────────────────────────────────────────────────────
-- 7) Observabilitate: există pg_stat_statements (în app sau public)?
-- ─────────────────────────────────────────────────────────────────────────────
SELECT to_regclass('pg_stat_statements') IS NOT NULL AS pg_stat_statements_available;

DO $$
BEGIN
  IF to_regclass('pg_stat_statements') IS NOT NULL THEN
    RAISE NOTICE 'pg_stat_statements e disponibil.';
    -- doar verificăm că vizualizarea răspunde
    PERFORM 1 FROM pg_stat_statements LIMIT 1;
  END IF;
EXCEPTION WHEN undefined_table THEN
  NULL; -- extensia nu e disponibilă; ignorăm
END$$;

-- (opțional, pentru citire manuală)
-- SELECT calls, round(total_exec_time::numeric,2) AS total_ms,
--        round(mean_exec_time::numeric,2) AS mean_ms,
--        left(query, 200) AS query
-- FROM pg_stat_statements
-- ORDER BY total_exec_time DESC
-- LIMIT 3;

-- ─────────────────────────────────────────────────────────────────────────────
-- 8) Validări finale „OK flags”
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
  (SELECT to_regclass('app.alembic_version') IS NOT NULL)  AS ok_alembic_in_app,
  (SELECT to_regclass('public.alembic_version') IS NULL)   AS ok_no_public_version,
  (SELECT current_setting('search_path'))                  AS effective_search_path;

-- EOF
