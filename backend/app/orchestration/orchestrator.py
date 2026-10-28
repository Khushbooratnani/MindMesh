from dataclasses import dataclass
import logging
import uuid
from typing import Any, Callable, Coroutine

from app.core.enums import MediaType, Privacy
from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.raw_input import RawInputModel
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.raw_input_repo import RawInputRepository
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.schemas.memory_output import MediaReference, MemoryV1
from app.services.ingestion_service import IngestionService
from app.services.phase2_service import Phase2Service
from app.storage.file_storage import FileStorage
from app.services.crypto_service import locker_crypto

logger = logging.getLogger(__name__)

PostPhase1Hook = Callable[[MemoryV1, RawInputModel, Phase1OutputModel], Coroutine[Any, Any, None]]


@dataclass
class OrchestratedIngestionResult:
    """Encapsulates memory output along with actual persistent database row IDs."""
    memory: MemoryV1
    raw_input_id: uuid.UUID
    phase1_output_id: uuid.UUID


class MindMeshOrchestrator:
    """Reusable MindMesh Orchestration and Persistence Coordinator.
    
    Coordinates the multi-phase pipeline starting from raw input preservation,
    durable media file storage, delegating to Phase 1 ingestion, persisting
    Phase 1 MemoryV1 JSONB, triggering Phase 2 dual-vector embeddings, and managing failure recovery.
    """

    def __init__(
        self,
        raw_input_repo: RawInputRepository,
        phase1_output_repo: Phase1OutputRepository,
        ingestion_service: IngestionService | None = None,
        file_storage: FileStorage | None = None,
        phase2_service: Phase2Service | None = None,
    ) -> None:
        self.raw_input_repo = raw_input_repo
        self.phase1_output_repo = phase1_output_repo
        self.ingestion_service = ingestion_service or IngestionService()
        self.file_storage = file_storage or FileStorage()
        self.phase2_service = phase2_service
        self._post_phase1_hooks: list[PostPhase1Hook] = []
        self.last_raw_input_id: uuid.UUID | None = None
        self.last_phase1_output_id: uuid.UUID | None = None

    def register_post_phase1_hook(self, hook: PostPhase1Hook) -> None:
        """Register a downstream hook for future phases (e.g. Phase 2 embeddings)."""
        self._post_phase1_hooks.append(hook)

    async def process_text_ingestion_result(
        self,
        request: TextIngestionRequest,
        current_user: CurrentUser,
        raw_text_verbatim: str | None = None,
        input_id: uuid.UUID | None = None,
    ) -> OrchestratedIngestionResult:
        """Orchestrate text ingestion with DB-first boundary between ingestion and Phase 1."""
        logger.info("[MindMesh] Request received")
        logger.info("[Storage] Saving raw input...")

        # 1. Capture exact original user text verbatim
        verbatim_text = raw_text_verbatim if raw_text_verbatim is not None else request.text
        structured_payload = request.model_dump(mode="json")

        # 2. Persist raw input to PostgreSQL before any processing
        privacy_val = request.privacy.value if hasattr(request.privacy, "value") else str(request.privacy)
        is_private_locker = (privacy_val == Privacy.PRIVATE_LOCKER.value)
        payload_to_store = locker_crypto.encrypt(verbatim_text) if is_private_locker else verbatim_text

        raw_input = await self.raw_input_repo.create(
            media_type=MediaType.TEXT.value,
            raw_payload=payload_to_store,
            structured_payload=structured_payload,
            client_id=current_user.id,
            owner_id=current_user.id,
            privacy=privacy_val,
            group_id=request.group_id,
            status="received",
            input_id=input_id,
        )
        self.last_raw_input_id = raw_input.id
        logger.info("[Storage] Raw input saved: %s", raw_input.id)

        try:
            # 3. Read that same raw input back from PostgreSQL (DB boundary)
            logger.info("[Storage] Reading raw input from PostgreSQL...")
            persisted_raw_input = await self.raw_input_repo.get_by_id(raw_input.id)
            if persisted_raw_input is None:
                raise RuntimeError(f"Failed to retrieve persisted raw input with id {raw_input.id}")
            logger.info("[Storage] Raw input retrieved: %s", persisted_raw_input.id)

            # 4. Construct Phase 1 input derived strictly from the persisted database record
            structured = persisted_raw_input.structured_payload or {}
            privacy_val = structured.get("privacy", Privacy.ONLY_ME.value)
            if isinstance(privacy_val, str):
                try:
                    privacy_enum = Privacy(privacy_val)
                except ValueError:
                    privacy_enum = Privacy.ONLY_ME
            else:
                privacy_enum = privacy_val

            # Decrypt in-memory for Phase 1 and Phase 2 processing
            decrypted_text = locker_crypto.decrypt(persisted_raw_input.raw_payload)

            phase1_request = TextIngestionRequest(
                text=decrypted_text,
                group_id=persisted_raw_input.group_id,
                privacy=privacy_enum,
                allowed_users=structured.get("allowed_users", []),
            )
            phase1_user = CurrentUser(id=persisted_raw_input.client_id)

            # 5. Mark processing and execute Phase 1 ingestion service
            await self.raw_input_repo.update_status(persisted_raw_input.id, status="processing")
            logger.info("[Phase 1] Starting text ingestion...")
            memory = self.ingestion_service.ingest_text(phase1_request, phase1_user)
            logger.info("[Phase 1] MemoryV1 generated: %s", memory.memory_id)
            logger.info("[Phase 1] Validation completed")

            # 6. Persist complete MemoryV1 JSONB in phase1_outputs table
            logger.info("[Storage] Saving Phase 1 output...")
            output_payload = memory.model_dump(mode="json")
            if is_private_locker and isinstance(output_payload.get("content"), dict):
                c_dict = dict(output_payload["content"])
                if c_dict.get("clean_text"):
                    c_dict["clean_text"] = locker_crypto.encrypt(c_dict["clean_text"])
                if c_dict.get("raw_text"):
                    c_dict["raw_text"] = locker_crypto.encrypt(c_dict["raw_text"])
                if c_dict.get("summary"):
                    c_dict["summary"] = locker_crypto.encrypt(c_dict["summary"])
                output_payload["content"] = c_dict

            phase1_output = await self.phase1_output_repo.create(
                raw_input_id=persisted_raw_input.id,
                memory_id=memory.memory_id,
                schema_version=memory.schema_version,
                payload=output_payload,
                owner_id=persisted_raw_input.owner_id,
                privacy=persisted_raw_input.privacy,
                processing_status=memory.processing.status,
                extractor_model=memory.processing.llm_model,
            )
            self.last_phase1_output_id = phase1_output.id
            logger.info("[Storage] Phase 1 output saved: %s", phase1_output.id)

            # 7. Mark raw input as completed
            await self.raw_input_repo.mark_completed(persisted_raw_input.id)
            logger.info("[Storage] Raw input marked completed")
            logger.info("[MindMesh] Processing completed successfully")

            # 8. Phase 2 Dual-Vector Embeddings
            if self.phase2_service is not None:
                try:
                    await self.phase2_service.process_phase1_output_id(phase1_output.id)
                    logger.info("[Phase 2] Dual-vector embeddings generated and stored for: %s", phase1_output.id)
                except Exception as p2_exc:
                    logger.warning("[Phase 2] Embedding generation failed for %s: %s", phase1_output.id, p2_exc)

            # 9. Phase 3 — Knowledge Graph sync (fail-soft, P0 PRIVATE_LOCKER blocked)
            if not is_private_locker:
                try:
                    from app.services.graph_builder import GraphBuilder
                    from app.database.neo4j import Neo4jRepository
                    graph_doc = GraphBuilder().build_graph_document(
                        memory=memory,
                        db_record={
                            "memory_id": str(phase1_output.id),
                            "owner_id": persisted_raw_input.owner_id,
                        },
                    )
                    neo4j_repo = Neo4jRepository()
                    if neo4j_repo.is_available():
                        neo4j_repo.upsert_graph_document(graph_doc)
                        logger.info("[Phase 3] Knowledge graph synced for memory: %s", memory.memory_id)
                    else:
                        logger.debug("[Phase 3] Neo4j unavailable — skipping graph sync for %s", memory.memory_id)
                except Exception as graph_exc:
                    logger.warning("[Phase 3] Graph sync failed for %s: %s", memory.memory_id, graph_exc)
            else:
                logger.debug("[Phase 3] PRIVATE_LOCKER memory — skipping graph sync (P0 isolation)")

            # 10. Phase 3 — Location geocoding & memory_locations linking (fail-soft, P0 blocked)
            if not is_private_locker:
                try:
                    from app.services.geocoding_service import LocationIQGeocoder
                    geocoder = LocationIQGeocoder()
                    places = _extract_places_from_memory(memory)
                    if places:
                        from app.database.connection.session import get_session_maker
                        session_factory = get_session_maker()
                        async with session_factory() as db_session:
                            for place_name in places:
                                geo_result = await geocoder.geocode(place_name)
                                if geo_result:
                                    await _upsert_memory_location(
                                        session=db_session,
                                        memory_id=memory.memory_id,
                                        geo_result=geo_result,
                                    )
                            await db_session.commit()
                        logger.info("[Phase 3] Geocoded %d places for memory: %s", len(places), memory.memory_id)
                except Exception as geo_exc:
                    logger.warning("[Phase 3] Geocoding failed for %s: %s", memory.memory_id, geo_exc)
            else:
                logger.debug("[Phase 3] PRIVATE_LOCKER memory — skipping geocoding (P0 isolation)")

            # 11. Trigger any registered future phase hooks (extensibility point)
            for hook in self._post_phase1_hooks:
                try:
                    await hook(memory, persisted_raw_input, phase1_output)
                except Exception as hook_exc:
                    logger.warning(f"Post-Phase 1 hook failed: {hook_exc}", exc_info=True)


            return OrchestratedIngestionResult(
                memory=memory,
                raw_input_id=persisted_raw_input.id,
                phase1_output_id=phase1_output.id,
            )

        except Exception as exc:
            # Resilient failure handling: preserve raw input and record error details
            error_message = f"{type(exc).__name__}: {str(exc)}"
            logger.error("[MindMesh] Processing failed: %s", error_message)
            await self.raw_input_repo.mark_failed(raw_input.id, error_message=error_message)
            logger.info("[Storage] Raw input marked failed: %s", raw_input.id)
            raise

    async def process_text_ingestion(
        self,
        request: TextIngestionRequest,
        current_user: CurrentUser,
        raw_text_verbatim: str | None = None,
        input_id: uuid.UUID | None = None,
    ) -> MemoryV1:
        """Convenience method returning MemoryV1 for backward compatibility."""
        result = await self.process_text_ingestion_result(
            request=request,
            current_user=current_user,
            raw_text_verbatim=raw_text_verbatim,
            input_id=input_id,
        )
        return result.memory

    async def process_image_ingestion_result(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str | None,
        group_id: str | None,
        privacy: Any,
        allowed_users: list[str],
        current_user: CurrentUser,
        context: str | None = None,
        input_id: uuid.UUID | None = None,
    ) -> OrchestratedIngestionResult:
        """Orchestrate image ingestion with durable FileStorage and DB-first boundary."""
        logger.info("[MindMesh] Image request received: %s", filename)

        # 1. Durably persist raw image bytes to FileStorage before DB write
        logger.info("[Storage] Persisting raw image to durable FileStorage...")
        storage_ref = self.file_storage.save_file(
            file_bytes=file_bytes,
            filename=filename,
            media_type=MediaType.IMAGE,
            content_type=content_type,
        )
        logger.info("[Storage] Image persisted: key=%s path=%s", storage_ref.storage_key, storage_ref.relative_path)

        # 2. Record raw metadata payload referencing durable storage asset and user context
        raw_description = f"Image upload: filename={storage_ref.original_filename}, content_type={storage_ref.content_type}, size_bytes={storage_ref.size_bytes}"
        if context:
            raw_description += f", context={context}"
        privacy_str = privacy.value if hasattr(privacy, "value") else str(privacy)
        structured_payload = {
            "media_type": "image",
            "storage_key": storage_ref.storage_key,
            "relative_path": storage_ref.relative_path,
            "original_filename": storage_ref.original_filename,
            "filename": storage_ref.original_filename,
            "content_type": storage_ref.content_type,
            "size_bytes": storage_ref.size_bytes,
            "sha256": storage_ref.sha256,
            "created_at": storage_ref.created_at,
            "user_context": context,
            "group_id": group_id,
            "privacy": privacy_str,
            "allowed_users": allowed_users,
        }

        # 3. Persist raw input record into PostgreSQL
        logger.info("[Storage] Saving raw input record to PostgreSQL...")
        is_private_locker = (privacy_str == Privacy.PRIVATE_LOCKER.value)
        payload_to_store = locker_crypto.encrypt(raw_description) if is_private_locker else raw_description

        raw_input = await self.raw_input_repo.create(
            media_type=MediaType.IMAGE.value,
            raw_payload=payload_to_store,
            structured_payload=structured_payload,
            client_id=current_user.id,
            owner_id=current_user.id,
            privacy=privacy_str,
            group_id=group_id,
            status="received",
            input_id=input_id,
        )
        self.last_raw_input_id = raw_input.id
        logger.info("[Storage] Raw input saved: %s", raw_input.id)

        try:
            # 4. Read persisted raw input back from PostgreSQL (DB boundary verification)
            logger.info("[Storage] Reading raw input from PostgreSQL...")
            persisted_raw_input = await self.raw_input_repo.get_by_id(raw_input.id)
            if persisted_raw_input is None:
                raise RuntimeError(f"Failed to retrieve persisted raw input with id {raw_input.id}")
            logger.info("[Storage] Raw input retrieved: %s", persisted_raw_input.id)

            # 5. Construct Phase 1 input derived strictly from the persisted database record and FileStorage
            stored_metadata = persisted_raw_input.structured_payload or {}
            persisted_storage_ref_path = stored_metadata.get("relative_path") or stored_metadata.get("storage_key")
            if not persisted_storage_ref_path:
                raise RuntimeError(f"Persisted record {persisted_raw_input.id} missing storage reference")
            persisted_file_bytes = self.file_storage.get_file(persisted_storage_ref_path)

            privacy_val = stored_metadata.get("privacy", Privacy.ONLY_ME.value)
            if isinstance(privacy_val, str):
                try:
                    privacy_enum = Privacy(privacy_val)
                except ValueError:
                    privacy_enum = Privacy.ONLY_ME
            else:
                privacy_enum = privacy_val

            phase1_user = CurrentUser(id=persisted_raw_input.client_id)
            persisted_user_context = stored_metadata.get("user_context")

            # Reconstruct MediaReference strictly from persisted DB record (structured_payload)
            media_ref = MediaReference(
                storage_key=stored_metadata.get("storage_key", ""),
                relative_path=stored_metadata.get("relative_path", ""),
                original_filename=stored_metadata.get("original_filename", filename),
                media_type=stored_metadata.get("media_type", "image"),
                content_type=stored_metadata.get("content_type"),
                size_bytes=stored_metadata.get("size_bytes", len(persisted_file_bytes)),
                sha256=stored_metadata.get("sha256", ""),
                created_at=stored_metadata.get("created_at"),
            )

            # 6. Mark processing and execute Phase 1 image ingestion
            await self.raw_input_repo.update_status(persisted_raw_input.id, status="processing")
            logger.info("[Phase 1] Starting image ingestion...")
            memory = self.ingestion_service.ingest_image(
                file_bytes=persisted_file_bytes,
                filename=stored_metadata.get("original_filename", filename),
                content_type=stored_metadata.get("content_type"),
                group_id=persisted_raw_input.group_id,
                privacy=privacy_enum,
                allowed_users=stored_metadata.get("allowed_users", []),
                current_user=phase1_user,
                media_reference=media_ref,
                user_context=persisted_user_context,
            )
            logger.info("[Phase 1] MemoryV1 generated: %s", memory.memory_id)
            logger.info("[Phase 1] Validation completed")

            # 7. Persist complete MemoryV1 JSONB
            logger.info("[Storage] Saving Phase 1 output...")
            output_payload = memory.model_dump(mode="json")
            if is_private_locker and isinstance(output_payload.get("content"), dict):
                c_dict = dict(output_payload["content"])
                if c_dict.get("clean_text"):
                    c_dict["clean_text"] = locker_crypto.encrypt(c_dict["clean_text"])
                if c_dict.get("description"):
                    c_dict["description"] = locker_crypto.encrypt(c_dict["description"])
                if c_dict.get("summary"):
                    c_dict["summary"] = locker_crypto.encrypt(c_dict["summary"])
                output_payload["content"] = c_dict

            phase1_output = await self.phase1_output_repo.create(
                raw_input_id=persisted_raw_input.id,
                memory_id=memory.memory_id,
                schema_version=memory.schema_version,
                payload=output_payload,
                owner_id=persisted_raw_input.owner_id,
                privacy=persisted_raw_input.privacy,
                processing_status=memory.processing.status,
                extractor_model=memory.processing.llm_model,
            )
            self.last_phase1_output_id = phase1_output.id
            logger.info("[Storage] Phase 1 output saved: %s", phase1_output.id)

            # 8. Mark raw input completed
            await self.raw_input_repo.mark_completed(persisted_raw_input.id)
            logger.info("[Storage] Raw input marked completed")
            logger.info("[MindMesh] Processing completed successfully")

            # 9. Phase 2 Dual-Vector Embeddings
            if self.phase2_service is not None:
                try:
                    await self.phase2_service.process_phase1_output_id(phase1_output.id)
                    logger.info("[Phase 2] Dual-vector embeddings generated and stored for: %s", phase1_output.id)
                except Exception as p2_exc:
                    logger.warning("[Phase 2] Embedding generation failed for %s: %s", phase1_output.id, p2_exc)

            # 10. Trigger hooks
            for hook in self._post_phase1_hooks:
                try:
                    await hook(memory, persisted_raw_input, phase1_output)
                except Exception as hook_exc:
                    logger.warning(f"Post-Phase 1 hook failed: {hook_exc}", exc_info=True)

            return OrchestratedIngestionResult(
                memory=memory,
                raw_input_id=persisted_raw_input.id,
                phase1_output_id=phase1_output.id,
            )

        except Exception as exc:
            error_message = f"{type(exc).__name__}: {str(exc)}"
            logger.error("[MindMesh] Processing failed: %s", error_message)
            await self.raw_input_repo.mark_failed(raw_input.id, error_message=error_message)
            raise

    async def process_image_ingestion(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str | None,
        group_id: str | None,
        privacy: Any,
        allowed_users: list[str],
        current_user: CurrentUser,
        context: str | None = None,
        input_id: uuid.UUID | None = None,
    ) -> MemoryV1:
        """Convenience method returning MemoryV1 for image ingestion."""
        result = await self.process_image_ingestion_result(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            group_id=group_id,
            privacy=privacy,
            allowed_users=allowed_users,
            current_user=current_user,
            context=context,
            input_id=input_id,
        )
        return result.memory

    async def process_audio_ingestion_result(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str | None,
        group_id: str | None,
        privacy: Any,
        allowed_users: list[str],
        current_user: CurrentUser,
        context: str | None = None,
        input_id: uuid.UUID | None = None,
    ) -> OrchestratedIngestionResult:
        """Orchestrate audio ingestion with durable FileStorage and DB-first boundary."""
        logger.info("[MindMesh] Audio request received: %s", filename)

        # 1. Durably persist raw audio bytes to FileStorage before DB write
        logger.info("[Storage] Persisting raw audio to durable FileStorage...")
        storage_ref = self.file_storage.save_file(
            file_bytes=file_bytes,
            filename=filename,
            media_type=MediaType.AUDIO,
            content_type=content_type,
        )
        logger.info("[Storage] Audio persisted: key=%s path=%s", storage_ref.storage_key, storage_ref.relative_path)

        # 2. Record raw metadata payload referencing durable storage asset and user context
        raw_description = f"Audio upload: filename={storage_ref.original_filename}, content_type={storage_ref.content_type}, size_bytes={storage_ref.size_bytes}"
        if context:
            raw_description += f", context={context}"
        privacy_str = privacy.value if hasattr(privacy, "value") else str(privacy)
        structured_payload = {
            "media_type": "audio",
            "storage_key": storage_ref.storage_key,
            "relative_path": storage_ref.relative_path,
            "original_filename": storage_ref.original_filename,
            "filename": storage_ref.original_filename,
            "content_type": storage_ref.content_type,
            "size_bytes": storage_ref.size_bytes,
            "sha256": storage_ref.sha256,
            "created_at": storage_ref.created_at,
            "user_context": context,
            "group_id": group_id,
            "privacy": privacy_str,
            "allowed_users": allowed_users,
        }

        # 3. Persist raw input record to PostgreSQL before Phase 1 processing
        logger.info("[Storage] Saving raw input record to PostgreSQL...")
        is_private_locker = (privacy_str == Privacy.PRIVATE_LOCKER.value)
        payload_to_store = locker_crypto.encrypt(raw_description) if is_private_locker else raw_description

        raw_input = await self.raw_input_repo.create(
            media_type=MediaType.AUDIO.value,
            raw_payload=payload_to_store,
            structured_payload=structured_payload,
            client_id=current_user.id,
            owner_id=current_user.id,
            privacy=privacy_str,
            group_id=group_id,
            status="received",
            input_id=input_id,
        )
        self.last_raw_input_id = raw_input.id
        logger.info("[Storage] Raw input saved: %s", raw_input.id)

        try:
            # 4. Read persisted raw input back from PostgreSQL (DB boundary verification)
            logger.info("[Storage] Reading raw input from PostgreSQL...")
            persisted_raw_input = await self.raw_input_repo.get_by_id(raw_input.id)
            if persisted_raw_input is None:
                raise RuntimeError(f"Failed to retrieve persisted raw input with id {raw_input.id}")
            logger.info("[Storage] Raw input retrieved: %s", persisted_raw_input.id)

            # 5. Construct Phase 1 input derived strictly from the persisted database record and FileStorage
            stored_metadata = persisted_raw_input.structured_payload or {}
            persisted_storage_ref_path = stored_metadata.get("relative_path") or stored_metadata.get("storage_key")
            if not persisted_storage_ref_path:
                raise RuntimeError(f"Persisted record {persisted_raw_input.id} missing storage reference")
            persisted_file_bytes = self.file_storage.get_file(persisted_storage_ref_path)

            privacy_val = stored_metadata.get("privacy", Privacy.ONLY_ME.value)
            if isinstance(privacy_val, str):
                try:
                    privacy_enum = Privacy(privacy_val)
                except ValueError:
                    privacy_enum = Privacy.ONLY_ME
            else:
                privacy_enum = privacy_val

            phase1_user = CurrentUser(id=persisted_raw_input.client_id)
            persisted_user_context = stored_metadata.get("user_context")

            # Reconstruct MediaReference strictly from persisted DB record (structured_payload)
            media_ref = MediaReference(
                storage_key=stored_metadata.get("storage_key", ""),
                relative_path=stored_metadata.get("relative_path", ""),
                original_filename=stored_metadata.get("original_filename", filename),
                media_type=stored_metadata.get("media_type", "audio"),
                content_type=stored_metadata.get("content_type"),
                size_bytes=stored_metadata.get("size_bytes", len(persisted_file_bytes)),
                sha256=stored_metadata.get("sha256", ""),
                created_at=stored_metadata.get("created_at"),
            )

            # 6. Mark processing and execute Phase 1 audio ingestion
            await self.raw_input_repo.update_status(persisted_raw_input.id, status="processing")
            logger.info("[Phase 1] Starting audio ingestion...")
            memory = self.ingestion_service.ingest_audio(
                file_bytes=persisted_file_bytes,
                filename=stored_metadata.get("original_filename", filename),
                content_type=stored_metadata.get("content_type"),
                group_id=persisted_raw_input.group_id,
                privacy=privacy_enum,
                allowed_users=stored_metadata.get("allowed_users", []),
                current_user=phase1_user,
                media_reference=media_ref,
                user_context=persisted_user_context,
            )
            logger.info("[Phase 1] MemoryV1 generated: %s", memory.memory_id)
            logger.info("[Phase 1] Validation completed")

            # 7. Persist complete MemoryV1 JSONB in phase1_outputs table
            logger.info("[Storage] Saving Phase 1 output...")
            output_payload = memory.model_dump(mode="json")
            if is_private_locker and isinstance(output_payload.get("content"), dict):
                c_dict = dict(output_payload["content"])
                if c_dict.get("clean_text"):
                    c_dict["clean_text"] = locker_crypto.encrypt(c_dict["clean_text"])
                if c_dict.get("raw_text"):
                    c_dict["raw_text"] = locker_crypto.encrypt(c_dict["raw_text"])
                if c_dict.get("summary"):
                    c_dict["summary"] = locker_crypto.encrypt(c_dict["summary"])
                output_payload["content"] = c_dict

            phase1_output = await self.phase1_output_repo.create(
                raw_input_id=persisted_raw_input.id,
                memory_id=memory.memory_id,
                schema_version=memory.schema_version,
                payload=output_payload,
                owner_id=persisted_raw_input.owner_id,
                privacy=persisted_raw_input.privacy,
                processing_status=memory.processing.status,
                extractor_model=memory.processing.llm_model,
            )
            self.last_phase1_output_id = phase1_output.id
            logger.info("[Storage] Phase 1 output saved: %s", phase1_output.id)

            # 8. Mark raw input completed
            await self.raw_input_repo.mark_completed(persisted_raw_input.id)
            logger.info("[Storage] Raw input marked completed")
            logger.info("[MindMesh] Processing completed successfully")

            # 9. Phase 2 Dual-Vector Embeddings
            if self.phase2_service is not None:
                try:
                    await self.phase2_service.process_phase1_output_id(phase1_output.id)
                    logger.info("[Phase 2] Dual-vector embeddings generated and stored for: %s", phase1_output.id)
                except Exception as p2_exc:
                    logger.warning("[Phase 2] Embedding generation failed for %s: %s", phase1_output.id, p2_exc)

            # 10. Trigger hooks
            for hook in self._post_phase1_hooks:
                try:
                    await hook(memory, persisted_raw_input, phase1_output)
                except Exception as hook_exc:
                    logger.warning(f"Post-Phase 1 hook failed: {hook_exc}", exc_info=True)

            return OrchestratedIngestionResult(
                memory=memory,
                raw_input_id=persisted_raw_input.id,
                phase1_output_id=phase1_output.id,
            )

        except Exception as exc:
            error_message = f"{type(exc).__name__}: {str(exc)}"
            logger.error("[MindMesh] Processing failed: %s", error_message)
            await self.raw_input_repo.mark_failed(raw_input.id, error_message=error_message)
            raise

    async def process_audio_ingestion(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str | None,
        group_id: str | None,
        privacy: Any,
        allowed_users: list[str],
        current_user: CurrentUser,
        context: str | None = None,
        input_id: uuid.UUID | None = None,
    ) -> MemoryV1:
        """Convenience method returning MemoryV1 for audio ingestion."""
        result = await self.process_audio_ingestion_result(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            group_id=group_id,
            privacy=privacy,
            allowed_users=allowed_users,
            current_user=current_user,
            context=context,
            input_id=input_id,
        )
        return result.memory


# ---------------------------------------------------------------------------
# Phase 3 module-level helpers (fail-soft, no hard dependencies)
# ---------------------------------------------------------------------------

def _extract_places_from_memory(memory: "MemoryV1") -> list[str]:
    """Return unique, non-empty place/location strings from MemoryV1 entities."""
    places: list[str] = []
    try:
        entities = getattr(memory, "entities", None)
        if not entities:
            return places
        # Support both pydantic models and plain dicts
        entities_dict = entities.model_dump() if hasattr(entities, "model_dump") else dict(entities)
        seen: set[str] = set()
        for field in ("places", "locations", "organizations"):
            for item in (entities_dict.get(field) or []):
                name = (item.get("name") or item if isinstance(item, str) else "").strip()
                if name and name not in seen:
                    places.append(name)
                    seen.add(name)
    except Exception:
        pass
    return places


async def _upsert_memory_location(session: Any, memory_id: str, geo_result: dict) -> None:
    """Insert geocoded location into `locations` and link via `memory_locations`."""
    from sqlalchemy import text as _sql_text

    display_name = geo_result.get("display_name") or geo_result.get("location") or geo_result.get("name", "")
    lat = geo_result.get("latitude")
    lon = geo_result.get("longitude")
    confidence = float(geo_result.get("confidence", 1.0))
    source = geo_result.get("source", "locationiq")
    normalized_name = (display_name.strip().lower())[:256] or "unknown_location"

    if lat is None or lon is None:
        return

    try:
        # Check for an existing close-by location row or matching normalized_name
        existing = (await session.execute(
            _sql_text(
                "SELECT location_id FROM locations "
                "WHERE normalized_name = :nname OR (ABS(latitude - :lat) < 0.001 AND ABS(longitude - :lon) < 0.001) "
                "LIMIT 1"
            ),
            {"nname": normalized_name, "lat": float(lat), "lon": float(lon)},
        )).fetchone()

        if existing:
            loc_id = int(existing[0])
        else:
            insert_res = await session.execute(
                _sql_text(
                    "INSERT INTO locations (normalized_name, display_name, latitude, longitude, source, confidence) "
                    "VALUES (:nname, :name, :lat, :lon, :src, :conf) "
                    "ON CONFLICT (normalized_name) DO UPDATE SET updated_at = CURRENT_TIMESTAMP "
                    "RETURNING location_id"
                ),
                {
                    "nname": normalized_name,
                    "name": display_name[:512],
                    "lat": float(lat),
                    "lon": float(lon),
                    "src": source,
                    "conf": min(1.0, max(0.0, confidence)),
                },
            )
            row = insert_res.fetchone()
            loc_id = int(row[0]) if row else None

        if loc_id:
            await session.execute(
                _sql_text(
                    "INSERT INTO memory_locations (memory_id, location_id, confidence, source) "
                    "VALUES (:mid, :lid, :conf, 'extraction') "
                    "ON CONFLICT (memory_id, location_id) DO UPDATE SET confidence = EXCLUDED.confidence"
                ),
                {"mid": memory_id, "lid": loc_id, "conf": min(1.0, max(0.0, confidence))},
            )
    except Exception as exc:
        logger.warning("[Phase 3] _upsert_memory_location failed: %s", exc)
