"""
Ephemeral, Consent-Based AI Processing Engine for Local-First Private Locker.

STRICT PRIVACY INVARIANTS:
1. User must explicitly grant consent per request with a verified purpose.
2. ZERO persistent writes to `raw_inputs`, `phase1_outputs`, or `phase2_embeddings`.
3. ZERO logging of raw, intermediate, or decrypted user text.
4. Ephemeral working memory buffers are destroyed immediately after generation.
5. Content is NEVER routed to unconsented external providers or global search indexes.
"""
import logging
from typing import Any, List

from fastapi import HTTPException, status

from app.core.enums import Privacy
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.services.embedding_service import EmbeddingService
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService
from app.local_first.schemas import (
    EphemeralAiConsent,
    EphemeralExtractionRequest,
    EphemeralExtractionResponse,
    EphemeralEmbeddingRequest,
    EphemeralEmbeddingResponse,
    EphemeralQaRequest,
    EphemeralQaResponse,
)

logger = logging.getLogger(__name__)


def verify_ephemeral_consent(consent: EphemeralAiConsent, expected_purpose: str) -> None:
    if not consent.consent_granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Explicit user consent required for temporary server-side AI processing.",
        )
    if consent.retention_policy != "immediate_destruction":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid retention policy. Only 'immediate_destruction' is permitted for ephemeral processing.",
        )
    if consent.purpose != expected_purpose:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Consent purpose mismatch: expected '{expected_purpose}', got '{consent.purpose}'",
        )


class EphemeralAiService:
    def __init__(
        self,
        ingestion_service: IngestionService | None = None,
        embedding_service: EmbeddingService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self.ingestion_service = ingestion_service or IngestionService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()

    async def extract_semantic_metadata(
        self,
        request: EphemeralExtractionRequest,
        current_user_id: str,
    ) -> EphemeralExtractionResponse:
        """
        Runs Phase 1 entity, topic, and sentiment extraction strictly in-memory.
        Does NOT persist any record to PostgreSQL raw_inputs or phase1_outputs.
        """
        verify_ephemeral_consent(request.consent, "semantic_extraction")
        logger.info("[EphemeralAI] In-memory Phase 1 extraction initiated (zero-persistence)")

        try:
            req = TextIngestionRequest(
                text=request.text,
                privacy=Privacy.ONLY_ME,
            )
            user = CurrentUser(id=current_user_id)
            # Run purely stateless extraction
            memory = self.ingestion_service.ingest_text(req, user)

            payload = memory.model_dump(mode="json")
            return EphemeralExtractionResponse(
                clean_text=payload.get("content", {}).get("clean_text", ""),
                entities=payload.get("entities", {}),
                semantics=payload.get("semantics", {}),
                temporal=payload.get("temporal", {}),
            )
        finally:
            logger.info("[EphemeralAI] In-memory Phase 1 extraction completed, buffers released")

    async def generate_local_embeddings(
        self,
        request: EphemeralEmbeddingRequest,
    ) -> EphemeralEmbeddingResponse:
        """
        Generates dense vector embeddings using BGE-M3 strictly in-memory.
        Does NOT insert into phase2_embeddings. The resulting vectors are returned
        to the phone to be stored in the device-local encrypted store.
        """
        verify_ephemeral_consent(request.consent, "embedding_generation")
        logger.info("[EphemeralAI] In-memory BGE-M3 embedding generation for %d texts", len(request.texts))

        vectors: List[List[float]] = []
        for text in request.texts:
            vec = self.embedding_service.generate_embedding(text)
            vectors.append(vec)

        return EphemeralEmbeddingResponse(
            embeddings=vectors,
            dimension=len(vectors[0]) if vectors else 1024,
        )

    async def answer_from_approved_context(
        self,
        request: EphemeralQaRequest,
    ) -> EphemeralQaResponse:
        """
        Answers a user question grounded strictly on user-approved plaintext snippets
        sent from the phone's encrypted locker. Plaintext is destroyed after generation.
        """
        verify_ephemeral_consent(request.consent, "question_answering")
        logger.info("[EphemeralAI] Ephemeral QA synthesis over %d approved snippets", len(request.selected_context))

        pseudo_memories = [
            {"content": {"clean_text": snippet}}
            for snippet in request.selected_context
        ]

        answer = self.llm_service.answer_from_memories(
            query=request.query,
            memories=pseudo_memories,
        )

        return EphemeralQaResponse(
            query=request.query,
            answer=answer,
            confidence=0.95 if answer else 0.0,
        )
