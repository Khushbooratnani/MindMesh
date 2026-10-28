-- ==============================================================================
-- MindMesh Platform Schema Migration: 001_initial_schema.sql
-- Foundation for Raw Inputs and Phase 1 Structured JSON Persistence
-- Target Database: mindmesh (PostgreSQL 18+ / pgvector compatible)
-- ==============================================================================

-- Enable UUID and vector extensions if available (safe, non-destructive)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ------------------------------------------------------------------------------
-- 1. Table: raw_inputs
-- Purpose: Persists the verbatim original user payload before any processing
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_inputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    media_type VARCHAR(32) NOT NULL,
    raw_payload TEXT NOT NULL,
    structured_payload JSONB,
    client_id VARCHAR(64) NOT NULL DEFAULT 'U_DEVELOPMENT',
    group_id VARCHAR(64),
    status VARCHAR(32) NOT NULL DEFAULT 'received',
    error_message TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indices for raw_inputs
CREATE INDEX IF NOT EXISTS idx_raw_inputs_media_type ON raw_inputs(media_type);
CREATE INDEX IF NOT EXISTS idx_raw_inputs_status ON raw_inputs(status);
CREATE INDEX IF NOT EXISTS idx_raw_inputs_client_id ON raw_inputs(client_id);
CREATE INDEX IF NOT EXISTS idx_raw_inputs_group_id ON raw_inputs(group_id);
CREATE INDEX IF NOT EXISTS idx_raw_inputs_received_at ON raw_inputs(received_at);

COMMENT ON TABLE raw_inputs IS 'Verbatim original input received from user/client before processing';
COMMENT ON COLUMN raw_inputs.raw_payload IS 'Exact original text or raw serialized string payload';
COMMENT ON COLUMN raw_inputs.structured_payload IS 'Optional structured JSONB representation for querying';
COMMENT ON COLUMN raw_inputs.status IS 'Processing status: received, processing, completed, failed';

-- ------------------------------------------------------------------------------
-- 2. Table: phase1_outputs
-- Purpose: Persists complete unflattened MemoryV1 JSON output produced by Phase 1
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS phase1_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_input_id UUID NOT NULL REFERENCES raw_inputs(id) ON DELETE CASCADE,
    memory_id VARCHAR(64) NOT NULL UNIQUE,
    schema_version VARCHAR(16) NOT NULL DEFAULT '1.0',
    payload JSONB NOT NULL,
    processing_status VARCHAR(32) NOT NULL DEFAULT 'completed',
    extractor_model VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indices for phase1_outputs
CREATE INDEX IF NOT EXISTS idx_phase1_outputs_raw_input_id ON phase1_outputs(raw_input_id);
CREATE INDEX IF NOT EXISTS idx_phase1_outputs_memory_id ON phase1_outputs(memory_id);
CREATE INDEX IF NOT EXISTS idx_phase1_outputs_processing_status ON phase1_outputs(processing_status);
CREATE INDEX IF NOT EXISTS idx_phase1_outputs_created_at ON phase1_outputs(created_at);
CREATE INDEX IF NOT EXISTS idx_phase1_outputs_payload_gin ON phase1_outputs USING GIN (payload);

COMMENT ON TABLE phase1_outputs IS 'Complete validated MemoryV1 JSON outputs linked to original raw inputs';
COMMENT ON COLUMN phase1_outputs.payload IS 'Complete unflattened MemoryV1 JSON structure';
