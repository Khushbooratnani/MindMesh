from datetime import UTC, datetime
from uuid import uuid4

from app.core.enums import MediaType
from app.schemas.canonical_input import CanonicalInput, SystemContext
from app.schemas.extraction_output import ExtractionOutput
from app.schemas.memory_output import (
    ContentFields,
    EntityFields,
    MemoryV1,
    ProcessingFields,
    SemanticFields,
    SystemFields,
    TemporalFields,
)


class MemoryAssembler:
    def assemble(
        self,
        system_context: SystemContext,
        canonical_input: CanonicalInput,
        extraction: ExtractionOutput,
        llm_provider: str,
        llm_model: str,
    ) -> MemoryV1:
        return MemoryV1(
            memory_id=f"M_{uuid4().hex}",
            system=SystemFields(
                owner_id=system_context.owner_id,
                group_id=system_context.group_id,
                media_type=system_context.media_type,
                created_at=datetime.now(UTC).isoformat(),
                privacy=system_context.privacy,
                allowed_users=system_context.allowed_users,
            ),
            content=ContentFields(
                raw_text=canonical_input.raw_text,
                clean_text=canonical_input.source_text,
                description=extraction.description,
                summary=extraction.summary,
            ),
            entities=EntityFields(**extraction.entities.model_dump()),
            semantics=SemanticFields(**extraction.semantics.model_dump()),
            temporal=TemporalFields(**extraction.temporal.model_dump()),
            additional_attributes=extraction.additional_attributes,
            processing=ProcessingFields(
                status="completed",
                source_modality=canonical_input.media_type,
                transcription_required=canonical_input.media_type == MediaType.AUDIO,
                image_understanding_required=canonical_input.media_type == MediaType.IMAGE,
                llm_provider=llm_provider,
                llm_model=llm_model,
                errors=[],
            ),
        )
