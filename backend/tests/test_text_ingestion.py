import pytest

from app.core.enums import MediaType, Privacy
from app.core.errors import EmptyTextError
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.services.ingestion_service import IngestionService
from app.services.text_processor import TextProcessor


def test_text_cleanup_rejects_empty_text():
    with pytest.raises(EmptyTextError):
        TextProcessor().process(" \n\t ")


def test_text_ingestion_returns_valid_memory_v1():
    request = TextIngestionRequest(
        text="Had amazing coffee with Akshat at Cafe Bodega in Goa.",
        group_id="G04",
        privacy=Privacy.GROUP,
    )

    memory = IngestionService().ingest_text(
        request=request,
        current_user=CurrentUser(id="U17"),
    )

    assert memory.schema_version == "1.0"
    assert memory.system.owner_id == "U17"
    assert memory.system.group_id == "G04"
    assert memory.system.media_type == MediaType.TEXT
    assert memory.system.privacy == Privacy.GROUP
    assert memory.content.clean_text == request.text
    assert "Akshat" in memory.entities.people
    assert "Goa" in memory.entities.locations
    assert "coffee" in memory.semantics.topics
    assert memory.processing.status == "completed"
    assert memory.processing.transcription_required is False
    assert memory.processing.image_understanding_required is False
