-- ==============================================================================
-- MindMesh Platform Schema Migration Rollback: 004_rollback_groups_and_acl.sql
-- Rolls back groups, memberships, invitations, ACLs, and comments
-- ==============================================================================

BEGIN;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS group_activities CASCADE;
DROP TABLE IF EXISTS group_feed_references CASCADE;
DROP TABLE IF EXISTS memory_user_access CASCADE;
DROP TABLE IF EXISTS memory_group_access CASCADE;
DROP TABLE IF EXISTS group_invitations CASCADE;
DROP TABLE IF EXISTS group_members CASCADE;
DROP TABLE IF EXISTS groups CASCADE;
COMMIT;
