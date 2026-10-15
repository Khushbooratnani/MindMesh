from typing import Optional, Dict, Any
from phase2_orchestration.storage.memory_repository import MemoryRepository, MemoryRepositoryError
from .embedding_service import EmbeddingService, EmbeddingGenerationError

class Phase2ExecutionError(Exception):
    """Raised when Phase 2 processing pipeline encounters a failure."""
    pass

class Phase2Service:
    """
    Orchestrator for Ingesting and Vectorizing Phase 1 Memory payloads.
    Pipeline:
      1. Receives MemoryV1 JSON.
      2. Constructs Content and Context text representations.
      3. Generates dual 1024-dim BAAI/bge-m3 embeddings.
      4. Persists JSONB and vector columns to PostgreSQL (or SQLite).
    """
    def __init__(
        self,
        memory_repo: Optional[MemoryRepository] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self.memory_repo = memory_repo or MemoryRepository()
        self.embedding_service = embedding_service or EmbeddingService()

    def process_memory(self, memory: Any) -> Dict[str, Any]:
        if isinstance(memory, dict):
            memory_dict = memory
        elif hasattr(memory, "model_dump"):
            memory_dict = memory.model_dump()
        elif hasattr(memory, "dict"):
            memory_dict = memory.dict()
        else:
            try:
                memory_dict = dict(memory)
            except Exception:
                raise Phase2ExecutionError("Invalid MemoryV1 JSON input payload")

        memory_id = memory_dict.get("memory_id")
        if not memory_id:
            raise Phase2ExecutionError("MemoryV1 JSON payload is missing required field: memory_id")

        schema_version = memory_dict.get("schema_version", "1.0")

        # 1. Text representations
        content_text = self.embedding_service.build_content_text(memory_dict)
        context_text = self.embedding_service.build_context_text(memory_dict)

        # 2. Dual embeddings (Content + Context)
        try:
            content_vec, context_vec = self.embedding_service.generate_content_and_context_vectors(memory_dict)
        except EmbeddingGenerationError as e:
            raise Phase2ExecutionError(f"Embedding generation failed: {str(e)}")
        except Exception as e:
            raise Phase2ExecutionError(f"Unexpected error during embedding generation: {str(e)}")

        # 3. Store in Database
        try:
            self.memory_repo.upsert_memory(
                memory_id=memory_id,
                schema_version=schema_version,
                memory_json=memory_dict,
                content_vector=content_vec,
                context_vector=context_vec
            )
        except MemoryRepositoryError as e:
            raise Phase2ExecutionError(f"Database storage failed: {str(e)}")

        return {
            "memory_id": memory_id,
            "schema_version": schema_version,
            "status": "processed",
            "stored": True,
            "embeddings": {
                "model": "BAAI/bge-m3",
                "content": {
                    "created": True,
                    "dimension": len(content_vec),
                    "input_text": content_text,
                    "vector_preview": [round(x, 4) for x in content_vec[:5]],
                    "vector_full": [round(x, 6) for x in content_vec]
                },
                "context": {
                    "created": True,
                    "dimension": len(context_vec),
                    "input_text": context_text,
                    "vector_preview": [round(x, 4) for x in context_vec[:5]],
                    "vector_full": [round(x, 6) for x in context_vec]
                }
            },
            "stored_memory": memory_dict
        }

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        return self.memory_repo.get_memory_by_id(memory_id)
