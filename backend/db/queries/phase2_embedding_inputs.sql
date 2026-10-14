SELECT
    memory_id,
    owner_id,
    group_id,
    media_type,
    privacy,
    text_for_embedding
FROM memory_embedding_inputs
ORDER BY created_at, memory_id;
