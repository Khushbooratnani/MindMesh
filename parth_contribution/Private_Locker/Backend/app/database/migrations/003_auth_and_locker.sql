-- 003_auth_and_locker.sql

-- 1. Create users table
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(128) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Insert the default development user so existing records have a valid owner_id
INSERT INTO users (id, username, password_hash)
VALUES ('U_DEVELOPMENT', 'development', 'NO_LOGIN_ALLOWED')
ON CONFLICT (id) DO NOTHING;

-- 2. Create user_sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    id VARCHAR(36) PRIMARY KEY,
    token_hash VARCHAR(256) UNIQUE NOT NULL,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions(user_id);

-- 3. Create private_lockers table
CREATE TABLE IF NOT EXISTS private_lockers (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(64) UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    password_hash VARCHAR(256) NOT NULL,
    recovery_key_hash VARCHAR(256) NOT NULL,
    failed_attempts INTEGER DEFAULT 0 NOT NULL,
    lockout_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 4. Create locker_sessions table
CREATE TABLE IF NOT EXISTS locker_sessions (
    id VARCHAR(36) PRIMARY KEY,
    token_hash VARCHAR(256) UNIQUE NOT NULL,
    locker_id VARCHAR(36) NOT NULL REFERENCES private_lockers(id) ON DELETE CASCADE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    revoked BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_locker_sessions_locker_id ON locker_sessions(locker_id);

-- 5. Add owner_id and privacy to raw_inputs
ALTER TABLE raw_inputs ADD COLUMN IF NOT EXISTS owner_id VARCHAR(64) DEFAULT 'U_DEVELOPMENT' NOT NULL;
ALTER TABLE raw_inputs ADD COLUMN IF NOT EXISTS privacy VARCHAR(32) DEFAULT 'ONLY_ME' NOT NULL;
ALTER TABLE raw_inputs ADD CONSTRAINT fk_raw_inputs_users FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS ix_raw_inputs_owner_id ON raw_inputs(owner_id);
CREATE INDEX IF NOT EXISTS ix_raw_inputs_privacy ON raw_inputs(privacy);

-- 6. Add owner_id and privacy to phase1_outputs
ALTER TABLE phase1_outputs ADD COLUMN IF NOT EXISTS owner_id VARCHAR(64) DEFAULT 'U_DEVELOPMENT' NOT NULL;
ALTER TABLE phase1_outputs ADD COLUMN IF NOT EXISTS privacy VARCHAR(32) DEFAULT 'ONLY_ME' NOT NULL;
ALTER TABLE phase1_outputs ADD CONSTRAINT fk_phase1_outputs_users FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS ix_phase1_outputs_owner_id ON phase1_outputs(owner_id);
CREATE INDEX IF NOT EXISTS ix_phase1_outputs_privacy ON phase1_outputs(privacy);

-- (Optional) Update existing records explicitly if constraints aren't doing it
UPDATE raw_inputs SET owner_id = 'U_DEVELOPMENT' WHERE owner_id IS NULL;
UPDATE phase1_outputs SET owner_id = 'U_DEVELOPMENT' WHERE owner_id IS NULL;
