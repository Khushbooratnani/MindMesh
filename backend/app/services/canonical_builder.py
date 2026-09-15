from app.schemas.canonical_input import CanonicalInput, ProcessedInput, SystemContext


class CanonicalInputBuilder:
    def build(
        self,
        processed: ProcessedInput,
        system_context: SystemContext,
    ) -> CanonicalInput:
        if system_context.user_context and system_context.user_context.strip():
            ctx = system_context.user_context.strip()
            body = processed.clean_text.strip() if processed.clean_text else ""
            source_text = f"{ctx}\n\n{body}" if body else ctx
        else:
            source_text = processed.clean_text

        return CanonicalInput(
            media_type=processed.media_type,
            source_text=source_text,
            raw_text=processed.raw_text,
            source_context=system_context,
            media_reference=system_context.media_reference,
            user_context=system_context.user_context,
        )
