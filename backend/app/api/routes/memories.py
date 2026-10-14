import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.enums import Privacy
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.schemas.memory_output import MemoryV1
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


def get_current_user() -> CurrentUser:
    return CurrentUser(id="U_MEHUL_01")


def get_ingestion_service() -> IngestionService:
    return IngestionService()


@router.post("/ingest", response_model=MemoryV1)
def ingest_memory(
    request: TextIngestionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> MemoryV1:
    return ingestion_service.ingest_text(request, current_user)


@router.post("/ingest/image", response_model=MemoryV1)
async def ingest_image_memory(
    media_type: str = Form(...),
    file: UploadFile = File(...),
    group_id: str | None = Form(None),
    privacy: Privacy = Form(Privacy.ONLY_ME),
    allowed_users: str = Form("[]"),
    current_user: CurrentUser = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> MemoryV1:
    if media_type != "image":
        from app.core.errors import UnsupportedMediaTypeError

        raise UnsupportedMediaTypeError("Image endpoint only accepts media_type=image.")

    file_bytes = await file.read()
    return ingestion_service.ingest_image(
        file_bytes=file_bytes,
        filename=file.filename or "upload",
        content_type=file.content_type,
        group_id=group_id,
        privacy=privacy,
        allowed_users=_parse_allowed_users(allowed_users),
        current_user=current_user,
    )


@router.post("/ingest/audio", response_model=MemoryV1)
async def ingest_audio_memory(
    media_type: str = Form(...),
    file: UploadFile = File(...),
    group_id: str | None = Form(None),
    privacy: Privacy = Form(Privacy.ONLY_ME),
    allowed_users: str = Form("[]"),
    current_user: CurrentUser = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> MemoryV1:
    if media_type != "audio":
        from app.core.errors import UnsupportedMediaTypeError
        raise UnsupportedMediaTypeError("Audio endpoint only accepts media_type=audio.")
    suffix = Path(file.filename or "upload.wav").suffix.lower() or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as temp_file:
        temp_file.write(await file.read())
        temp_file.flush()
        return ingestion_service.ingest_audio(
            file_path=Path(temp_file.name), group_id=group_id, privacy=privacy,
            allowed_users=_parse_allowed_users(allowed_users), current_user=current_user,
        )


def _parse_allowed_users(value: str) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("allowed_users must be a JSON array of strings.")
    return parsed
