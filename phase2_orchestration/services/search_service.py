from typing import Any, Optional, List, Dict
from phase2_orchestration.config import settings
from phase2_orchestration.schemas.search_schemas import MemorySearchResponse, MemorySearchResult
from phase2_orchestration.storage.memory_repository import MemoryRepository, MemoryRepositoryError
from .embedding_service import EmbeddingService, EmbeddingGenerationError
from .llm_service import LLMService

class MemorySearchError(Exception):
    """Raised when semantic memory search fails."""
    pass

class MemorySearchService:
    """
    Orchestrator for Semantic Retrieval across Phase 2 Vector Stores.
    Pipeline:
      1. Receives natural language search query.
      2. Generates 1024-dim query embedding using BAAI/bge-m3.
      3. Performs weighted dual-vector cosine similarity search in database.
      4. Applies privacy/access permissions check.
      5. Generates grounded answer using LLM service.
      6. Returns ranked memory results.
    """
    def __init__(
        self,
        memory_repo: Optional[MemoryRepository] = None,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None,
    ):
        self.memory_repo = memory_repo or MemoryRepository()
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()

    def _can_read(self, memory_json: Dict[str, Any], user_id: str) -> bool:
        """Enforces privacy rules: Owner, Public/Group, or Allowed Users."""
        if not memory_json:
            return False
        system = memory_json.get("system", {})
        owner_id = system.get("owner_id")
        privacy = system.get("privacy", "ONLY_ME")
        allowed_users = system.get("allowed_users", [])

        if owner_id == user_id:
            return True
        if privacy in ("GROUP", "PUBLIC", "group", "public"):
            return True
        if privacy in ("SELECTED", "selected") and user_id in allowed_users:
            return True
        return False

    def search(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = "U_DEVELOPMENT",
        content_weight: Optional[float] = None,
        context_weight: Optional[float] = None,
    ) -> MemorySearchResponse:
        cw = content_weight if content_weight is not None else settings.DEFAULT_CONTENT_WEIGHT
        ctx_w = context_weight if context_weight is not None else settings.DEFAULT_CONTEXT_WEIGHT

        # Step 1: Generate Query Vector
        try:
            query_vector = self.embedding_service.generate_embedding(query)
        except EmbeddingGenerationError as exc:
            raise MemorySearchError(f"Query embedding generation failed: {str(exc)}") from exc

        # Step 2: Vector Search in PostgreSQL / pgvector
        try:
            candidates = self.memory_repo.search_by_vectors(
                query_vector=query_vector,
                content_weight=cw,
                context_weight=ctx_w
            )
        except MemoryRepositoryError as exc:
            raise MemorySearchError(f"Vector search failed: {str(exc)}") from exc

        # Step 3: Privacy and Access Filtering
        accessible = [
            candidate for candidate in candidates
            if self._can_read(candidate["memory_json"], user_id)
        ]

        selected = accessible[:top_k]
        memories = [candidate["memory_json"] for candidate in selected]

        # Step 4: Generate Grounded Natural Language Answer
        answer = self.llm_service.answer_from_memories(
            query=query,
            memories=memories
        )

        # Step 5: Format structured results
        results = [
            MemorySearchResult(
                memory_id=candidate["memory_id"],
                similarity_score=round(candidate["similarity_score"], 4),
                score=round(candidate["similarity_score"], 4),
                content_score=round(candidate.get("content_score", 0.0), 4) if candidate.get("content_score") is not None else None,
                context_score=round(candidate.get("context_score", 0.0), 4) if candidate.get("context_score") is not None else None,
                summary=candidate["memory_json"].get("content", {}).get("summary") or candidate["memory_json"].get("content", {}).get("clean_text"),
                entities=candidate["memory_json"].get("entities"),
                semantics=candidate["memory_json"].get("semantics"),
                memory=candidate["memory_json"]
            )
            for candidate in selected
        ]

        return MemorySearchResponse(
            query=query,
            answer=answer,
            results=results,
            total_results=len(results)
        )
