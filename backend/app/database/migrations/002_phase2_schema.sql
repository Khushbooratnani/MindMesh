-- ==============================================================================
-- MindMesh Platform Schema Migration: 002_phase2_schema.sql
-- Foundation for Phase 2 Dual-Vector Embeddings & Semantic Retrieval
-- Target Database: mindmesh (PostgreSQL 18+ / pgvector compatible)
-- ==============================================================================

-- Enable vector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "vector";

-- ------------------------------------------------------------------------------
-- 1. Table: phase2_embeddings
-- Purpose: Persists 1024-dim dual vector embeddings (content & context) linked
--          to the canonical MemoryV1 stored in phase1_outputs
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS phase2_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phase1_output_id UUID NOT NULL UNIQUE REFERENCES phase1_outputs(id),
    memory_id VARCHAR(64) NOT NULL UNIQUE REFERENCES phase1_outputs(memory_id),
    content_vector vector(1024) NOT NULL,
    context_vector vector(1024) NOT NULL,
    embedding_model VARCHAR(128) NOT NULL DEFAULT 'BAAI/bge-m3',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indices for phase2_embeddings
CREATE INDEX IF NOT EXISTS idx_phase2_embeddings_phase1_output_id ON phase2_embeddings(phase1_output_id);
CREATE INDEX IF NOT EXISTS idx_phase2_embeddings_memory_id ON phase2_embeddings(memory_id);
CREATE INDEX IF NOT EXISTS idx_phase2_embeddings_created_at ON phase2_embeddings(created_at);

-- Cosine Distance HNSW Index for ultra-fast ANN vector retrieval
CREATE INDEX IF NOT EXISTS idx_phase2_embeddings_content_hnsw ON phase2_embeddings USING hnsw (content_vector vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_phase2_embeddings_context_hnsw ON phase2_embeddings USING hnsw (context_vector vector_cosine_ops);

COMMENT ON TABLE phase2_embeddings IS 'Phase 2 dual 1024-dim vector representations linked to canonical MemoryV1 in phase1_outputs';
COMMENT ON COLUMN phase2_embeddings.content_vector IS '1024-dim BAAI/bge-m3 embedding of stored memory clean_text, raw_text, summary, and description';
COMMENT ON COLUMN phase2_embeddings.context_vector IS '1024-dim BAAI/bge-m3 embedding of stored memory entities, semantics, mood, and temporal attributes';
COMMENT ON COLUMN phase2_embeddings.embedding_model IS 'Embedding model identifier (default BAAI/bge-m3)';
