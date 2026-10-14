import json
import math
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from .db_session import SessionLocal, init_db
from .db_models import MemoryTable, HAS_PGVECTOR

class MemoryRepositoryError(Exception):
    """Raised when memory database storage operations fail."""
    pass

class MemoryRepository:
    def __init__(self, session_factory=None):
        try:
            init_db()
        except Exception:
            pass
        self.session_factory = session_factory or SessionLocal

    def upsert_memory(
        self,
        memory_id: str,
        schema_version: str,
        memory_json: Dict[str, Any],
        content_vector: List[float],
        context_vector: List[float]
    ) -> MemoryTable:
        if not memory_id:
            raise MemoryRepositoryError("memory_id is required for database storage")

        session: Session = self.session_factory()
        try:
            dialect_name = session.bind.dialect.name if session.bind else ""
            if dialect_name == "sqlite" or not HAS_PGVECTOR:
                content_vec_data = json.dumps(content_vector) if isinstance(content_vector, list) else content_vector
                context_vec_data = json.dumps(context_vector) if isinstance(context_vector, list) else context_vector
            else:
                content_vec_data = content_vector
                context_vec_data = context_vector

            existing = session.query(MemoryTable).filter(MemoryTable.memory_id == memory_id).first()

            if existing:
                existing.schema_version = schema_version
                existing.memory_json = memory_json
                existing.content_vector = content_vec_data
                existing.context_vector = context_vec_data
                record = existing
            else:
                record = MemoryTable(
                    memory_id=memory_id,
                    schema_version=schema_version,
                    memory_json=memory_json,
                    content_vector=content_vec_data,
                    context_vector=context_vec_data
                )
                session.add(record)

            session.commit()
            session.refresh(record)
            return record
        except Exception as e:
            session.rollback()
            raise MemoryRepositoryError(f"Failed to upsert memory {memory_id}: {str(e)}")
        finally:
            session.close()

    def get_memory_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        session: Session = self.session_factory()
        try:
            record = session.query(MemoryTable).filter(MemoryTable.memory_id == memory_id).first()
            return record.to_dict() if record else None
        except Exception as e:
            raise MemoryRepositoryError(f"Failed to query memory {memory_id}: {str(e)}")
        finally:
            session.close()

    def search_by_vectors(
        self,
        query_vector: List[float],
        content_weight: float = 0.5,
        context_weight: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Rank memories by the weighted cosine similarity of both vectors:
        content_vector ("What happened?") and context_vector ("Entities, topics, context").
        """
        if not query_vector:
            raise MemoryRepositoryError("query_vector is required for semantic search")

        total_weight = content_weight + context_weight
        if total_weight <= 0:
            c_weight, ctx_weight = 0.5, 0.5
        else:
            c_weight = content_weight / total_weight
            ctx_weight = context_weight / total_weight

        session: Session = self.session_factory()
        try:
            dialect_name = session.bind.dialect.name if session.bind else ""
            if dialect_name == "postgresql" and HAS_PGVECTOR:
                content_distance = MemoryTable.content_vector.cosine_distance(query_vector)
                context_distance = MemoryTable.context_vector.cosine_distance(query_vector)
                weighted_distance = (c_weight * content_distance) + (ctx_weight * context_distance)
                
                rows = (
                    session.query(
                        MemoryTable,
                        (1 - weighted_distance).label("similarity_score"),
                        (1 - content_distance).label("content_score"),
                        (1 - context_distance).label("context_score")
                    )
                    .filter(MemoryTable.content_vector.isnot(None), MemoryTable.context_vector.isnot(None))
                    .order_by(weighted_distance.asc())
                    .all()
                )
                return [
                    {
                        "memory_id": record.memory_id,
                        "memory_json": record.to_dict()["memory_json"],
                        "similarity_score": float(sim_score),
                        "score": float(sim_score),
                        "content_score": float(c_score),
                        "context_score": float(ctx_score)
                    }
                    for record, sim_score, c_score, ctx_score in rows
                ]

            # SQLite local fallback with native exact cosine similarity
            ranked = []
            for record in session.query(MemoryTable).all():
                content = self._deserialize_vector(record.content_vector)
                context = self._deserialize_vector(record.context_vector)
                if not content or not context:
                    continue
                content_sim = self._cosine_similarity(query_vector, content)
                context_sim = self._cosine_similarity(query_vector, context)
                sim_score = (c_weight * content_sim) + (ctx_weight * context_sim)
                ranked.append({
                    "memory_id": record.memory_id,
                    "memory_json": record.to_dict()["memory_json"],
                    "similarity_score": sim_score,
                    "score": sim_score,
                    "content_score": content_sim,
                    "context_score": context_sim
                })
            return sorted(ranked, key=lambda item: item["similarity_score"], reverse=True)
        except Exception as exc:
            raise MemoryRepositoryError(f"Failed to run vector search: {str(exc)}") from exc
        finally:
            session.close()

    @staticmethod
    def _deserialize_vector(value: Any) -> List[float]:
        if isinstance(value, str):
            return json.loads(value)
        return list(value) if value is not None else []

    @staticmethod
    def _cosine_similarity(left: List[float], right: List[float]) -> float:
        if len(left) != len(right):
            raise MemoryRepositoryError("Vector dimension mismatch")
        denominator = math.sqrt(sum(v * v for v in left)) * math.sqrt(sum(v * v for v in right))
        return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0
