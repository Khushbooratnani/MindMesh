CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    group_id TEXT,
    media_type TEXT NOT NULL CHECK (media_type IN ('text', 'image', 'audio')),
    created_at TIMESTAMPTZ NOT NULL,
    privacy TEXT NOT NULL CHECK (privacy IN ('ONLY_ME', 'GROUP', 'SELECTED')),
    allowed_users TEXT[] NOT NULL DEFAULT '{}',
    raw_text TEXT,
    clean_text TEXT NOT NULL,
    description TEXT NOT NULL,
    summary TEXT NOT NULL,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('positive', 'neutral', 'negative', 'mixed', 'unknown')),
    mentioned_dates TEXT[] NOT NULL DEFAULT '{}',
    inferred_time TEXT,
    time_of_day TEXT,
    processing_status TEXT NOT NULL CHECK (processing_status IN ('completed', 'failed', 'partial')),
    source_modality TEXT NOT NULL CHECK (source_modality IN ('text', 'image', 'audio')),
    transcription_required BOOLEAN NOT NULL,
    image_understanding_required BOOLEAN NOT NULL,
    llm_provider TEXT NOT NULL,
    llm_model TEXT NOT NULL,
    processing_errors TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS memory_entities (
    id BIGSERIAL PRIMARY KEY,
    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('person', 'place', 'location', 'event', 'organization')),
    entity_value TEXT NOT NULL,
    UNIQUE (memory_id, entity_type, entity_value)
);

CREATE TABLE IF NOT EXISTS memory_topics (
    id BIGSERIAL PRIMARY KEY,
    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    UNIQUE (memory_id, topic)
);

CREATE TABLE IF NOT EXISTS memory_activities (
    id BIGSERIAL PRIMARY KEY,
    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
    activity TEXT NOT NULL,
    UNIQUE (memory_id, activity)
);

CREATE TABLE IF NOT EXISTS memory_moods (
    id BIGSERIAL PRIMARY KEY,
    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
    mood TEXT NOT NULL,
    UNIQUE (memory_id, mood)
);

CREATE TABLE IF NOT EXISTS memory_attributes (
    id BIGSERIAL PRIMARY KEY,
    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value_json JSONB NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    source TEXT NOT NULL CHECK (source IN ('llm', 'system', 'user')),
    UNIQUE (memory_id, key)
);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    memory_id TEXT PRIMARY KEY REFERENCES memories(memory_id) ON DELETE CASCADE,
    embedding_model TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    embedded_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_embeddings_embedding_idx
ON memory_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE TABLE IF NOT EXISTS memory_embedding_jobs (
    memory_id TEXT PRIMARY KEY REFERENCES memories(memory_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    embedding_model TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_graph_jobs (
    memory_id TEXT PRIMARY KEY REFERENCES memories(memory_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    graph_model TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW memory_embedding_inputs AS
SELECT
    m.memory_id,
    m.owner_id,
    m.group_id,
    m.media_type,
    m.created_at,
    m.privacy,
    trim(concat_ws(
        E'\n',
        'Summary: ' || m.summary,
        'Description: ' || m.description,
        'Content: ' || m.clean_text,
        'People: ' || COALESCE(people.values, ''),
        'Places: ' || COALESCE(places.values, ''),
        'Locations: ' || COALESCE(locations.values, ''),
        'Organizations: ' || COALESCE(organizations.values, ''),
        'Topics: ' || COALESCE(topics.values, ''),
        'Activities: ' || COALESCE(activities.values, ''),
        'Mood: ' || COALESCE(moods.values, ''),
        'Sentiment: ' || m.sentiment,
        'Time of day: ' || COALESCE(m.time_of_day, 'unknown')
    )) AS text_for_embedding
FROM memories m
LEFT JOIN LATERAL (
    SELECT string_agg(entity_value, ', ' ORDER BY entity_value) AS values
    FROM memory_entities
    WHERE memory_id = m.memory_id AND entity_type = 'person'
) people ON true
LEFT JOIN LATERAL (
    SELECT string_agg(entity_value, ', ' ORDER BY entity_value) AS values
    FROM memory_entities
    WHERE memory_id = m.memory_id AND entity_type = 'place'
) places ON true
LEFT JOIN LATERAL (
    SELECT string_agg(entity_value, ', ' ORDER BY entity_value) AS values
    FROM memory_entities
    WHERE memory_id = m.memory_id AND entity_type = 'location'
) locations ON true
LEFT JOIN LATERAL (
    SELECT string_agg(entity_value, ', ' ORDER BY entity_value) AS values
    FROM memory_entities
    WHERE memory_id = m.memory_id AND entity_type = 'organization'
) organizations ON true
LEFT JOIN LATERAL (
    SELECT string_agg(topic, ', ' ORDER BY topic) AS values
    FROM memory_topics
    WHERE memory_id = m.memory_id
) topics ON true
LEFT JOIN LATERAL (
    SELECT string_agg(activity, ', ' ORDER BY activity) AS values
    FROM memory_activities
    WHERE memory_id = m.memory_id
) activities ON true
LEFT JOIN LATERAL (
    SELECT string_agg(mood, ', ' ORDER BY mood) AS values
    FROM memory_moods
    WHERE memory_id = m.memory_id
) moods ON true
WHERE m.processing_status = 'completed';
