-- ==============================================================================
-- MindMesh Platform Schema Migration Rollback: 005_rollback_locations_and_spatial.sql
-- Rolls back memory locations and spatial tables
-- ==============================================================================

BEGIN;
DROP TABLE IF EXISTS memory_locations CASCADE;
DROP TABLE IF EXISTS locations CASCADE;
COMMIT;
