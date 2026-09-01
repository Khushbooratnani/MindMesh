from fastapi import APIRouter, Depends

from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.schemas.memory_output import MemoryV1
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


def get_current_user() -> CurrentUser:
    return CurrentUser(id="U_DEVELOPMENT")


def get_ingestion_service() -> IngestionService:
    return IngestionService()


@router.post("/ingest", response_model=MemoryV1)
def ingest_memory(
    request: TextIngestionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> MemoryV1:
    return ingestion_service.ingest_text(request, current_user)
