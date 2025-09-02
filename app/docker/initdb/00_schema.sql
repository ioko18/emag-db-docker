DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'app') THEN
    EXECUTE format('CREATE SCHEMA app AUTHORIZATION %I', current_user);
  END IF;
END $$;

ALTER DATABASE appdb SET search_path = app, public;
ALTER ROLE appuser IN DATABASE appdb SET search_path = app, public;
