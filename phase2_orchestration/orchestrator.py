"""
Phase 2 Unified Orchestrator:
Coordinates Embedding generation, Vector Storage, and Semantic Memory Retrieval.
Location dependencies have been completely removed.
"""
from typing import Dict, Any, Optional
from phase2_orchestration.storage.memory_repository import MemoryRepository
from phase2_orchestration.services.embedding_service import EmbeddingService
from phase2_orchestration.services.phase2_service import Phase2Service
from phase2_orchestration.services.search_service import MemorySearchService
from phase2_orchestration.services.llm_service import LLMService
from phase2_orchestration.schemas.phase2_schemas import Phase2ProcessResponse
from phase2_orchestration.schemas.search_schemas import MemorySearchResponse

class Phase2Orchestrator:
    def __init__(
        self,
        memory_repo: Optional[MemoryRepository] = None,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None,
    ):
        self.memory_repo = memory_repo or MemoryRepository()
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()

        # Ingestion & Embedding Pipeline
        self.phase2_service = Phase2Service(
            memory_repo=self.memory_repo,
            embedding_service=self.embedding_service
        )

        # Retrieval & Search Pipeline
        self.search_service = MemorySearchService(
            memory_repo=self.memory_repo,
            embedding_service=self.embedding_service,
            llm_service=self.llm_service
        )

    def ingest_memory(self, memory_payload: Dict[str, Any]) -> Phase2ProcessResponse:
        """
        Orchestration Pipeline 1:
        Takes Phase 1 MemoryV1 JSON, extracts text representations,
        generates dual 1024-dim BAAI/bge-m3 vectors, and persists to DB.
        """
        result = self.phase2_service.process_memory(memory_payload)
        return Phase2ProcessResponse(**result)

    def search_memories(
        self,
        query: str,
        user_id: str = "U_DEVELOPMENT",
        top_k: int = 5,
        content_weight: float = 0.5,
        context_weight: float = 0.5,
    ) -> MemorySearchResponse:
        """
        Orchestration Pipeline 2:
        Takes user query, generates query embedding vector,
        retrieves top matching memories via cosine similarity,
        and generates a grounded answer.
        """
        return self.search_service.search(
            query=query,
            top_k=top_k,
            user_id=user_id,
            content_weight=content_weight,
            context_weight=context_weight,
        )

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a stored memory by ID."""
        return self.phase2_service.get_memory(memory_id)

_orchestrator_instance = None

def get_orchestrator() -> Phase2Orchestrator:
    """Singleton getter for FastAPI dependency injection or app importing."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = Phase2Orchestrator()
    return _orchestrator_instance
