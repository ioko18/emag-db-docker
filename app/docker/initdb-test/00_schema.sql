DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'app') THEN
    EXECUTE format('CREATE SCHEMA %I AUTHORIZATION %I', 'app', current_user);
  END IF;
END $$;

ALTER DATABASE appdb_test SET search_path = app, public;
ALTER ROLE appuser IN DATABASE appdb_test SET search_path = app, public;
