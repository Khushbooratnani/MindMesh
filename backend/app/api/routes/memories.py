import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Privacy
from app.database.connection.session import get_db_session
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.raw_input_repo import RawInputRepository
from app.orchestration.orchestrator import MindMeshOrchestrator
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.schemas.memory_output import MemoryV1
from app.services.ingestion_service import IngestionService

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
    return MindMeshOrchestrator(
        raw_input_repo=raw_input_repo,
        phase1_output_repo=phase1_output_repo,
        ingestion_service=ingestion_service,
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
