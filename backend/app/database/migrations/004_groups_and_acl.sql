-- ==============================================================================
-- MindMesh Platform Schema Migration: 004_groups_and_acl.sql
-- Production Groups, Memberships, Invitations, ACLs & Collaborative Comments
-- ==============================================================================

-- 1. Table: groups
CREATE TABLE IF NOT EXISTS groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    description TEXT,
    avatar_url VARCHAR(512),
    created_by VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    is_archived BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_groups_created_by ON groups(created_by);
CREATE INDEX IF NOT EXISTS idx_groups_created_at ON groups(created_at);

-- 2. Table: group_members
CREATE TABLE IF NOT EXISTS group_members (
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(32) DEFAULT 'MEMBER' NOT NULL, -- OWNER, ADMIN, CONTRIBUTOR, MEMBER, GUEST
    joined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (group_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_group_members_user_id ON group_members(user_id);
CREATE INDEX IF NOT EXISTS idx_group_members_role ON group_members(role);

-- 3. Table: group_invitations
CREATE TABLE IF NOT EXISTS group_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    inviter_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invitee_email VARCHAR(256) NOT NULL,
    token_hash VARCHAR(256) UNIQUE NOT NULL,
    role VARCHAR(32) DEFAULT 'MEMBER' NOT NULL,
    status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, -- PENDING, ACCEPTED, REJECTED, EXPIRED, REVOKED
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_group_invitations_group_id ON group_invitations(group_id);
CREATE INDEX IF NOT EXISTS idx_group_invitations_email ON group_invitations(invitee_email);

-- 4. Table: memory_group_access (Resource-Level Group Sharing ACL)
CREATE TABLE IF NOT EXISTS memory_group_access (
    memory_id VARCHAR(64) NOT NULL REFERENCES phase1_outputs(memory_id) ON DELETE CASCADE,
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    granted_by VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    can_edit BOOLEAN DEFAULT FALSE NOT NULL,
    can_reshare BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (memory_id, group_id)
);
CREATE INDEX IF NOT EXISTS idx_mga_group_id ON memory_group_access(group_id);
CREATE INDEX IF NOT EXISTS idx_mga_memory_id ON memory_group_access(memory_id);

-- 5. Table: memory_user_access (Resource-Level Individual Sharing ACL)
CREATE TABLE IF NOT EXISTS memory_user_access (
    memory_id VARCHAR(64) NOT NULL REFERENCES phase1_outputs(memory_id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    granted_by VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    can_edit BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (memory_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_mua_user_id ON memory_user_access(user_id);
CREATE INDEX IF NOT EXISTS idx_mua_memory_id ON memory_user_access(memory_id);

-- 6. Table: group_feed_references (Explicit Memory Feed Associations)
CREATE TABLE IF NOT EXISTS group_feed_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id VARCHAR(64) NOT NULL REFERENCES phase1_outputs(memory_id) ON DELETE CASCADE,
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    shared_by VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_group_feed_ref UNIQUE (group_id, memory_id)
);
CREATE INDEX IF NOT EXISTS idx_gfr_group_id ON group_feed_references(group_id);
CREATE INDEX IF NOT EXISTS idx_gfr_memory_id ON group_feed_references(memory_id);

-- 7. Table: group_activities (Group Event Audit Trail)
CREATE TABLE IF NOT EXISTS group_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    actor_id VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    activity_type VARCHAR(64) NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_group_activities_group_id ON group_activities(group_id);

-- 8. Table: comments (Collaborative Memory Discussions & Knowledge Capture)
CREATE TABLE IF NOT EXISTS comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id VARCHAR(64) NOT NULL REFERENCES phase1_outputs(memory_id) ON DELETE CASCADE,
    author_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_knowledge_eligible BOOLEAN DEFAULT FALSE NOT NULL,
    derived_memory_id VARCHAR(64) REFERENCES phase1_outputs(memory_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_memory_id ON comments(memory_id);
CREATE INDEX IF NOT EXISTS idx_comments_author_id ON comments(author_id);
CREATE INDEX IF NOT EXISTS idx_comments_created_at ON comments(created_at);
