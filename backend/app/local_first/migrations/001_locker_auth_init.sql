-- ==============================================================================
-- MindMesh Separate Locker Authentication Database Schema Migration
-- Database Target: mindmesh_locker_auth
-- Version: 001_locker_auth_init
-- Description: Creates isolated credential verifiers and session tracking tables.
-- INVARIANT: No user memories, media, vectors, or keys may ever be added here.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS locker_auth_identities (
    id VARCHAR(36) PRIMARY KEY,
    user_reference VARCHAR(64) UNIQUE NOT NULL,
    argon2_hash VARCHAR(256) NOT NULL,
    recovery_hash VARCHAR(256) NOT NULL,
    failed_attempts INTEGER DEFAULT 0 NOT NULL,
    lockout_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_locker_auth_user_ref ON locker_auth_identities (user_reference);

CREATE TABLE IF NOT EXISTS locker_auth_sessions (
    id VARCHAR(36) PRIMARY KEY,
    token_hash VARCHAR(256) UNIQUE NOT NULL,
    identity_id VARCHAR(36) NOT NULL REFERENCES locker_auth_identities(id) ON DELETE CASCADE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    revoked BOOLEAN DEFAULT FALSE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_locker_auth_sessions_token_hash ON locker_auth_sessions (token_hash);
CREATE INDEX IF NOT EXISTS idx_locker_auth_sessions_identity ON locker_auth_sessions (identity_id);
CREATE INDEX IF NOT EXISTS idx_locker_auth_sessions_revoked ON locker_auth_sessions (revoked);
