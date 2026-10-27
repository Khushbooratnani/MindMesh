-- =============================================================================
-- MindMesh — Rollback Migration: 003_auth_and_locker
-- =============================================================================
-- WARNING: This script drops Private Locker tables and removes locker columns.
-- Only execute this if you need to revert the database schema to pre-locker state.
-- =============================================================================

BEGIN;

-- Drop locker sessions table
DROP TABLE IF EXISTS locker_sessions CASCADE;

-- Drop private lockers table
DROP TABLE IF EXISTS private_lockers CASCADE;

-- Drop user sessions table (if created by 003)
DROP TABLE IF EXISTS user_sessions CASCADE;

-- Note: The users table is preserved to prevent losing user accounts.
-- If users table needs to be dropped (only if no other tables depend on it):
-- DROP TABLE IF EXISTS users CASCADE;

-- Remove added columns from phase1_outputs if they exist
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='phase1_outputs' AND column_name='privacy') THEN
        ALTER TABLE phase1_outputs DROP COLUMN privacy;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='phase1_outputs' AND column_name='owner_id') THEN
        ALTER TABLE phase1_outputs DROP COLUMN owner_id;
    END IF;
END $$;

-- Remove added columns from raw_inputs if they exist
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='raw_inputs' AND column_name='privacy') THEN
        ALTER TABLE raw_inputs DROP COLUMN privacy;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='raw_inputs' AND column_name='owner_id') THEN
        ALTER TABLE raw_inputs DROP COLUMN owner_id;
    END IF;
END $$;

COMMIT;
