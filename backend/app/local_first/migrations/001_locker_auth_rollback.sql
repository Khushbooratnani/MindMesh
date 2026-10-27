-- ==============================================================================
-- MindMesh Separate Locker Authentication Database Schema Rollback
-- Database Target: mindmesh_locker_auth
-- Version: 001_locker_auth_rollback
-- ==============================================================================

DROP TABLE IF EXISTS locker_auth_sessions CASCADE;
DROP TABLE IF EXISTS locker_auth_identities CASCADE;
