-- Group and Sharing schema migration

CREATE TABLE IF NOT EXISTS groups (
    id UUID PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    created_by VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    user_id VARCHAR(64) REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL DEFAULT 'MEMBER',
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (group_id, user_id)
);

CREATE TABLE IF NOT EXISTS memory_group_access (
    memory_id VARCHAR(64) REFERENCES phase1_outputs(memory_id) ON DELETE CASCADE,
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    granted_by VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (memory_id, group_id)
);

CREATE TABLE IF NOT EXISTS memory_user_access (
    memory_id VARCHAR(64) REFERENCES phase1_outputs(memory_id) ON DELETE CASCADE,
    user_id VARCHAR(64) REFERENCES users(id) ON DELETE CASCADE,
    granted_by VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (memory_id, user_id)
);

CREATE TABLE IF NOT EXISTS group_feed_references (
    id UUID PRIMARY KEY,
    memory_id VARCHAR(64) REFERENCES phase1_outputs(memory_id) ON DELETE CASCADE,
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    shared_by VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_group_feed_references_memory_id ON group_feed_references(memory_id);
CREATE INDEX IF NOT EXISTS ix_group_feed_references_group_id ON group_feed_references(group_id);

CREATE TABLE IF NOT EXISTS comments (
    id UUID PRIMARY KEY,
    memory_id VARCHAR(64) REFERENCES phase1_outputs(memory_id) ON DELETE CASCADE,
    author_id VARCHAR(64) REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_knowledge_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    derived_memory_id VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_comments_memory_id ON comments(memory_id);
CREATE INDEX IF NOT EXISTS ix_comments_author_id ON comments(author_id);

ALTER TABLE raw_inputs ADD COLUMN IF NOT EXISTS owning_group_id UUID REFERENCES groups(id) ON DELETE SET NULL;
ALTER TABLE raw_inputs ADD COLUMN IF NOT EXISTS source_type VARCHAR(32) NOT NULL DEFAULT 'INGESTION';
ALTER TABLE raw_inputs ADD COLUMN IF NOT EXISTS parent_memory_id VARCHAR(64);
ALTER TABLE raw_inputs ADD COLUMN IF NOT EXISTS revision_of_id UUID REFERENCES raw_inputs(id) ON DELETE SET NULL;
ALTER TABLE raw_inputs ADD COLUMN IF NOT EXISTS superseded_by_id UUID REFERENCES raw_inputs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_raw_inputs_owning_group_id ON raw_inputs(owning_group_id);
CREATE INDEX IF NOT EXISTS ix_raw_inputs_source_type ON raw_inputs(source_type);
CREATE INDEX IF NOT EXISTS ix_raw_inputs_parent_memory_id ON raw_inputs(parent_memory_id);
CREATE INDEX IF NOT EXISTS ix_raw_inputs_revision_of_id ON raw_inputs(revision_of_id);
CREATE INDEX IF NOT EXISTS ix_raw_inputs_superseded_by_id ON raw_inputs(superseded_by_id);

ALTER TABLE phase1_outputs ADD COLUMN IF NOT EXISTS owning_group_id UUID REFERENCES groups(id) ON DELETE SET NULL;
ALTER TABLE phase1_outputs ADD COLUMN IF NOT EXISTS source_type VARCHAR(32) NOT NULL DEFAULT 'INGESTION';
ALTER TABLE phase1_outputs ADD COLUMN IF NOT EXISTS parent_memory_id VARCHAR(64);

CREATE INDEX IF NOT EXISTS ix_phase1_outputs_owning_group_id ON phase1_outputs(owning_group_id);
CREATE INDEX IF NOT EXISTS ix_phase1_outputs_source_type ON phase1_outputs(source_type);
CREATE INDEX IF NOT EXISTS ix_phase1_outputs_parent_memory_id ON phase1_outputs(parent_memory_id);
