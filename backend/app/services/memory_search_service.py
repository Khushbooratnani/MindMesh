from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import MemorySearchError
from app.database.repositories.phase2_embedding_repo import Phase2EmbeddingRepository
from app.schemas.search_schemas import MemorySearchResponse, MemorySearchResult
from app.services.embedding_service import EmbeddingService, EmbeddingGenerationError
from app.services.llm_service import LLMService
from app.services.crypto_service import locker_crypto


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

    def _can_read(self, memory_json: dict[str, Any], user_id: str, locker_session_valid: bool = False) -> bool:
        """Enforces privacy rules for memories (default-deny)."""
        if not memory_json:
            return False
        system = memory_json.get("system", {})
        owner_id = system.get("owner_id")
        privacy = (system.get("privacy") or "ONLY_ME").upper()
        allowed_users = system.get("allowed_users", [])

        # 1. Private Locker isolation firewall
        if privacy == "PRIVATE_LOCKER":
            return owner_id == user_id and locker_session_valid

        # 2. Personal ownership
        if owner_id == user_id:
            return True

        # 3. Explicitly public memories
        if privacy == "PUBLIC":
            return True

        # 4. Explicitly allowed users in payload
        if privacy in ("SELECTED", "CUSTOM", "SHARED") and user_id in allowed_users:
            return True

        # 5. Development mode fallback (non-private memories only)
        if not user_id or user_id == "U_DEVELOPMENT":
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
        locker_session_valid: bool = False,
        group_id: Optional[Any] = None,
    ) -> MemorySearchResponse:
        cw = content_weight if content_weight is not None else settings.default_content_weight
        ctx_w = context_weight if context_weight is not None else settings.default_context_weight
        effective_user_id = user_id or "U_DEVELOPMENT"

        # If searching within a specific group context, validate caller membership first
        target_group_uuid: Optional[uuid.UUID] = None
        if group_id:
            try:
                target_group_uuid = group_id if isinstance(group_id, uuid.UUID) else uuid.UUID(str(group_id))
            except Exception:
                target_group_uuid = None

            if target_group_uuid:
                from app.services.group_service import GroupService
                try:
                    await GroupService.verify_membership(
                        session=session,
                        group_id=target_group_uuid,
                        user_id=effective_user_id,
                    )
                except Exception:
                    # User is not an active member or group doesn't exist -> Return zero results (deny safely)
                    return MemorySearchResponse(
                        query=query,
                        answer=f'I couldn\'t find any stored memory in this group related to "{query}".',
                        grounded=False,
                        results=[],
                        total_results=0,
                    )

        # 1. Generate query vector (1024-dim)
        try:
            query_vector = self.embedding_service.generate_embedding(query)
        except EmbeddingGenerationError as exc:
            raise MemorySearchError(f"Query embedding generation failed: {str(exc)}") from exc

        # 2. Vector search in PostgreSQL pgvector / repository with database-level ACL pre-filtering
        try:
            candidates = await self.embedding_repo.search_by_vectors(
                session=session,
                query_vector=query_vector,
                user_id=effective_user_id,
                content_weight=cw,
                context_weight=ctx_w,
                top_k=top_k * 2,
                locker_session_valid=locker_session_valid,
                group_id=target_group_uuid,
            )
        except Exception as exc:
            raise MemorySearchError(f"Vector search failed: {str(exc)}") from exc

        # 3. Defense-in-depth post-filter & Relevance Gate
        accessible = []
        for cand in candidates:
            m_json = cand.get("memory_json", {})
            sys_meta = m_json.get("system", {})
            priv = (sys_meta.get("privacy") or "ONLY_ME").upper()
            # Enforce Private Locker isolation firewall
            if priv == "PRIVATE_LOCKER" and not (sys_meta.get("owner_id") == effective_user_id and locker_session_valid):
                continue
            accessible.append(cand)

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
        memories = []
        for cand in selected:
            if "memory_json" in cand:
                m_copy = dict(cand["memory_json"])
                c_copy = dict(m_copy.get("content", {}))
                if c_copy.get("clean_text"):
                    c_copy["clean_text"] = locker_crypto.decrypt(c_copy["clean_text"])
                if c_copy.get("raw_text"):
                    c_copy["raw_text"] = locker_crypto.decrypt(c_copy["raw_text"])
                if c_copy.get("summary"):
                    c_copy["summary"] = locker_crypto.decrypt(c_copy["summary"])
                m_copy["content"] = c_copy
                memories.append(m_copy)

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
                    media_meta["url"] = f"/api/v1/media/{storage_key}"
                mem["media"] = media_meta

            raw_clean_text = content_meta.get("clean_text") or content_meta.get("raw_text")
            decrypted_clean_text = locker_crypto.decrypt(raw_clean_text) if raw_clean_text else None
            raw_summary = content_meta.get("summary") or content_meta.get("clean_text")
            decrypted_summary = locker_crypto.decrypt(raw_summary) if raw_summary else None

            results.append(
                MemorySearchResult(
                    memory_id=cand["memory_id"],
                    similarity_score=round(cand["similarity_score"], 4),
                    score=round(cand["similarity_score"], 4),
                    source_modality=system_meta.get("media_type", "text").upper(),
                    user_context=mem.get("user_context"),
                    clean_text=decrypted_clean_text,
                    media=media_meta if media_meta else None,
                    content_score=round(cand.get("content_score", 0.0), 4) if cand.get("content_score") is not None else None,
                    context_score=round(cand.get("context_score", 0.0), 4) if cand.get("context_score") is not None else None,
                    summary=decrypted_summary,
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
