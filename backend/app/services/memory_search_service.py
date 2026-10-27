from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import MemorySearchError
from app.database.repositories.phase2_embedding_repo import Phase2EmbeddingRepository
from app.schemas.search_schemas import MemorySearchResponse, MemorySearchResult
from app.services.embedding_service import EmbeddingService, EmbeddingGenerationError
from app.services.llm_service import LLMService


class MemorySearchService:
    """
    Orchestrator for Semantic Retrieval across Phase 2 Dual-Vector Embeddings.
    Pipeline:
      1. Receives natural language search query.
      2. Generates 1024-dim query embedding using BAAI/bge-m3.
      3. Performs weighted dual-vector cosine similarity search in PostgreSQL (pgvector).
      4. Checks existing privacy permissions (owner / public / group / selected).
      5. Synthesizes grounded answer using LLM service.
      6. Returns ranked memory search results.
    """
    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None,
        embedding_repo: Optional[Phase2EmbeddingRepository] = None,
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()
        self.embedding_repo = embedding_repo or Phase2EmbeddingRepository()

    def _can_read(self, memory_json: dict[str, Any], user_id: str) -> bool:
        """Enforces existing development privacy rules without altering Phase 1 behavior."""
        if not memory_json:
            return False
        system = memory_json.get("system", {})
        owner_id = system.get("owner_id")
        privacy = (system.get("privacy") or "ONLY_ME").upper()
        allowed_users = system.get("allowed_users", [])

        if not user_id or user_id == "U_DEVELOPMENT":
            return True
        if owner_id == user_id:
            return True
        if privacy in ("GROUP", "PUBLIC"):
            return True
        if privacy in ("SELECTED", "CUSTOM") and user_id in allowed_users:
            return True
        return False

    async def search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = "U_DEVELOPMENT",
        content_weight: Optional[float] = None,
        context_weight: Optional[float] = None,
    ) -> MemorySearchResponse:
        cw = content_weight if content_weight is not None else settings.default_content_weight
        ctx_w = context_weight if context_weight is not None else settings.default_context_weight

        # 1. Generate query vector (1024-dim)
        try:
            query_vector = self.embedding_service.generate_embedding(query)
        except EmbeddingGenerationError as exc:
            raise MemorySearchError(f"Query embedding generation failed: {str(exc)}") from exc

        # 2. Vector search in PostgreSQL pgvector / repository
        try:
            candidates = await self.embedding_repo.search_by_vectors(
                session=session,
                query_vector=query_vector,
                content_weight=cw,
                context_weight=ctx_w,
                top_k=top_k * 2,
            )
        except Exception as exc:
            raise MemorySearchError(f"Vector search failed: {str(exc)}") from exc

        # 3. Privacy filter & Relevance Gate
        effective_user_id = user_id or "U_DEVELOPMENT"
        accessible = [
            cand for cand in candidates
            if self._can_read(cand.get("memory_json", {}), effective_user_id)
        ]

        # Deterministic relevance threshold gate
        min_threshold = (
            -1.0
            if (self.embedding_service.force_mock or settings.embedding_force_mock)
            else settings.search_min_relevance_score
        )
        relevant = [
            cand for cand in accessible
            if cand.get("similarity_score", 0.0) >= min_threshold
        ]

        # If no candidates meet the relevance threshold, do NOT call LLM
        if not relevant:
            return MemorySearchResponse(
                query=query,
                answer=f'I couldn\'t find any stored memory related to "{query}".',
                grounded=False,
                results=[],
                total_results=0,
            )

        selected = relevant[:top_k]
        memories = [cand["memory_json"] for cand in selected if "memory_json" in cand]

        # 4. Generate grounded natural language answer strictly from relevant memories
        answer = self.llm_service.answer_from_memories(
            query=query,
            memories=memories,
        )

        # 5. Format structured results
        results = []
        for cand in selected:
            mem = dict(cand.get("memory_json", {}))
            system_meta = mem.get("system", {})
            content_meta = mem.get("content", {})
            media_meta = dict(mem.get("media", {})) if mem.get("media") else {}

            storage_key = (
                media_meta.get("storage_key")
                or system_meta.get("media_reference")
                or (media_meta.get("relative_path") if media_meta.get("relative_path") else None)
            )

            if storage_key:
                if not media_meta.get("storage_key"):
                    media_meta["storage_key"] = storage_key
                if not media_meta.get("url"):
                    media_meta["url"] = f"http://10.9.11.238:8001/api/v1/media/{storage_key}"
                mem["media"] = media_meta

            results.append(
                MemorySearchResult(
                    memory_id=cand["memory_id"],
                    similarity_score=round(cand["similarity_score"], 4),
                    score=round(cand["similarity_score"], 4),
                    source_modality=system_meta.get("media_type", "text").upper(),
                    user_context=mem.get("user_context"),
                    clean_text=content_meta.get("clean_text") or content_meta.get("raw_text"),
                    media=media_meta if media_meta else None,
                    content_score=round(cand.get("content_score", 0.0), 4) if cand.get("content_score") is not None else None,
                    context_score=round(cand.get("context_score", 0.0), 4) if cand.get("context_score") is not None else None,
                    summary=content_meta.get("summary") or content_meta.get("clean_text"),
                    entities=mem.get("entities"),
                    semantics=mem.get("semantics"),
                    memory=mem,
                )
            )

        return MemorySearchResponse(
            query=query,
            answer=answer,
            grounded=True,
            results=results,
            total_results=len(results),
        )
