import json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import JSONB
from .db_session import Base

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False

# Use JSONB on PostgreSQL, with fallback to JSON on SQLite
JSONBType = JSON().with_variant(JSONB(), "postgresql")

class MemoryTable(Base):
    """
    Core storage model for Phase 2:
    - Stores full MemoryV1 payload in JSONB.
    - Stores dual 1024-dim BAAI/bge-m3 vectors (Content + Context) via pgvector.
    """
    __tablename__ = "memories"

    memory_id = Column(String(255), primary_key=True, index=True)
    schema_version = Column(String(50), default="1.0")
    
    # Complete MemoryV1 payload
    memory_json = Column(JSONBType, nullable=False)
    
    # Dual 1024-dim vectors
    if HAS_PGVECTOR:
        content_vector = Column(Vector(1024).with_variant(Text(), "sqlite"), nullable=True)
        context_vector = Column(Vector(1024).with_variant(Text(), "sqlite"), nullable=True)
    else:
        content_vector = Column(Text, nullable=True)
        context_vector = Column(Text, nullable=True)

    created_at = Column(String(255), default=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        json_payload = self.memory_json
        if isinstance(json_payload, str):
            try:
                json_payload = json.loads(json_payload)
            except Exception:
                pass

        return {
            "memory_id": self.memory_id,
            "schema_version": self.schema_version,
            "memory_json": json_payload,
            "created_at": self.created_at
        }
