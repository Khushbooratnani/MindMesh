import json
from typing import Any
import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, exists

from app.config import settings
from app.core.enums import Privacy, GroupRole
from app.database.connection.session import get_db_session
from app.database.models.raw_input import RawInputModel
from app.database.models.user import UserModel
from app.database.models.groups import MemoryGroupAccessModel, GroupFeedReferenceModel
from app.database.models.phase1_output import Phase1OutputModel
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.phase2_embedding_repo import Phase2EmbeddingRepository
from app.database.repositories.raw_input_repo import RawInputRepository
from app.orchestration.orchestrator import MindMeshOrchestrator
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.schemas.memory_output import MemoryV1
from app.schemas.search_schemas import MemorySearchRequest, MemorySearchResponse
from app.schemas.group import ShareMemoryRequest, RevokeMemoryShareRequest, MemorySharesResponse
from app.services.crypto_service import locker_crypto
from app.services.ingestion_service import IngestionService
from app.services.memory_search_service import MemorySearchService
from app.services.phase2_service import Phase2Service
from app.services.share_service import ShareService
from app.services.group_service import GroupService
from app.api.dependencies.auth import get_current_user, get_active_locker_session

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


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


async def _handle_group_ingestion_pre(
    group_id_str: str | None, privacy: Privacy, user_id: str, db: AsyncSession
) -> uuid.UUID | None:
    if not group_id_str:
        return None
    if privacy == Privacy.PRIVATE_LOCKER:
        raise HTTPException(
            status_code=400,
            detail="Private locker memories cannot be associated with a group.",
        )
    try:
        target_gid = uuid.UUID(str(group_id_str))
    except (ValueError, TypeError):
        return None

    # Enforce active membership and upload permissions (OWNER, ADMIN, CONTRIBUTOR, MEMBER)
    await GroupService.verify_membership(
        session=db,
        group_id=target_gid,
        user_id=user_id,
        required_roles=[
            GroupRole.OWNER.value,
            GroupRole.ADMIN.value,
            GroupRole.CONTRIBUTOR.value,
            GroupRole.MEMBER.value,
        ],
    )
    return target_gid


async def _handle_group_ingestion_post(
    target_gid: uuid.UUID | None, memory_id: str, user_id: str, db: AsyncSession
) -> None:
    if not target_gid:
        return
    db.add(
        MemoryGroupAccessModel(
            memory_id=memory_id,
            group_id=target_gid,
            granted_by=user_id,
        )
    )
    db.add(
        GroupFeedReferenceModel(
            memory_id=memory_id,
            group_id=target_gid,
            shared_by=user_id,
        )
    )
    await db.commit()


@router.post("/ingest", response_model=MemoryV1)
async def ingest_memory(
    request: TextIngestionRequest,
    response: Response,
    fastapi_req: Request,
    current_user: UserModel = Depends(get_current_user),
    orchestrator: MindMeshOrchestrator = Depends(get_orchestrator),
    db: AsyncSession = Depends(get_db_session),
) -> MemoryV1:
    target_gid = await _handle_group_ingestion_pre(
        request.group_id, request.privacy, current_user.id, db
    )
    if request.privacy == Privacy.PRIVATE_LOCKER:
        await get_active_locker_session(fastapi_req, current_user, db)

    result = await orchestrator.process_text_ingestion_result(request, current_user)
    await _handle_group_ingestion_post(target_gid, result.memory.memory_id, current_user.id, db)
    await db.commit()

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
    fastapi_req: Request = None,
    current_user: UserModel = Depends(get_current_user),
    orchestrator: MindMeshOrchestrator = Depends(get_orchestrator),
    db: AsyncSession = Depends(get_db_session),
) -> MemoryV1:
    target_gid = await _handle_group_ingestion_pre(group_id, privacy, current_user.id, db)
    if privacy == Privacy.PRIVATE_LOCKER:
        await get_active_locker_session(fastapi_req, current_user, db)

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
    await _handle_group_ingestion_post(target_gid, result.memory.memory_id, current_user.id, db)
    await db.commit()

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
    fastapi_req: Request = None,
    current_user: UserModel = Depends(get_current_user),
    orchestrator: MindMeshOrchestrator = Depends(get_orchestrator),
    db: AsyncSession = Depends(get_db_session),
) -> MemoryV1:
    target_gid = await _handle_group_ingestion_pre(group_id, privacy, current_user.id, db)
    if privacy == Privacy.PRIVATE_LOCKER:
        await get_active_locker_session(fastapi_req, current_user, db)

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
    await _handle_group_ingestion_post(target_gid, result.memory.memory_id, current_user.id, db)
    await db.commit()

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
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Read-only diagnostic endpoint to inspect persisted raw_inputs for the caller. Disabled in production."""
    if settings.app_env.lower() in ("production", "prod"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diagnostic inventory endpoint is disabled in production.",
        )

    from sqlalchemy.orm import selectinload

    stmt = (
        select(RawInputModel)
        .options(selectinload(RawInputModel.phase1_outputs))
        .where(
            and_(
                RawInputModel.owner_id == current_user.id,
                RawInputModel.privacy != "PRIVATE_LOCKER",
            )
        )
        .order_by(RawInputModel.received_at.asc())
    )
    result = await session.execute(stmt)
    raw_inputs = result.scalars().all()

    inventory = []
    for r in raw_inputs:
        for p in r.phase1_outputs:
            if p.privacy == "PRIVATE_LOCKER":
                continue
            inventory.append({
                "raw_input_id": str(r.id),
                "media_type": r.media_type,
                "raw_payload": locker_crypto.decrypt(r.raw_payload) if r.raw_payload else "",
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
    group_id: str | None = None,
    fastapi_req: Request = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Production stream feed powered by PostgreSQL raw_inputs joined with canonical phase1_outputs MemoryV1."""
    repo = RawInputRepository(session)

    if group_id:
        from sqlalchemy.orm import selectinload

        # 1. Require valid group and authenticated active membership
        try:
            target_gid = uuid.UUID(str(group_id))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invalid group identifier format: '{group_id}'.",
            )

        # Enforce membership check: raises 404 if not found / 403 if not member
        await GroupService.verify_membership(
            session=session,
            group_id=target_gid,
            user_id=current_user.id,
        )

        # Shared memories subquery via MemoryGroupAccessModel
        shared_raw_ids = select(Phase1OutputModel.raw_input_id).where(
            and_(
                Phase1OutputModel.privacy != "PRIVATE_LOCKER",
                exists().where(
                    and_(
                        MemoryGroupAccessModel.memory_id == Phase1OutputModel.memory_id,
                        MemoryGroupAccessModel.group_id == target_gid,
                    )
                ),
            )
        )

        stmt = (
            select(RawInputModel)
            .options(selectinload(RawInputModel.phase1_outputs))
            .where(
                and_(
                    RawInputModel.privacy != "PRIVATE_LOCKER",
                    or_(
                        RawInputModel.group_id == str(target_gid),
                        RawInputModel.group_id == group_id,
                        RawInputModel.id.in_(shared_raw_ids),
                    ),
                )
            )
            .order_by(RawInputModel.received_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        raw_inputs = result.scalars().all()

        count_stmt = select(func.count(RawInputModel.id)).where(
            and_(
                RawInputModel.privacy != "PRIVATE_LOCKER",
                or_(
                    RawInputModel.group_id == str(target_gid),
                    RawInputModel.group_id == group_id,
                    RawInputModel.id.in_(shared_raw_ids),
                ),
            )
        )
        total_count = (await session.execute(count_stmt)).scalar() or 0
    else:
        # P0 PRIVACY ISOLATION: Main Stream feed must NEVER include Private Locker memories under any circumstances.
        include_private = False
        raw_inputs = await repo.get_feed(
            user_id=current_user.id, limit=limit, offset=offset, include_private=False
        )
        total_count = await repo.get_total_count(user_id=current_user.id, include_private=False)

    items = []
    for r in raw_inputs:
        # Check if canonical phase1_output is available
        p1 = r.phase1_outputs[0] if r.phase1_outputs else None
        st = r.structured_payload or {}

        decrypted_raw = locker_crypto.decrypt(r.raw_payload) if r.raw_payload else ""

        if p1 and p1.payload:
            p1_payload = dict(p1.payload)
            p1_system = dict(p1_payload.get("system") or {})
            p1_content = dict(p1_payload.get("content") or {})
            p1_entities = p1_payload.get("entities") or {}
            p1_semantics = p1_payload.get("semantics") or {}
            p1_temporal = p1_payload.get("temporal") or {}
            p1_processing = p1_payload.get("processing") or {}
            media_obj = p1_payload.get("media")

            # Decrypt content fields if encrypted
            for k in ("clean_text", "raw_text", "summary", "description"):
                if k in p1_content and p1_content[k]:
                    p1_content[k] = locker_crypto.decrypt(str(p1_content[k]))

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

            media_url = f"/api/v1/media/{storage_key}" if storage_key else None
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
                    or decrypted_raw
                )
            elif media_type == "image":
                display_text = (
                    p1_content.get("description")
                    or p1_content.get("summary")
                    or p1_content.get("clean_text")
                    or user_ctx
                    or decrypted_raw
                )
            else:
                display_text = (
                    p1_content.get("clean_text")
                    or p1_content.get("summary")
                    or decrypted_raw
                )

            if media_obj and isinstance(media_obj, dict):
                p1_payload["media"] = media_obj
            p1_payload["content"] = p1_content

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
                "privacy": r.privacy,
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
            media_url = f"/api/v1/media/{storage_key}" if storage_key else None
            orig_filename = st.get("original_filename") or st.get("filename")
            user_ctx = st.get("user_context")

            items.append({
                "id": str(r.id),
                "memory_id": str(r.id),
                "raw_input_id": str(r.id),
                "phase1_output_id": None,
                "media_type": r.media_type,
                "raw_payload": decrypted_raw,
                "structured_payload": st,
                "received_at": r.received_at.isoformat() if r.received_at else None,
                "created_at": r.received_at.isoformat() if r.received_at else None,
                "status": r.status,
                "user_context": user_ctx,
                "original_filename": orig_filename,
                "storage_key": storage_key,
                "media_url": media_url,
                "group_id": r.group_id,
                "privacy": r.privacy,
                "system": {
                    "owner_id": r.owner_id or r.client_id,
                    "group_id": r.group_id,
                    "media_type": r.media_type,
                    "created_at": r.received_at.isoformat() if r.received_at else "",
                    "privacy": r.privacy or "ONLY_ME",
                    "allowed_users": [],
                },
                "content": {
                    "raw_text": decrypted_raw,
                    "clean_text": decrypted_raw,
                    "description": "",
                    "summary": decrypted_raw[:100] if decrypted_raw else "",
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
    fastapi_req: Request,
    session: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
    search_service: MemorySearchService = Depends(get_search_service),
) -> MemorySearchResponse:
    """Semantic dual-vector memory search with grounded LLM answer synthesis."""
    # P0 PRIVACY ISOLATION: Normal semantic search must NEVER return Private Locker records.
    locker_session_valid = False

    search_kwargs = {
        "session": session,
        "query": request.query,
        "top_k": request.top_k,
        "user_id": current_user.id,
        "content_weight": request.content_weight,
        "context_weight": request.context_weight,
    }
    import inspect
    sig = inspect.signature(search_service.search)
    if "group_id" in sig.parameters:
        search_kwargs["group_id"] = request.group_id
    if "locker_session_valid" in sig.parameters:
        search_kwargs["locker_session_valid"] = locker_session_valid

    return await search_service.search(**search_kwargs)


@router.post("/{memory_id}/share")
async def share_memory(
    memory_id: str,
    request: ShareMemoryRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Share personal memory to groups or users."""
    await ShareService.share_memory(
        session=db,
        memory_id=memory_id,
        user_id=current_user.id,
        group_ids=request.group_ids,
        user_ids=request.user_ids,
        can_edit=request.can_edit,
        can_reshare=request.can_reshare,
    )
    return {
        "message": "Memory shared successfully.",
        "memory_id": memory_id,
        "shared_groups": [str(g) for g in request.group_ids],
        "shared_users": request.user_ids,
    }


@router.post("/{memory_id}/revoke")
async def revoke_memory_share(
    memory_id: str,
    request: RevokeMemoryShareRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke sharing permissions for a memory."""
    await ShareService.revoke_access(
        session=db,
        memory_id=memory_id,
        user_id=current_user.id,
        group_ids=request.group_ids,
        user_ids=request.user_ids,
    )
    return {
        "message": "Memory access revoked successfully.",
        "memory_id": memory_id,
    }


@router.get("/{memory_id}/shares", response_model=MemorySharesResponse)
async def get_memory_shares(
    memory_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """View current sharing permissions for a memory."""
    return await ShareService.get_memory_shares(
        session=db,
        memory_id=memory_id,
        user_id=current_user.id,
    )
