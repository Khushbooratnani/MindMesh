import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Privacy
from app.database.connection.session import get_db_session
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.phase2_embedding_repo import Phase2EmbeddingRepository
from app.database.repositories.raw_input_repo import RawInputRepository
from app.orchestration.orchestrator import MindMeshOrchestrator
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.schemas.memory_output import MemoryV1
from app.schemas.search_schemas import MemorySearchRequest, MemorySearchResponse
from app.services.ingestion_service import IngestionService
from app.services.memory_search_service import MemorySearchService
from app.services.phase2_service import Phase2Service

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


def get_current_user() -> CurrentUser:
    return CurrentUser(id="U_DEVELOPMENT")


def get_ingestion_service() -> IngestionService:
    return IngestionService()


def get_orchestrator(
    session: AsyncSession = Depends(get_db_session),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> MindMeshOrchestrator:
    raw_input_repo = RawInputRepository(session)
    phase1_output_repo = Phase1OutputRepository(session)
    phase2_repo = Phase2EmbeddingRepository(session)
    phase2_service = Phase2Service(
        phase1_output_repo=phase1_output_repo,
        phase2_embedding_repo=phase2_repo,
        session=session,
    )
    return MindMeshOrchestrator(
        raw_input_repo=raw_input_repo,
        phase1_output_repo=phase1_output_repo,
        ingestion_service=ingestion_service,
        phase2_service=phase2_service,
    )


@router.post("/ingest", response_model=MemoryV1)
async def ingest_memory(
    request: TextIngestionRequest,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: MindMeshOrchestrator = Depends(get_orchestrator),
) -> MemoryV1:
    result = await orchestrator.process_text_ingestion_result(request, current_user)
    response.headers["X-Raw-Input-Id"] = str(result.raw_input_id)
    response.headers["X-Phase1-Output-Id"] = str(result.phase1_output_id)
    return result.memory


@router.post("/ingest/image", response_model=MemoryV1)
async def ingest_image_memory(
    response: Response,
    media_type: str = Form(...),
    file: UploadFile = File(...),
    context: str | None = Form(None),
    group_id: str | None = Form(None),
    privacy: Privacy = Form(Privacy.ONLY_ME),
    allowed_users: str = Form("[]"),
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: MindMeshOrchestrator = Depends(get_orchestrator),
) -> MemoryV1:
    if media_type != "image":
        from app.core.errors import UnsupportedMediaTypeError

        raise UnsupportedMediaTypeError("Image endpoint only accepts media_type=image.")

    file_bytes = await file.read()
    result = await orchestrator.process_image_ingestion_result(
        file_bytes=file_bytes,
        filename=file.filename or "upload",
        content_type=file.content_type,
        context=context,
        group_id=group_id,
        privacy=privacy,
        allowed_users=_parse_allowed_users(allowed_users),
        current_user=current_user,
    )
    response.headers["X-Raw-Input-Id"] = str(result.raw_input_id)
    response.headers["X-Phase1-Output-Id"] = str(result.phase1_output_id)
    return result.memory


@router.post("/ingest/audio", response_model=MemoryV1)
async def ingest_audio_memory(
    response: Response,
    media_type: str = Form("audio"),
    file: UploadFile = File(...),
    context: str | None = Form(None),
    group_id: str | None = Form(None),
    privacy: Privacy = Form(Privacy.ONLY_ME),
    allowed_users: str = Form("[]"),
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: MindMeshOrchestrator = Depends(get_orchestrator),
) -> MemoryV1:
    if media_type != "audio":
        from app.core.errors import UnsupportedMediaTypeError

        raise UnsupportedMediaTypeError("Audio endpoint only accepts media_type=audio.")

    file_bytes = await file.read()
    result = await orchestrator.process_audio_ingestion_result(
        file_bytes=file_bytes,
        filename=file.filename or "upload.audio",
        content_type=file.content_type,
        context=context,
        group_id=group_id,
        privacy=privacy,
        allowed_users=_parse_allowed_users(allowed_users),
        current_user=current_user,
    )
    response.headers["X-Raw-Input-Id"] = str(result.raw_input_id)
    response.headers["X-Phase1-Output-Id"] = str(result.phase1_output_id)
    return result.memory


def _parse_allowed_users(value: str) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("allowed_users must be a JSON array of strings.")
    return parsed


@router.get("/inventory")
async def get_memories_inventory(
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Read-only diagnostic endpoint to inspect persisted raw_inputs and phase1_outputs."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.database.models.raw_input import RawInputModel

    stmt = (
        select(RawInputModel)
        .options(selectinload(RawInputModel.phase1_outputs))
        .order_by(RawInputModel.received_at.asc())
    )
    result = await session.execute(stmt)
    raw_inputs = result.scalars().all()

    inventory = []
    for r in raw_inputs:
        for p in r.phase1_outputs:
            inventory.append({
                "raw_input_id": str(r.id),
                "media_type": r.media_type,
                "raw_payload": r.raw_payload,
                "structured_payload": r.structured_payload,
                "raw_status": r.status,
                "phase1_output_id": str(p.id),
                "memory_id": p.memory_id,
                "phase1_status": p.processing_status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })
    return inventory


@router.get("/feed")
async def get_raw_feed(
    limit: int = 150,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Production stream feed powered by PostgreSQL raw_inputs joined with canonical phase1_outputs MemoryV1."""
    repo = RawInputRepository(session)
    raw_inputs = await repo.get_feed(limit=limit, offset=offset)
    total_count = await repo.get_total_count()

    items = []
    for r in raw_inputs:
        # Check if canonical phase1_output is available
        p1 = r.phase1_outputs[0] if r.phase1_outputs else None
        st = r.structured_payload or {}

        if p1 and p1.payload:
            p1_payload = dict(p1.payload)
            p1_system = p1_payload.get("system") or {}
            p1_content = p1_payload.get("content") or {}
            p1_entities = p1_payload.get("entities") or {}
            p1_semantics = p1_payload.get("semantics") or {}
            p1_temporal = p1_payload.get("temporal") or {}
            p1_processing = p1_payload.get("processing") or {}
            media_obj = p1_payload.get("media")

            storage_key = None
            if media_obj and isinstance(media_obj, dict):
                storage_key = media_obj.get("storage_key") or st.get("storage_key")
                if storage_key:
                    media_obj["storage_key"] = storage_key
                    media_obj["url"] = f"/api/v1/media/{storage_key}"
                orig_filename = (
                    media_obj.get("original_filename")
                    or st.get("original_filename")
                    or st.get("filename")
                )
            else:
                storage_key = st.get("storage_key")
                orig_filename = st.get("original_filename") or st.get("filename")

            media_url = (
                f"http://10.9.11.238:8001/api/v1/media/{storage_key}"
                if storage_key
                else None
            )
            user_ctx = (
                p1_payload.get("user_context")
                or p1_content.get("user_context")
                or st.get("user_context")
            )

            # Determine clean, rich display text
            media_type = p1_system.get("media_type") or r.media_type
            if media_type == "audio":
                display_text = (
                    p1_content.get("raw_text")
                    or p1_content.get("clean_text")
                    or p1_content.get("summary")
                    or r.raw_payload
                )
            elif media_type == "image":
                display_text = (
                    p1_content.get("description")
                    or p1_content.get("summary")
                    or p1_content.get("clean_text")
                    or user_ctx
                    or r.raw_payload
                )
            else:
                display_text = (
                    p1_content.get("clean_text")
                    or p1_content.get("summary")
                    or r.raw_payload
                )

            if media_obj and isinstance(media_obj, dict):
                p1_payload["media"] = media_obj

            items.append({
                "id": p1.memory_id or str(r.id),
                "memory_id": p1.memory_id or str(r.id),
                "raw_input_id": str(r.id),
                "phase1_output_id": str(p1.id),
                "media_type": media_type,
                "raw_payload": display_text,
                "structured_payload": st,
                "received_at": r.received_at.isoformat() if r.received_at else None,
                "created_at": p1_system.get("created_at")
                or (r.received_at.isoformat() if r.received_at else None),
                "status": p1.processing_status or r.status,
                "user_context": user_ctx,
                "original_filename": orig_filename,
                "storage_key": storage_key,
                "media_url": media_url,
                "group_id": p1_system.get("group_id") or r.group_id,
                # Canonical MemoryV1 structure fields
                "system": p1_system,
                "content": p1_content,
                "entities": p1_entities,
                "semantics": p1_semantics,
                "temporal": p1_temporal,
                "processing": p1_processing,
                "media": media_obj,
                "additional_attributes": p1_payload.get("additional_attributes") or [],
                "memory": p1_payload,
            })
        else:
            # Safe fallback for raw inputs without phase1_output
            storage_key = st.get("storage_key")
            media_url = (
                f"http://10.9.11.238:8001/api/v1/media/{storage_key}"
                if storage_key
                else None
            )
            orig_filename = st.get("original_filename") or st.get("filename")
            user_ctx = st.get("user_context")

            items.append({
                "id": str(r.id),
                "memory_id": str(r.id),
                "raw_input_id": str(r.id),
                "phase1_output_id": None,
                "media_type": r.media_type,
                "raw_payload": r.raw_payload,
                "structured_payload": st,
                "received_at": r.received_at.isoformat() if r.received_at else None,
                "created_at": r.received_at.isoformat() if r.received_at else None,
                "status": r.status,
                "user_context": user_ctx,
                "original_filename": orig_filename,
                "storage_key": storage_key,
                "media_url": media_url,
                "group_id": r.group_id,
                "system": {
                    "owner_id": r.client_id,
                    "group_id": r.group_id,
                    "media_type": r.media_type,
                    "created_at": r.received_at.isoformat() if r.received_at else "",
                    "privacy": "ONLY_ME",
                    "allowed_users": [],
                },
                "content": {
                    "raw_text": r.raw_payload,
                    "clean_text": r.raw_payload,
                    "description": "",
                    "summary": r.raw_payload[:100] if r.raw_payload else "",
                    "user_context": user_ctx,
                },
                "entities": {
                    "people": [],
                    "places": [],
                    "locations": [],
                    "events": [],
                    "organizations": [],
                },
                "semantics": {
                    "topics": [r.media_type.upper()],
                    "activities": [],
                    "sentiment": "unknown",
                    "mood": [],
                },
                "temporal": {
                    "mentioned_dates": [],
                    "inferred_time": None,
                    "time_of_day": None,
                },
                "processing": {
                    "status": r.status,
                    "source_modality": r.media_type,
                    "transcription_required": False,
                    "image_understanding_required": False,
                    "llm_provider": "local",
                    "llm_model": "Qwen",
                    "errors": [r.error_message] if r.error_message else [],
                },
                "media": None,
                "additional_attributes": [],
                "memory": None,
            })

    return {
        "total_count": total_count,
        "items": items,
    }


def get_search_service(
    session: AsyncSession = Depends(get_db_session),
) -> MemorySearchService:
    return MemorySearchService(
        embedding_repo=Phase2EmbeddingRepository(session)
    )


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    request: MemorySearchRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
    search_service: MemorySearchService = Depends(get_search_service),
) -> MemorySearchResponse:
    """Semantic dual-vector memory search with grounded LLM answer synthesis."""
    return await search_service.search(
        session=session,
        query=request.query,
        top_k=request.top_k,
        user_id=current_user.id,
        content_weight=request.content_weight,
        context_weight=request.context_weight,
    )



