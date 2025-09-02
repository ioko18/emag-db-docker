-- app/docker/initdb/00_schema.sql
-- Bootstrap inițial pentru clusterul nou (rulat de postgres:16 la init).
-- Idempotent: folosim IF NOT EXISTS și DO-blocks defensive.

-- 0) Siguranță & claritate
SET client_min_messages = warning;

-- 1) Creează schema aplicatiei și setează proprietarul pe rolul curent
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_namespace WHERE nspname = 'app'
  ) THEN
    EXECUTE 'CREATE SCHEMA app AUTHORIZATION CURRENT_USER';
  ELSE
    -- asigură proprietarul (dacă rulăm ca superuser)
    BEGIN
      EXECUTE 'ALTER SCHEMA app OWNER TO CURRENT_USER';
    EXCEPTION WHEN insufficient_privilege THEN
      -- ignoră dacă nu avem drepturi (ex: deja deținută de alt rol non-superuser)
      NULL;
    END;
  END IF;
END$$;

-- 2) Setări persistente de search_path
--    a) la nivel de BAZĂ DE DATE (se aplică tuturor conexiunilor către acest DB)
DO $$
DECLARE
  dbname text := current_database();
BEGIN
  EXECUTE format('ALTER DATABASE %I SET search_path = app, public', dbname);
END$$;

--    b) la nivel de ROL curent, dar DOAR pentru acest DB
DO $$
DECLARE
  dbname text := current_database();
BEGIN
  EXECUTE format('ALTER ROLE CURRENT_USER IN DATABASE %I SET search_path = app, public', dbname);
END$$;

-- 3) Hardening minim pe schema public (evită CREATE arbitrar de la PUBLIC)
DO $$
BEGIN
  BEGIN
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
  EXCEPTION WHEN insufficient_privilege THEN
    -- dacă nu suntem superuser / owner de 'public', ignorăm
    NULL;
  END;
  -- păstrează USAGE (implicit oricum)
  BEGIN
    GRANT USAGE ON SCHEMA public TO PUBLIC;
  EXCEPTION WHEN insufficient_privilege THEN
    NULL;
  END;
END$$;

-- 4) Extensii pentru observabilitate & căutare

-- 4.1) pg_stat_statements (în public; necesită shared_preload_libraries configurat)
--      Dacă preload-ul nu este activ, comanda reușește, dar view-ul devine disponibil după restart.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 4.2) pg_trgm relocat în schema 'app'
--      Dacă există deja în altă schemă (ex: public), îl mutăm; altfel îl creăm direct în 'app'.
DO $$
DECLARE
  ext_schema text;
BEGIN
  SELECT n.nspname
    INTO ext_schema
  FROM pg_extension e
  JOIN pg_namespace n ON n.oid = e.extnamespace
  WHERE e.extname = 'pg_trgm';

  IF ext_schema IS NULL THEN
    -- nu e instalată -> instalează în schema 'app'
    EXECUTE 'CREATE EXTENSION pg_trgm WITH SCHEMA app';
  ELSIF ext_schema <> 'app' THEN
    -- instalată în altă parte -> mută în 'app'
    EXECUTE 'ALTER EXTENSION pg_trgm SET SCHEMA app';
  END IF;
END$$;

-- 5) Comentarii utile (documentare)
COMMENT ON SCHEMA app IS 'Schema aplicației (sursă de adevăr). Obiectiv: totul în app; public doar pentru extensii standard.';

-- 6) Verificări rapide (opțional: inofensive)
--    (Aceste SELECT-uri nu opresc init-ul; sunt doar informative în logs.)
DO $$
DECLARE
  msg text;
BEGIN
  SELECT 'search_path (DB) set to: ' || current_setting('search_path') INTO msg;
  RAISE NOTICE '%', msg;
EXCEPTION WHEN others THEN
  NULL;
END$$;

-- 7) Asigură-te că sesiunile curente folosesc schema corectă (în acest script)
SET search_path TO app, public;

-- 8) (Loc rezervat) – dacă vrei în viitor bootstrap minim de obiecte în app,
--    le poți crea explicit prefixate cu app. (ex: app.example_table)
--    Exemplu comentat:
-- CREATE TABLE IF NOT EXISTS app.__bootstrap_marker(
--   id int PRIMARY KEY,
--   created_at timestamptz DEFAULT now()
--);
