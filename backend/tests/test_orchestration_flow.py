import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.routes.memories import get_ingestion_service
from app.core.enums import MediaType, Privacy
from app.core.errors import EmptyTextError
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.raw_input_repo import RawInputRepository
from app.main import app
from app.orchestration.orchestrator import MindMeshOrchestrator
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.services.audio_processor import AudioProcessor
from app.services.image_processor import ImageProcessor
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService
from app.services.whisper_service import WhisperService
from app.storage.file_storage import FileStorage


@pytest.mark.asyncio
async def test_orchestrator_successful_text_flow(db_session):
    """Verify happy path: raw input stored -> Phase 1 executed -> phase1 output stored -> status completed."""
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        ingestion_service = IngestionService(
            llm_service=LLMService(model_name="mock-memory-extractor")
        )

        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
        )

        hook_called = []
        async def dummy_hook(memory, raw_input, phase1_output):
            hook_called.append(memory.memory_id)

        orchestrator.register_post_phase1_hook(dummy_hook)

        request = TextIngestionRequest(
            text="Had amazing coffee with Akshat at Cafe Bodega in Goa.",
            group_id="G04",
            privacy=Privacy.GROUP,
        )
        current_user = CurrentUser(id="U17")

        custom_input_id = uuid.uuid4()
        memory = await orchestrator.process_text_ingestion(
            request=request,
            current_user=current_user,
            input_id=custom_input_id,
        )
        await session.commit()

        assert memory.schema_version == "1.0"
        assert memory.system.owner_id == "U17"
        assert memory.media is None
        assert len(hook_called) == 1
        assert hook_called[0] == memory.memory_id

    # Verify persistence in database
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)

        # 1. Raw input is completed
        raw_record = await raw_repo.get_by_id(custom_input_id)
        assert raw_record is not None
        assert raw_record.raw_payload == request.text
        assert raw_record.status == "completed"
        assert raw_record.error_message is None

        # 2. Phase 1 output is persisted and linked to raw_record.id
        outputs = await phase1_repo.get_by_raw_input_id(custom_input_id)
        assert len(outputs) == 1
        assert outputs[0].memory_id == memory.memory_id
        assert outputs[0].payload["content"]["clean_text"] == request.text
        assert outputs[0].payload.get("media") is None


@pytest.mark.asyncio
async def test_orchestrator_failure_resilience(db_session):
    """Verify failure path: raw input preserved with status='failed', NO phase1_outputs created."""
    custom_input_id = uuid.uuid4()
    
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        
        # IngestionService will raise EmptyTextError on whitespace-only text
        ingestion_service = IngestionService(
            llm_service=LLMService(model_name="mock-memory-extractor")
        )

        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
        )

        invalid_request = TextIngestionRequest(
            text="   ",
            group_id="G04",
            privacy=Privacy.ONLY_ME,
        )
        current_user = CurrentUser(id="U_FAIL_USER")

        with pytest.raises(EmptyTextError):
            await orchestrator.process_text_ingestion(
                request=invalid_request,
                current_user=current_user,
                input_id=custom_input_id,
            )
        await session.commit()

    # Verify database state after failure
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)

        # 1. Raw input MUST STILL EXIST and be marked failed
        raw_record = await raw_repo.get_by_id(custom_input_id)
        assert raw_record is not None
        assert raw_record.raw_payload == "   "
        assert raw_record.status == "failed"
        assert "EmptyTextError" in raw_record.error_message

        # 2. NO Phase 1 output should exist for this failed input
        outputs = await phase1_repo.get_by_raw_input_id(custom_input_id)
        assert len(outputs) == 0


def test_api_endpoint_persists_raw_and_phase1_output():
    """Verify that calling the FastAPI HTTP endpoint executes the full orchestrated persistence."""
    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
        llm_service=LLMService(model_name="mock-memory-extractor")
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/memories/ingest",
        json={
            "media_type": "text",
            "text": "Yesterday I met Rohan and Akshat at Blue Tokai in Indiranagar.",
            "group_id": "G_ARCHITECTURE",
            "privacy": "ONLY_ME",
            "allowed_users": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.0"
    assert payload["system"]["owner_id"] == "U_DEVELOPMENT"
    assert "Rohan" in payload["entities"]["people"]
    assert response.headers.get("X-Raw-Input-Id") is not None
    assert response.headers.get("X-Phase1-Output-Id") is not None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_exact_multiline_text_preservation(db_session):
    """Verify raw_inputs.raw_payload preserves exact whitespace and newlines, while Phase 1 produces normalized clean_text."""
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        ingestion_service = IngestionService(
            llm_service=LLMService(model_name="mock-memory-extractor")
        )
        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
        )

        multiline_text = "Hello   MindMesh\nThis is a database boundary test."
        request = TextIngestionRequest(
            text=multiline_text,
            privacy=Privacy.ONLY_ME,
        )
        current_user = CurrentUser(id="U_MULTILINE")
        result = await orchestrator.process_text_ingestion_result(request, current_user)
        await session.commit()

        # Clean text normalized by Phase 1
        assert result.memory.content.clean_text == "Hello MindMesh This is a database boundary test."

    # Raw database record preserves verbatim multiline text
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        persisted = await raw_repo.get_by_id(result.raw_input_id)
        assert persisted is not None
        assert persisted.raw_payload == multiline_text


@pytest.mark.asyncio
async def test_orchestrator_db_boundary_enforcement(db_session):
    """Prove that Phase 1 receives input derived strictly from the database record, not original request."""
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        ingestion_service = IngestionService(
            llm_service=LLMService(model_name="mock-memory-extractor")
        )

        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
        )

        # Mock the get_by_id method to return a record with modified text and client_id
        original_get_by_id = raw_repo.get_by_id
        db_persisted_override_text = "This text came strictly from the PostgreSQL database read."
        db_persisted_user_id = "U_FROM_POSTGRESQL"

        async def mocked_get_by_id(input_id):
            real_record = await original_get_by_id(input_id)
            # Mutate record to simulate DB-side transformation
            real_record.raw_payload = db_persisted_override_text
            real_record.client_id = db_persisted_user_id
            return real_record

        raw_repo.get_by_id = mocked_get_by_id

        request = TextIngestionRequest(
            text="Original in-memory request text that should NOT reach Phase 1 directly",
            group_id="G_TEST",
            privacy=Privacy.ONLY_ME,
        )
        current_user = CurrentUser(id="U_ORIGINAL_CALLER")

        result = await orchestrator.process_text_ingestion_result(request, current_user)
        await session.commit()

        # Phase 1 MUST have processed the DB record value, NOT the original request
        assert result.memory.content.clean_text == db_persisted_override_text
        assert result.memory.system.owner_id == db_persisted_user_id
        assert result.memory.content.clean_text != request.text


@pytest.mark.asyncio
async def test_orchestrator_image_file_storage_and_db_flow(tmp_path, db_session):
    """Verify image upload -> FileStorage -> raw_inputs WRITE -> READ -> Phase 1 -> phase1_outputs."""
    storage = FileStorage(base_dir=tmp_path / "media_store")
    
    # Mock image processor to avoid live vision endpoint calls
    class MockImageProcessor(ImageProcessor):
        def _describe_image(self, file_bytes: bytes, content_type: str) -> str:
            return "A photograph of Vagator Beach cliffs at sunset with orange sky."

    image_proc = MockImageProcessor()
    ingestion_service = IngestionService(
        image_processor=image_proc,
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )

    fake_png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    custom_input_id = uuid.uuid4()
    current_user = CurrentUser(id="U_IMAGE_AUTHOR")

    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
            file_storage=storage,
        )

        result = await orchestrator.process_image_ingestion_result(
            file_bytes=fake_png_bytes,
            filename="beach_vacation.png",
            content_type="image/png",
            group_id="G_HOLIDAYS",
            privacy=Privacy.SELECTED,
            allowed_users=["U_FRIEND"],
            current_user=current_user,
            input_id=custom_input_id,
        )
        await session.commit()

        assert result.raw_input_id == custom_input_id
        assert result.memory.system.media_type == MediaType.IMAGE
        assert "Vagator Beach" in result.memory.content.clean_text
        
        # Verify MemoryV1 contains the original media reference
        assert result.memory.media is not None
        assert result.memory.media.media_type == "image"
        assert result.memory.media.original_filename == "beach_vacation.png"
        assert result.memory.media.content_type == "image/png"
        assert result.memory.media.size_bytes == len(fake_png_bytes)
        assert result.memory.media.sha256 is not None
        assert result.memory.media.storage_key is not None

    # 1. Verify FileStorage persistence and file existence on disk
    stored_key = result.raw_input_id
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)

        raw_rec = await raw_repo.get_by_id(custom_input_id)
        assert raw_rec is not None
        assert raw_rec.media_type == "image"
        assert raw_rec.status == "completed"

        # Verify structured_payload fields match MemoryV1 media reference
        payload = raw_rec.structured_payload
        assert payload["media_type"] == "image"
        assert payload["original_filename"] == "beach_vacation.png"
        assert payload["content_type"] == "image/png"
        assert payload["size_bytes"] == len(fake_png_bytes)
        assert payload["storage_key"] == result.memory.media.storage_key
        assert payload["relative_path"] == result.memory.media.relative_path
        assert payload["sha256"] == result.memory.media.sha256

        # 2. Verify the original file physically exists on disk and remains intact
        disk_path = storage.get_file_path(payload["relative_path"])
        assert disk_path.exists()
        assert disk_path.is_file()
        assert disk_path.read_bytes() == fake_png_bytes
        assert storage.exists(payload["storage_key"]) is True

        # 3. Verify phase1_outputs persistence carries media reference
        phase1_records = await phase1_repo.get_by_raw_input_id(custom_input_id)
        assert len(phase1_records) == 1
        assert phase1_records[0].memory_id == result.memory.memory_id
        assert phase1_records[0].payload["system"]["media_type"] == "image"
        assert phase1_records[0].payload["media"]["storage_key"] == result.memory.media.storage_key
        assert phase1_records[0].payload["media"]["original_filename"] == "beach_vacation.png"


@pytest.mark.asyncio
async def test_orchestrator_audio_file_storage_and_db_flow(tmp_path, db_session):
    """Verify audio upload -> FileStorage -> raw_inputs WRITE -> READ -> Phase 1 -> phase1_outputs, and file remains."""
    storage = FileStorage(base_dir=tmp_path / "media_store")
    
    def mock_transcribe(fp):
        return {
            "transcript": "Had lunch at Martin's Corner in Betalbatim with Rohan.",
            "language": "en",
            "language_probability": 0.98,
            "duration": 4.2,
            "segments": [],
        }

    whisper_svc = WhisperService(mock_transcriber=mock_transcribe)
    audio_proc = AudioProcessor(whisper_service=whisper_svc)
    ingestion_service = IngestionService(
        audio_processor=audio_proc,
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )

    audio_bytes = b"OggS" + b"\x00" * 48
    custom_input_id = uuid.uuid4()
    current_user = CurrentUser(id="U_AUDIO_AUTHOR")

    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
            file_storage=storage,
        )

        result = await orchestrator.process_audio_ingestion_result(
            file_bytes=audio_bytes,
            filename="martins_corner.m4a",
            content_type="audio/m4a",
            group_id="G_TRIPS",
            privacy=Privacy.ONLY_ME,
            allowed_users=[],
            current_user=current_user,
            input_id=custom_input_id,
        )
        await session.commit()

        assert result.raw_input_id == custom_input_id
        assert result.memory.system.media_type == MediaType.AUDIO
        assert result.memory.processing.transcription_required is True
        assert result.memory.processing.source_modality == MediaType.AUDIO
        assert "Martin's Corner" in result.memory.content.clean_text

        # Verify MemoryV1 contains the original audio media reference
        assert result.memory.media is not None
        assert result.memory.media.media_type == "audio"
        assert result.memory.media.original_filename == "martins_corner.m4a"
        assert result.memory.media.content_type == "audio/m4a"
        assert result.memory.media.size_bytes == len(audio_bytes)
        assert result.memory.media.sha256 is not None
        assert result.memory.media.storage_key is not None

    # Verify storage and DB state
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)

        raw_rec = await raw_repo.get_by_id(custom_input_id)
        assert raw_rec is not None
        assert raw_rec.media_type == "audio"
        assert raw_rec.status == "completed"

        payload = raw_rec.structured_payload
        assert payload["media_type"] == "audio"
        assert payload["original_filename"] == "martins_corner.m4a"
        assert payload["size_bytes"] == len(audio_bytes)
        assert payload["storage_key"] == result.memory.media.storage_key
        assert payload["relative_path"] == result.memory.media.relative_path
        assert payload["sha256"] == result.memory.media.sha256

        # Ensure stored file STILL exists on disk after Whisper temporary files were cleaned up
        disk_path = storage.get_file_path(payload["relative_path"])
        assert disk_path.exists()
        assert disk_path.read_bytes() == audio_bytes

        # Verify phase1_outputs carries media reference and transcript
        phase1_records = await phase1_repo.get_by_raw_input_id(custom_input_id)
        assert len(phase1_records) == 1
        assert phase1_records[0].memory_id == result.memory.memory_id
        assert phase1_records[0].payload["media"]["storage_key"] == result.memory.media.storage_key
        assert phase1_records[0].payload["media"]["original_filename"] == "martins_corner.m4a"
        assert phase1_records[0].payload["content"]["clean_text"] == result.memory.content.clean_text


@pytest.mark.asyncio
async def test_orchestrator_file_storage_failure_prevents_phase1(tmp_path, db_session):
    """Verify that if FileStorage fails, Phase 1 is NEVER invoked and no completed record is written."""
    class BrokenStorage(FileStorage):
        def save_file(self, *args, **kwargs):
            raise IOError("Simulated disk write failure or full disk")

    broken_storage = BrokenStorage(base_dir=tmp_path / "broken_store")
    phase1_called = []

    class TrackedIngestionService(IngestionService):
        def ingest_audio(self, *args, **kwargs):
            phase1_called.append("audio")
            return super().ingest_audio(*args, **kwargs)

    ingestion_service = TrackedIngestionService()
    custom_input_id = uuid.uuid4()

    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
            file_storage=broken_storage,
        )

        with pytest.raises(IOError) as exc_info:
            await orchestrator.process_audio_ingestion_result(
                file_bytes=b"OggS" + b"\x00" * 32,
                filename="test.m4a",
                content_type="audio/m4a",
                group_id=None,
                privacy=Privacy.ONLY_ME,
                allowed_users=[],
                current_user=CurrentUser(id="U_FAIL"),
                input_id=custom_input_id,
            )
        assert "Simulated disk write failure" in str(exc_info.value)

    # Phase 1 was NOT called
    assert len(phase1_called) == 0

    # No completed record created
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        rec = await raw_repo.get_by_id(custom_input_id)
        assert rec is None  # Never reached DB write
        outputs = await phase1_repo.get_by_raw_input_id(custom_input_id)
        assert len(outputs) == 0


@pytest.mark.asyncio
async def test_orchestrator_image_with_user_context_flow(tmp_path, db_session):
    """Verify image upload WITH context: context is in DB, survives DB read, coexists with MediaReference, and enriches MemoryV1."""
    storage = FileStorage(base_dir=tmp_path / "media_store")
    
    class MockImageProcessor(ImageProcessor):
        def _describe_image(self, file_bytes: bytes, content_type: str) -> str:
            return "A photograph of orange sunset sky over the ocean."

    ingestion_service = IngestionService(
        image_processor=MockImageProcessor(),
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )

    fake_png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    custom_input_id = uuid.uuid4()
    current_user = CurrentUser(id="U_IMAGE_AUTHOR")
    user_context = "Goa trip with Rohan at sunset"

    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
            file_storage=storage,
        )

        result = await orchestrator.process_image_ingestion_result(
            file_bytes=fake_png_bytes,
            filename="goa_trip.png",
            content_type="image/png",
            group_id="G_HOLIDAYS",
            privacy=Privacy.ONLY_ME,
            allowed_users=[],
            current_user=current_user,
            context=user_context,
            input_id=custom_input_id,
        )
        await session.commit()

        # Verify MemoryV1 structure has user_context, media, and entities from user_context
        assert result.memory.user_context == user_context
        assert result.memory.content.user_context == user_context
        assert result.memory.media is not None
        assert result.memory.media.original_filename == "goa_trip.png"
        assert result.memory.media.media_type == "image"
        assert "Rohan" in result.memory.entities.people
        assert "Goa" in result.memory.entities.locations

    # Verify persistent database state across DB boundary
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)

        # 1. raw_inputs record stores user_context
        raw_rec = await raw_repo.get_by_id(custom_input_id)
        assert raw_rec is not None
        assert raw_rec.status == "completed"
        assert raw_rec.structured_payload["user_context"] == user_context
        assert "context=Goa trip with Rohan at sunset" in raw_rec.raw_payload

        # 2. phase1_outputs payload carries user_context and MediaReference
        outputs = await phase1_repo.get_by_raw_input_id(custom_input_id)
        assert len(outputs) == 1
        assert outputs[0].payload["user_context"] == user_context
        assert outputs[0].payload["content"]["user_context"] == user_context
        assert outputs[0].payload["media"]["original_filename"] == "goa_trip.png"


@pytest.mark.asyncio
async def test_orchestrator_audio_with_user_context_flow(tmp_path, db_session):
    """Verify audio upload WITH context: context is in DB, coexists with Whisper transcript & MediaReference in MemoryV1."""
    storage = FileStorage(base_dir=tmp_path / "media_store")
    
    def mock_transcribe(fp):
        return {
            "transcript": "I really love the battery life and display quality.",
            "language": "en",
            "language_probability": 0.99,
            "duration": 3.5,
            "segments": [],
        }

    whisper_svc = WhisperService(mock_transcriber=mock_transcribe)
    audio_proc = AudioProcessor(whisper_service=whisper_svc)
    ingestion_service = IngestionService(
        audio_processor=audio_proc,
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )

    audio_bytes = b"OggS" + b"\x00" * 32
    custom_input_id = uuid.uuid4()
    current_user = CurrentUser(id="U_AUDIO_AUTHOR")
    user_context = "My review of the phone I bought in Goa with Rohan"

    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
            file_storage=storage,
        )

        result = await orchestrator.process_audio_ingestion_result(
            file_bytes=audio_bytes,
            filename="phone_review.m4a",
            content_type="audio/m4a",
            group_id=None,
            privacy=Privacy.ONLY_ME,
            allowed_users=[],
            current_user=current_user,
            context=user_context,
            input_id=custom_input_id,
        )
        await session.commit()

        # Verify MemoryV1 carries user_context, transcript, and media
        assert result.memory.user_context == user_context
        assert result.memory.content.user_context == user_context
        assert result.memory.content.raw_text == "I really love the battery life and display quality."
        assert result.memory.media is not None
        assert result.memory.media.original_filename == "phone_review.m4a"
        assert result.memory.media.media_type == "audio"
        assert result.memory.processing.transcription_required is True
        assert "Rohan" in result.memory.entities.people
        assert "Goa" in result.memory.entities.locations

    # Verify database state
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)

        raw_rec = await raw_repo.get_by_id(custom_input_id)
        assert raw_rec is not None
        assert raw_rec.structured_payload["user_context"] == user_context

        outputs = await phase1_repo.get_by_raw_input_id(custom_input_id)
        assert len(outputs) == 1
        assert outputs[0].payload["user_context"] == user_context
        assert outputs[0].payload["content"]["raw_text"] == "I really love the battery life and display quality."
        assert outputs[0].payload["media"]["original_filename"] == "phone_review.m4a"


def test_api_endpoints_accept_optional_context():
    """Verify HTTP API endpoints accept optional context form field for both image and audio."""
    import io
    from app.main import app

    class MockImageProcessor(ImageProcessor):
        def _describe_image(self, file_bytes: bytes, content_type: str) -> str:
            return "Photo of a restaurant table."

    def mock_transcribe(fp):
        return {"transcript": "Delicious dinner.", "language": "en", "duration": 2.0, "segments": []}

    ingestion_service = IngestionService(
        image_processor=MockImageProcessor(),
        audio_processor=AudioProcessor(whisper_service=WhisperService(mock_transcriber=mock_transcribe)),
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )
    app.dependency_overrides[get_ingestion_service] = lambda: ingestion_service
    client = TestClient(app)

    # 1. Image upload with context
    img_resp = client.post(
        "/api/v1/memories/ingest/image",
        data={"media_type": "image", "context": "Dinner in Goa with Rohan"},
        files={"file": ("dinner.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32), "image/png")},
    )
    assert img_resp.status_code == 200
    img_json = img_resp.json()
    assert img_json["user_context"] == "Dinner in Goa with Rohan"
    assert img_json["media"]["original_filename"] == "dinner.png"
    assert "Rohan" in img_json["entities"]["people"]

    # 2. Audio upload with context
    aud_resp = client.post(
        "/api/v1/memories/ingest/audio",
        data={"media_type": "audio", "context": "Quick voice thought in Goa"},
        files={"file": ("note.m4a", io.BytesIO(b"OggS" + b"\x00" * 32), "audio/m4a")},
    )
    assert aud_resp.status_code == 200
    aud_json = aud_resp.json()
    assert aud_json["user_context"] == "Quick voice thought in Goa"
    assert aud_json["content"]["raw_text"] == "Delicious dinner."
    assert aud_json["media"]["original_filename"] == "note.m4a"

    # 3. Audio upload WITHOUT context (backward compatibility)
    aud_no_ctx = client.post(
        "/api/v1/memories/ingest/audio",
        data={"media_type": "audio"},
        files={"file": ("note2.m4a", io.BytesIO(b"OggS" + b"\x00" * 32), "audio/m4a")},
    )
    assert aud_no_ctx.status_code == 200
    assert aud_no_ctx.json()["user_context"] is None

    app.dependency_overrides.clear()



