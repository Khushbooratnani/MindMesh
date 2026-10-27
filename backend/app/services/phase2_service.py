import copy
import logging
from typing import Any, Optional
import uuid

from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.phase2_embedding_repo import Phase2EmbeddingRepository
from app.schemas.phase2_schemas import (
    Phase2EmbeddingMetadata,
    Phase2ProcessResponse,
    VectorPreview,
)
from app.services.embedding_service import (
    EmbeddingGenerationError,
    EmbeddingService,
)
from app.services.crypto_service import locker_crypto

logger = logging.getLogger(__name__)


class Phase2ExecutionError(Exception):
    """Raised when Phase 2 processing pipeline encounters a failure."""
    pass


class Phase2Service:
    """Orchestrates Phase 2 Dual-Vector Ingestion and Indexing.
    
    Database-First Pipeline:
      1. Reads canonical completed Phase 1 output record from PostgreSQL (phase1_outputs).
      2. Extracts canonical MemoryV1 JSONB payload.
      3. Constructs Content ("What happened?") and Context ("Entities, topics, mood, time") text.
      4. Generates dual 1024-dim BAAI/bge-m3 embeddings.
      5. Persists vector index record in PostgreSQL (phase2_embeddings) linked to phase1_output_id.
    """

    def __init__(
        self,
        phase1_output_repo: Optional[Phase1OutputRepository] = None,
        phase2_embedding_repo: Optional[Phase2EmbeddingRepository] = None,
        embedding_service: Optional[EmbeddingService] = None,
        session: Optional[Any] = None,
    ) -> None:
        if session is not None:
            self.phase1_output_repo = phase1_output_repo or Phase1OutputRepository(session)
            self.phase2_embedding_repo = phase2_embedding_repo or Phase2EmbeddingRepository(session)
        else:
            self.phase1_output_repo = phase1_output_repo
            self.phase2_embedding_repo = phase2_embedding_repo
        self.embedding_service = embedding_service or EmbeddingService()

    @staticmethod
    def _decrypt_transient_payload(payload: Any) -> Any:
        """
        Recursively decrypts enc:v1: ciphertext values inside a transient copy of the payload.
        Decryption occurs only in ephemeral memory strictly for vector generation.
        The original database record and memory payload are never modified.
        """
        if isinstance(payload, dict):
            return {k: Phase2Service._decrypt_transient_payload(v) for k, v in payload.items()}
        elif isinstance(payload, list):
            return [Phase2Service._decrypt_transient_payload(v) for v in payload]
        elif isinstance(payload, str) and payload.startswith("enc:v1:"):
            return locker_crypto.decrypt(payload)
        return payload

    async def process_phase1_output_id(
        self,
        phase1_output_id: uuid.UUID | str,
        session: Optional[Any] = None,
    ) -> Phase2ProcessResponse:
        """Processes exactly one phase1_outputs database record into Phase 2 vector embeddings."""
        phase1_repo = self.phase1_output_repo or (Phase1OutputRepository(session) if session else None)
        phase2_repo = self.phase2_embedding_repo or (Phase2EmbeddingRepository(session) if session else None)

        if phase1_repo is None or phase2_repo is None:
            raise Phase2ExecutionError("Database session or repositories must be provided to Phase2Service")

        target_id = (
            phase1_output_id if isinstance(phase1_output_id, uuid.UUID) else uuid.UUID(str(phase1_output_id))
        )

        # 1. Read canonical phase1_outputs from PostgreSQL
        logger.info("[Phase2] Reading canonical Phase 1 output from PostgreSQL: %s", target_id)
        phase1_record = await phase1_repo.get_by_id(target_id)
        if phase1_record is None:
            raise Phase2ExecutionError(f"No Phase 1 output record found in PostgreSQL with id: {target_id}")

        memory_payload = phase1_record.payload
        if not isinstance(memory_payload, dict):
            raise Phase2ExecutionError(f"Phase 1 record payload is invalid or empty for id: {target_id}")

        memory_id = phase1_record.memory_id or memory_payload.get("memory_id")
        if not memory_id:
            raise Phase2ExecutionError(f"Phase 1 record missing memory_id for id: {target_id}")

        schema_version = phase1_record.schema_version or memory_payload.get("schema_version", "1.0")

        # Determine if payload is private locker content
        is_private = (
            phase1_record.privacy in ("PRIVATE_LOCKER", "PRIVATE")
            or (isinstance(memory_payload.get("system"), dict) and memory_payload["system"].get("privacy") in ("PRIVATE_LOCKER", "PRIVATE"))
        )

        # 2. Ephemeral in-memory copy for vector representations (database record remains strictly encrypted)
        transient_payload = copy.deepcopy(memory_payload)
        content_dict = transient_payload.get("content", {})
        has_ciphertext = isinstance(content_dict, dict) and any(
            isinstance(v, str) and v.startswith("enc:v1:") for v in content_dict.values()
        )
        if is_private or has_ciphertext:
            transient_payload = self._decrypt_transient_payload(transient_payload)

        content_text = self.embedding_service.build_content_text(transient_payload)
        context_text = self.embedding_service.build_context_text(transient_payload)

        logger.info("[Phase2] Generating BAAI/bge-m3 embeddings for memory: %s", memory_id)

        # 3. Generate dual 1024-dim embeddings from the decrypted semantic text
        try:
            content_vec, context_vec = self.embedding_service.generate_content_and_context_vectors(transient_payload)
        except EmbeddingGenerationError as e:
            raise Phase2ExecutionError(f"Phase 2 embedding generation failed: {str(e)}") from e
        except Exception as e:
            raise Phase2ExecutionError(f"Unexpected error generating Phase 2 embeddings: {str(e)}") from e
        finally:
            del transient_payload

        # 4. Store vector record in PostgreSQL
        logger.info("[Phase2] Persisting dual vectors in PostgreSQL phase2_embeddings...")
        try:
            embedding_record = await phase2_repo.create_or_update(
                phase1_output_id=target_id,
                memory_id=memory_id,
                content_vector=content_vec,
                context_vector=context_vec,
                embedding_model=self.embedding_service.model_name,
            )
        except Exception as e:
            raise Phase2ExecutionError(f"Failed to persist Phase 2 embeddings to database: {str(e)}") from e

        logger.info(
            "[Phase2] Successfully stored Phase 2 embeddings (id=%s, memory_id=%s)",
            embedding_record.id,
            memory_id,
        )

        # For private locker memories, redact plaintext input_text from response preview to avoid leakage
        preview_content = "[REDACTED_PRIVATE_CONTENT]" if is_private else content_text
        preview_context = "[REDACTED_PRIVATE_CONTENT]" if is_private else context_text

        return Phase2ProcessResponse(
            embedding_id=embedding_record.id,
            phase1_output_id=target_id,
            memory_id=memory_id,
            schema_version=schema_version,
            status="processed",
            stored=True,
            embeddings=Phase2EmbeddingMetadata(
                model=self.embedding_service.model_name,
                content=VectorPreview(
                    created=True,
                    dimension=len(content_vec),
                    input_text=preview_content,
                    vector_preview=[round(x, 4) for x in content_vec[:5]],
                ),
                context=VectorPreview(
                    created=True,
                    dimension=len(context_vec),
                    input_text=preview_context,
                    vector_preview=[round(x, 4) for x in context_vec[:5]],
                ),
            ),
            created_at=embedding_record.created_at,
        )

    async def get_embedding_by_memory_id(self, memory_id: str):
        """Retrieve stored Phase 2 embedding record by memory_id."""
        return await self.phase2_embedding_repo.get_by_memory_id(memory_id)
