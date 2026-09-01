from app.schemas.canonical_input import CanonicalInput, ProcessedInput, SystemContext


class CanonicalInputBuilder:
    def build(
        self,
        processed: ProcessedInput,
        system_context: SystemContext,
    ) -> CanonicalInput:
        return CanonicalInput(
            media_type=processed.media_type,
            source_text=processed.clean_text,
            raw_text=processed.raw_text,
            source_context=system_context,
        )
