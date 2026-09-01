import pytest

from app.core.enums import MediaType, Privacy, Sentiment
from app.core.errors import SchemaValidationError
from app.schemas.memory_output import (
    ContentFields,
    EntityFields,
    MemoryV1,
    ProcessingFields,
    SemanticFields,
    SystemFields,
    TemporalFields,
)
from app.services.validation_service import ValidationService


def build_memory(**overrides):
    memory = {
        "memory_id": "M_TEST",
        "system": SystemFields(
            owner_id="U17",
            group_id="G04",
            media_type=MediaType.TEXT,
            created_at="2026-08-31T10:30:00+00:00",
            privacy=Privacy.GROUP,
            allowed_users=[],
        ),
        "content": ContentFields(
            raw_text="Had coffee with Akshat.",
            clean_text="Had coffee with Akshat.",
            description="A memory about coffee with Akshat.",
            summary="Coffee with Akshat.",
        ),
        "entities": EntityFields(people=["Akshat", "akshat", " "]),
        "semantics": SemanticFields(
            topics=["coffee", "Coffee", ""],
            activities=["drinking coffee"],
            sentiment=Sentiment.POSITIVE,
            mood=["happy"],
        ),
        "temporal": TemporalFields(time_of_day="unknown"),
        "additional_attributes": [],
        "processing": ProcessingFields(
            status="completed",
            source_modality=MediaType.TEXT,
            transcription_required=False,
            image_understanding_required=False,
            llm_provider="openai-compatible",
            llm_model="mock-memory-extractor",
            errors=[],
        ),
    }
    memory.update(overrides)
    return MemoryV1(**memory)


def test_valid_memory_passes_and_normalizes_arrays():
    memory = ValidationService().validate(build_memory())

    assert memory.entities.people == ["Akshat"]
    assert memory.semantics.topics == ["coffee"]


def test_allowed_users_requires_selected_privacy():
    memory = build_memory(
        system=SystemFields(
            owner_id="U17",
            group_id="G04",
            media_type=MediaType.TEXT,
            created_at="2026-08-31T10:30:00+00:00",
            privacy=Privacy.GROUP,
            allowed_users=["U18"],
        )
    )

    with pytest.raises(SchemaValidationError):
        ValidationService().validate(memory)
