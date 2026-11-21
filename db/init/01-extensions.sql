-- Felpesa DB bootstrap. Runs once, on first container init.
-- Idempotent: safe if postgres ever re-runs it manually.

-- gen_random_uuid() — used by every table's UUID PK.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- citext — case-insensitive text, useful later for emails / handles.
-- Not used in v1 schema, enabled now so we don't migrate extensions later.
CREATE EXTENSION IF NOT EXISTS citext;

-- Sanity: fail loudly if the DB name isn't what we expect.
DO $$
BEGIN
  IF current_database() <> 'felpesa_dev' THEN
    RAISE EXCEPTION 'Unexpected database: % (expected felpesa_dev)', current_database();
  END IF;
END $$;
