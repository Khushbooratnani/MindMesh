import json
import logging
from typing import Any, Optional
import uuid

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.phase2_embedding import Phase2EmbeddingModel
from app.database.repositories.base import BaseRepository
from app.services.authz_service import AuthorizationService

logger = logging.getLogger(__name__)


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class Phase2EmbeddingRepository:
    """Data access repository for phase2_embeddings table."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session

    async def create_or_update(
        self,
        phase1_output_id: uuid.UUID | str,
        memory_id: str,
        content_vector: list[float],
        context_vector: list[float],
        embedding_model: str = "BAAI/bge-m3",
        embedding_id: uuid.UUID | None = None,
        session: Optional[AsyncSession] = None,
    ) -> Phase2EmbeddingModel:
        """Persist or update 1024-dim dual vectors linked to phase1_output_id."""
        s = session or self.session
        if s is None:
            raise ValueError("AsyncSession required for database operation")

        target_phase1_id = (
            phase1_output_id if isinstance(phase1_output_id, uuid.UUID) else uuid.UUID(str(phase1_output_id))
        )

        # Check if record already exists
        result = await s.execute(
            select(Phase2EmbeddingModel).where(
                (Phase2EmbeddingModel.phase1_output_id == target_phase1_id)
                | (Phase2EmbeddingModel.memory_id == memory_id)
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.content_vector = content_vector
            existing.context_vector = context_vector
            existing.embedding_model = embedding_model
            record = existing
        else:
            record = Phase2EmbeddingModel(
                id=embedding_id or uuid.uuid4(),
                phase1_output_id=target_phase1_id,
                memory_id=memory_id,
                content_vector=content_vector,
                context_vector=context_vector,
                embedding_model=embedding_model,
            )
            s.add(record)

        await s.flush()
        return record

    async def get_by_id(
        self,
        embedding_id: uuid.UUID | str,
        session: Optional[AsyncSession] = None,
    ) -> Phase2EmbeddingModel | None:
        """Retrieve phase2 embedding record by primary key."""
        s = session or self.session
        if s is None:
            raise ValueError("AsyncSession required for database operation")
        target_id = embedding_id if isinstance(embedding_id, uuid.UUID) else uuid.UUID(str(embedding_id))
        result = await s.execute(
            select(Phase2EmbeddingModel)
            .options(selectinload(Phase2EmbeddingModel.phase1_output))
            .where(Phase2EmbeddingModel.id == target_id)
        )
        return result.scalar_one_or_none()

    async def get_by_phase1_output_id(
        self,
        phase1_output_id: uuid.UUID | str,
        session: Optional[AsyncSession] = None,
    ) -> Phase2EmbeddingModel | None:
        """Retrieve phase2 embedding record by phase1_output_id."""
        s = session or self.session
        if s is None:
            raise ValueError("AsyncSession required for database operation")
        target_id = (
            phase1_output_id if isinstance(phase1_output_id, uuid.UUID) else uuid.UUID(str(phase1_output_id))
        )
        result = await s.execute(
            select(Phase2EmbeddingModel)
            .options(selectinload(Phase2EmbeddingModel.phase1_output))
            .where(Phase2EmbeddingModel.phase1_output_id == target_id)
        )
        return result.scalar_one_or_none()

    async def get_by_memory_id(
        self,
        memory_id: str,
        session: Optional[AsyncSession] = None,
    ) -> Phase2EmbeddingModel | None:
        """Retrieve phase2 embedding record by memory_id."""
        s = session or self.session
        if s is None:
            raise ValueError("AsyncSession required for database operation")
        result = await s.execute(
            select(Phase2EmbeddingModel)
            .options(selectinload(Phase2EmbeddingModel.phase1_output))
            .where(Phase2EmbeddingModel.memory_id == memory_id)
        )
        return result.scalar_one_or_none()

    async def search_by_vectors(
        self,
        query_vector: list[float],
        user_id: str = "U_DEVELOPMENT",
        content_weight: float = 0.5,
        context_weight: float = 0.5,
        top_k: int = 10,
        locker_session_valid: bool = False,
        group_id: Optional[uuid.UUID] = None,
        session: Optional[AsyncSession] = None,
    ) -> list[dict[str, Any]]:
        """Rank memories by weighted cosine similarity across dual vector columns.
        
        Retrieves matching records with canonical MemoryV1 JSONB payload from phase1_outputs.
        """
        s = session or self.session
        if s is None:
            raise ValueError("AsyncSession required for vector search")

        if not query_vector:
            raise ValueError("query_vector is required for vector search")

        total_weight = content_weight + context_weight
        if total_weight <= 0:
            c_weight, ctx_weight = 0.5, 0.5
        else:
            c_weight = content_weight / total_weight
            ctx_weight = context_weight / total_weight

        # Use Central ACL
        allowed_memories_stmt = AuthorizationService.get_accessible_memory_ids_query(
            user_id=user_id,
            locker_session_valid=locker_session_valid,
            group_id=group_id,
        )
        allowed_memories_res = await s.execute(allowed_memories_stmt)
        allowed_memory_ids = [row[0] for row in allowed_memories_res.all()]

        if not allowed_memory_ids:
            return []

        dialect_name = s.bind.dialect.name if s.bind else ""

        if dialect_name == "postgresql":
            # Native PostgreSQL pgvector cosine distance operator <=>
            # 1 - (vec1 <=> vec2) = cosine similarity
            query_vec_str = "[" + ",".join(str(float(x)) for x in query_vector) + "]"
            sql_query = text(
                """
                SELECT 
                    e.id AS embedding_id,
                    e.phase1_output_id,
                    e.memory_id,
                    e.embedding_model,
                    e.created_at,
                    p.payload AS memory_payload,
                    (1 - (e.content_vector <=> CAST(:qvec AS vector))) AS content_similarity,
                    (1 - (e.context_vector <=> CAST(:qvec AS vector))) AS context_similarity,
                    (
                        (:c_w * (1 - (e.content_vector <=> CAST(:qvec AS vector)))) +
                        (:ctx_w * (1 - (e.context_vector <=> CAST(:qvec AS vector))))
                    ) AS combined_similarity
                FROM phase2_embeddings e
                JOIN phase1_outputs p ON e.phase1_output_id = p.id
                WHERE (p.memory_id = ANY(:allowed_ids))
                  AND (p.privacy != 'PRIVATE_LOCKER' OR :locker_valid = true)
                ORDER BY combined_similarity DESC
                LIMIT :top_k
                """
            )
            result = await s.execute(
                sql_query,
                {
                    "qvec": query_vec_str,
                    "c_w": c_weight,
                    "ctx_w": ctx_weight,
                    "top_k": top_k,
                    "allowed_ids": list(allowed_memory_ids),
                    "locker_valid": locker_session_valid,
                },
            )
            rows = result.mappings().all()
            return [
                {
                    "embedding_id": row["embedding_id"],
                    "phase1_output_id": row["phase1_output_id"],
                    "memory_id": row["memory_id"],
                    "memory_payload": row["memory_payload"],
                    "memory_json": row["memory_payload"],
                    "content_similarity": float(row["content_similarity"]),
                    "context_similarity": float(row["context_similarity"]),
                    "content_score": float(row["content_similarity"]),
                    "context_score": float(row["context_similarity"]),
                    "similarity_score": float(row["combined_similarity"]),
                    "score": float(row["combined_similarity"]),
                }
                for row in rows
            ]

        # SQLite / In-Memory Python ranking fallback for testing
        result = await s.execute(
            select(Phase2EmbeddingModel).options(selectinload(Phase2EmbeddingModel.phase1_output))
        )
        embeddings = result.scalars().all()
        ranked = []

        for record in embeddings:
            if not record.phase1_output or not record.content_vector or not record.context_vector:
                continue

            # Filter by authorization using our fetched list
            if record.memory_id not in allowed_memory_ids:
                continue
            if record.phase1_output.privacy == "PRIVATE_LOCKER" and not locker_session_valid:
                continue

            content_sim = _cosine_similarity(query_vector, record.content_vector)
            context_sim = _cosine_similarity(query_vector, record.context_vector)
            combined_sim = (c_weight * content_sim) + (ctx_weight * context_sim)

            ranked.append(
                {
                    "embedding_id": record.id,
                    "phase1_output_id": record.phase1_output_id,
                    "memory_id": record.memory_id,
                    "memory_payload": record.phase1_output.payload,
                    "memory_json": record.phase1_output.payload,
                    "content_similarity": content_sim,
                    "context_similarity": context_sim,
                    "content_score": content_sim,
                    "context_score": context_sim,
                    "similarity_score": combined_sim,
                    "score": combined_sim,
                }
            )

        ranked.sort(key=lambda item: item["similarity_score"], reverse=True)
        return ranked[:top_k]

