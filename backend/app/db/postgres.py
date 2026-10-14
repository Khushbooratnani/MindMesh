from collections.abc import Iterable
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import settings


class PostgresRepository:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or settings.database_url

    def fetch_embedding_inputs(
        self,
        embedding_model: str,
        limit: int,
        memory_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT memory_id, text_for_embedding
            FROM memory_embedding_inputs
            WHERE (%s::text[] IS NULL OR memory_id = ANY(%s::text[]))
              AND memory_id NOT IN (
                  SELECT memory_id
                  FROM memory_embeddings
                  WHERE embedding_model = %s
              )
            ORDER BY created_at, memory_id
            LIMIT %s
        """
        ids = memory_ids or None
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (ids, ids, embedding_model, limit))
                return list(cur.fetchall())

    def upsert_embedding(
        self,
        memory_id: str,
        embedding_model: str,
        embedding: list[float],
        embedded_text: str,
    ) -> None:
        query = """
            INSERT INTO memory_embeddings (
                memory_id,
                embedding_model,
                embedding,
                embedded_text
            ) VALUES (
                %s,
                %s,
                %s::vector,
                %s
            )
            ON CONFLICT (memory_id) DO UPDATE SET
                embedding_model = EXCLUDED.embedding_model,
                embedding = EXCLUDED.embedding,
                embedded_text = EXCLUDED.embedded_text,
                created_at = now()
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        memory_id,
                        embedding_model,
                        _pgvector_literal(embedding),
                        embedded_text,
                    ),
                )

    def search_similar_memories(
        self,
        owner_id: str,
        query_embedding: list[float],
        embedding_model: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                m.memory_id,
                m.summary,
                1 - (e.embedding <=> %s::vector) AS score
            FROM memory_embeddings e
            JOIN memories m ON m.memory_id = e.memory_id
            WHERE (
                m.owner_id = %s
                OR m.privacy = 'GROUP'
                OR %s = ANY(m.allowed_users)
            )
              AND e.embedding_model = %s
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
        """
        vector = _pgvector_literal(query_embedding)
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (vector, owner_id, owner_id, embedding_model, vector, limit))
                return list(cur.fetchall())

    def search_nearby_memories(
        self,
        owner_id: str,
        latitude: float,
        longitude: float,
        radius_meters: float,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = """
            WITH nearby AS (
                SELECT
                m.memory_id,
                m.summary,
                l.display_name AS location,
                l.latitude,
                l.longitude,
                ml.confidence AS location_confidence,
                ST_Distance(
                    l.point,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                ) AS distance_meters,
                ROW_NUMBER() OVER (
                    PARTITION BY m.memory_id
                    ORDER BY ST_Distance(
                        l.point,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                    ), l.location_id
                ) AS memory_location_rank
                FROM memory_locations ml
                JOIN memories m ON m.memory_id = ml.memory_id
                JOIN locations l ON l.location_id = ml.location_id
                WHERE (
                m.owner_id = %s
                OR m.privacy = 'GROUP'
                OR %s = ANY(m.allowed_users)
                )
                AND ST_DWithin(
                  l.point,
                  ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                  %s
                )
            )
            SELECT memory_id, summary, location, latitude, longitude,
                   location_confidence, distance_meters
            FROM nearby
            WHERE memory_location_rank = 1
            ORDER BY distance_meters, memory_id
            LIMIT %s
        """
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (longitude, latitude, longitude, latitude, owner_id, owner_id, longitude, latitude, radius_meters, limit))
                return list(cur.fetchall())

    def fetch_memories_by_ids(
        self,
        owner_id: str,
        memory_ids: list[str],
    ) -> list[dict[str, Any]]:
        if not memory_ids:
            return []

        query = """
            SELECT memory_id, summary
            FROM memories
            WHERE (
                owner_id = %s
                OR privacy = 'GROUP'
                OR %s = ANY(allowed_users)
            )
              AND memory_id = ANY(%s::text[])
        """
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (owner_id, owner_id, memory_ids))
                rows = list(cur.fetchall())

        row_by_id = {row["memory_id"]: row for row in rows}
        return [row_by_id[memory_id] for memory_id in memory_ids if memory_id in row_by_id]

    def fetch_graph_inputs(
        self,
        graph_model: str,
        limit: int,
        memory_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                m.memory_id,
                m.schema_version,
                m.owner_id,
                m.group_id,
                m.media_type,
                m.created_at,
                m.privacy,
                m.summary,
                m.description,
                m.clean_text,
                m.sentiment,
                m.time_of_day,
                COALESCE(
                    jsonb_agg(DISTINCT jsonb_build_object(
                        'type', me.entity_type,
                        'value', me.entity_value
                    )) FILTER (WHERE me.id IS NOT NULL),
                    '[]'::jsonb
                ) AS entities,
                COALESCE(jsonb_agg(DISTINCT mt.topic) FILTER (WHERE mt.id IS NOT NULL), '[]'::jsonb) AS topics,
                COALESCE(jsonb_agg(DISTINCT ma.activity) FILTER (WHERE ma.id IS NOT NULL), '[]'::jsonb) AS activities,
                COALESCE(jsonb_agg(DISTINCT mm.mood) FILTER (WHERE mm.id IS NOT NULL), '[]'::jsonb) AS moods
            FROM memories m
            LEFT JOIN memory_entities me ON me.memory_id = m.memory_id
            LEFT JOIN memory_topics mt ON mt.memory_id = m.memory_id
            LEFT JOIN memory_activities ma ON ma.memory_id = m.memory_id
            LEFT JOIN memory_moods mm ON mm.memory_id = m.memory_id
            WHERE m.processing_status = 'completed'
              AND (%s::text[] IS NULL OR m.memory_id = ANY(%s::text[]))
              AND m.memory_id NOT IN (
                  SELECT memory_id
                  FROM memory_graph_jobs
                  WHERE status = 'completed' AND graph_model = %s
              )
            GROUP BY m.memory_id
            ORDER BY m.created_at, m.memory_id
            LIMIT %s
        """
        ids = memory_ids or None
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (ids, ids, graph_model, limit))
                return list(cur.fetchall())

    def mark_graph_job_completed(self, memory_id: str, graph_model: str) -> None:
        self._upsert_job("memory_graph_jobs", memory_id, graph_model, "completed", None)

    def mark_embedding_job_completed(self, memory_id: str, embedding_model: str) -> None:
        self._upsert_job("memory_embedding_jobs", memory_id, embedding_model, "completed", None)

    def mark_embedding_job_failed(
        self,
        memory_id: str,
        embedding_model: str,
        error: str,
    ) -> None:
        self._upsert_job("memory_embedding_jobs", memory_id, embedding_model, "failed", error)

    def mark_graph_job_failed(self, memory_id: str, graph_model: str, error: str) -> None:
        self._upsert_job("memory_graph_jobs", memory_id, graph_model, "failed", error)

    def _upsert_job(
        self,
        table: str,
        memory_id: str,
        model: str,
        status: str,
        error: str | None,
    ) -> None:
        model_column = "embedding_model" if table == "memory_embedding_jobs" else "graph_model"
        query = f"""
            INSERT INTO {table} (memory_id, status, {model_column}, attempts, last_error)
            VALUES (%s, %s, %s, 1, %s)
            ON CONFLICT (memory_id) DO UPDATE SET
                status = EXCLUDED.status,
                {model_column} = EXCLUDED.{model_column},
                attempts = {table}.attempts + 1,
                last_error = EXCLUDED.last_error,
                updated_at = now()
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (memory_id, status, model, error))

    def _connect(self):
        return psycopg.connect(self.database_url)


def _pgvector_literal(values: Iterable[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"
