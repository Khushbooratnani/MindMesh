from app.config import settings
from app.core.enums import MediaType
from app.core.errors import FileTooLargeError, UnsupportedMediaTypeError
from app.schemas.canonical_input import SystemContext
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.schemas.memory_output import MemoryV1
from app.services.canonical_builder import CanonicalInputBuilder
from app.services.image_processor import ImageProcessor
from app.services.audio_processor import AudioProcessor
from app.services.llm_service import LLMService
from app.services.memory_assembler import MemoryAssembler
from app.services.text_processor import TextProcessor
from app.services.validation_service import ValidationService


class IngestionService:
    def __init__(
        self,
        text_processor: TextProcessor | None = None,
        image_processor: ImageProcessor | None = None,
        audio_processor: AudioProcessor | None = None,
        canonical_builder: CanonicalInputBuilder | None = None,
        llm_service: LLMService | None = None,
        memory_assembler: MemoryAssembler | None = None,
        validation_service: ValidationService | None = None,
    ):
        self.text_processor = text_processor or TextProcessor()
        self.image_processor = image_processor or ImageProcessor()
        self.audio_processor = audio_processor or AudioProcessor()
        self.canonical_builder = canonical_builder or CanonicalInputBuilder()
        self.llm_service = llm_service or LLMService(settings.memory_extraction_model)
        self.memory_assembler = memory_assembler or MemoryAssembler()
        self.validation_service = validation_service or ValidationService()

    def ingest_text(
        self,
        request: TextIngestionRequest,
        current_user: CurrentUser,
    ) -> MemoryV1:
        system_context = self._build_system_context(request, current_user)

        if request.media_type != MediaType.TEXT:
            raise UnsupportedMediaTypeError("Only text ingestion is implemented in this milestone.")

        processed = self.text_processor.process(request.text)
        canonical_input = self.canonical_builder.build(
            processed=processed,
            system_context=system_context,
        )
        extraction = self.llm_service.extract_memory(canonical_input)
        memory = self.memory_assembler.assemble(
            system_context=system_context,
            canonical_input=canonical_input,
            extraction=extraction,
            llm_provider="openai-compatible",
            llm_model=self.llm_service.model_name,
        )
        return self.validation_service.validate(memory)

    def ingest_image(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str | None,
        group_id: str | None,
        privacy,
        allowed_users: list[str],
        current_user: CurrentUser,
    ) -> MemoryV1:
        if len(file_bytes) > settings.max_image_size_mb * 1024 * 1024:
            raise FileTooLargeError("Image upload exceeds the configured size limit.")

        system_context = SystemContext(
            owner_id=current_user.id,
            group_id=group_id,
            media_type=MediaType.IMAGE,
            privacy=privacy,
            allowed_users=allowed_users,
        )
        processed = self.image_processor.process(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
        )
        canonical_input = self.canonical_builder.build(
            processed=processed,
            system_context=system_context,
        )
        extraction = self.llm_service.extract_memory(canonical_input)
        memory = self.memory_assembler.assemble(
            system_context=system_context,
            canonical_input=canonical_input,
            extraction=extraction,
            llm_provider="openai-compatible",
            llm_model=self.llm_service.model_name,
        )
        return self.validation_service.validate(memory)

    def ingest_audio(
        self,
        file_path,
        group_id: str | None,
        privacy,
        allowed_users: list[str],
        current_user: CurrentUser,
    ) -> MemoryV1:
        if file_path.stat().st_size > settings.max_audio_size_mb * 1024 * 1024:
            raise FileTooLargeError("Audio upload exceeds the configured size limit.")
        system_context = SystemContext(
            owner_id=current_user.id, group_id=group_id, media_type=MediaType.AUDIO,
            privacy=privacy, allowed_users=allowed_users,
        )
        processed = self.audio_processor.process(file_path)
        canonical_input = self.canonical_builder.build(processed=processed, system_context=system_context)
        extraction = self.llm_service.extract_memory(canonical_input)
        memory = self.memory_assembler.assemble(
            system_context=system_context, canonical_input=canonical_input,
            extraction=extraction, llm_provider="openai-compatible", llm_model=self.llm_service.model_name,
        )
        return self.validation_service.validate(memory)

    def _build_system_context(
        self,
        request: TextIngestionRequest,
        current_user: CurrentUser,
    ) -> SystemContext:
        return SystemContext(
            owner_id=current_user.id,
            group_id=request.group_id,
            media_type=request.media_type,
            privacy=request.privacy,
            allowed_users=request.allowed_users,
        )
