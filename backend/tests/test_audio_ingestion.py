import io
from pathlib import Path
import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.routes.memories import get_ingestion_service
from app.core.enums import MediaType, Privacy
from app.core.errors import UnsupportedFileFormatError, TranscriptionFailedError
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.raw_input_repo import RawInputRepository
from app.main import app
from app.orchestration.orchestrator import MindMeshOrchestrator
from app.schemas.ingestion_request import CurrentUser
from app.services.audio_processor import AudioProcessor, is_valid_audio_header
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService
from app.services.whisper_service import WhisperService
from app.tools.dataset_runner import calculate_word_error_rate, parse_dataset_manifest


def get_mock_whisper_service(mock_text: str = "Met Rohan and Akshat in Panjim Goa for dinner.") -> WhisperService:
    def mock_transcribe(file_path: Path) -> dict:
        return {
            "transcript": mock_text,
            "language": "en",
            "language_probability": 0.99,
            "duration": 5.4,
            "segments": [{"start": 0.0, "end": 5.4, "text": mock_text}],
        }
    return WhisperService(mock_transcriber=mock_transcribe)


def test_whisper_service_mock():
    """Verify WhisperService with mock transcriber returns correct structure without model download."""
    service = get_mock_whisper_service("Test voice recording")
    # Path does not need to be real for mock transcriber
    res = service.transcribe(Path(__file__))
    assert res["transcript"] == "Test voice recording"
    assert res["language"] == "en"
    assert res["language_probability"] == 0.99
    assert res["duration"] == 5.4
    assert len(res["segments"]) == 1


def test_audio_header_and_bin_validation():
    """Verify magic header validation for audio containers including OggS (.bin files)."""
    ogg_header = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    riff_header = b"RIFF$\x00\x00\x00WAVE"
    id3_header = b"ID3\x03\x00\x00\x00\x00\x00\x00"
    m4a_header = b"\x00\x00\x00\x20ftypM4A "
    invalid_header = b"NOT_AN_AUDIO_FILE_HEADER"

    assert is_valid_audio_header(ogg_header) is True
    assert is_valid_audio_header(riff_header) is True
    assert is_valid_audio_header(id3_header) is True
    assert is_valid_audio_header(m4a_header) is True
    assert is_valid_audio_header(invalid_header) is False


def test_audio_processor_bin_ogg_handling(tmp_path):
    """Verify AudioProcessor decodes .bin file when containing valid Ogg header."""
    ogg_content = b"OggS\x00\x02\x00\x00" + b"\x00" * 60
    bin_file = tmp_path / "voice_note.bin"
    bin_file.write_bytes(ogg_content)

    processor = AudioProcessor(whisper_service=get_mock_whisper_service("Voice note content"))
    processed = processor.process(file_path=bin_file)

    assert processed.media_type == MediaType.AUDIO
    assert processed.raw_text == "Voice note content"
    assert processed.clean_text == "Voice note content"


def test_audio_processor_invalid_format_rejection(tmp_path):
    """Verify AudioProcessor rejects non-audio formats and invalid .bin files."""
    invalid_file = tmp_path / "document.pdf"
    invalid_file.write_bytes(b"%PDF-1.4...")

    processor = AudioProcessor(whisper_service=get_mock_whisper_service())
    with pytest.raises(UnsupportedFileFormatError):
        processor.process(file_path=invalid_file)

    invalid_bin = tmp_path / "random.bin"
    invalid_bin.write_bytes(b"PLAIN_RANDOM_BYTES_WITHOUT_AUDIO_HEADER")
    with pytest.raises(UnsupportedFileFormatError):
        processor.process(file_path=invalid_bin)


def test_ingestion_service_audio_flow():
    """Verify IngestionService.ingest_audio extracts entities and creates valid MemoryV1."""
    whisper = get_mock_whisper_service("Had coffee with Akshat in Goa yesterday.")
    audio_proc = AudioProcessor(whisper_service=whisper)
    ingestion_service = IngestionService(
        audio_processor=audio_proc,
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )

    current_user = CurrentUser(id="U_AUDIO_USER")
    memory = ingestion_service.ingest_audio(
        file_bytes=b"OggS" + b"\x00" * 32,
        filename="recording.m4a",
        content_type="audio/m4a",
        group_id="G_AUDIO",
        privacy=Privacy.SELECTED,
        allowed_users=["U2", "U3"],
        current_user=current_user,
    )

    assert memory.schema_version == "1.0"
    assert memory.system.owner_id == "U_AUDIO_USER"
    assert memory.system.media_type == MediaType.AUDIO
    assert memory.processing.source_modality == MediaType.AUDIO
    assert memory.processing.transcription_required is True
    assert memory.content.clean_text == "Had coffee with Akshat in Goa yesterday."
    assert "Akshat" in memory.entities.people
    assert "Goa" in memory.entities.locations


@pytest.mark.asyncio
async def test_orchestrator_audio_db_first_flow(db_session):
    """Verify complete DB-first lifecycle for audio: raw_inputs WRITE -> READ -> Phase 1 -> phase1_outputs WRITE."""
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        whisper = get_mock_whisper_service("Visited Aguada Fort in North Goa with Rohan.")
        ingestion_service = IngestionService(
            audio_processor=AudioProcessor(whisper_service=whisper),
            llm_service=LLMService(model_name="mock-memory-extractor"),
        )
        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
        )

        custom_input_id = uuid.uuid4()
        audio_bytes = b"OggS" + b"\x00" * 40
        current_user = CurrentUser(id="U_ORCH_AUDIO")

        result = await orchestrator.process_audio_ingestion_result(
            file_bytes=audio_bytes,
            filename="drive_audio_01.m4a",
            content_type="audio/m4a",
            group_id="G_TRIP",
            privacy=Privacy.ONLY_ME,
            allowed_users=[],
            current_user=current_user,
            input_id=custom_input_id,
        )
        await session.commit()

        assert result.memory.system.media_type == MediaType.AUDIO
        assert result.memory.processing.transcription_required is True
        assert result.raw_input_id == custom_input_id
        assert result.memory.media is not None
        assert result.memory.media.original_filename == "drive_audio_01.m4a"
        assert result.memory.media.media_type == "audio"
        assert result.memory.media.size_bytes == len(audio_bytes)

    # Verify persistent database state
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)

        # 1. raw_inputs record is preserved with audio metadata and status completed
        raw_rec = await raw_repo.get_by_id(custom_input_id)
        assert raw_rec is not None
        assert raw_rec.media_type == "audio"
        assert raw_rec.status == "completed"
        assert raw_rec.structured_payload["filename"] == "drive_audio_01.m4a"
        assert raw_rec.structured_payload["size_bytes"] == len(audio_bytes)

        # 2. phase1_outputs is linked via raw_input_id foreign key
        outputs = await phase1_repo.get_by_raw_input_id(custom_input_id)
        assert len(outputs) == 1
        assert outputs[0].id == result.phase1_output_id
        assert outputs[0].memory_id == result.memory.memory_id
        assert outputs[0].payload["processing"]["source_modality"] == "audio"
        assert outputs[0].payload["media"]["original_filename"] == "drive_audio_01.m4a"


@pytest.mark.asyncio
async def test_orchestrator_audio_failure_resilience(db_session):
    """Verify that when audio transcription fails, raw_inputs is preserved with status='failed'."""
    custom_input_id = uuid.uuid4()

    def failing_transcribe(fp: Path):
        raise TranscriptionFailedError("Corrupted audio data decoding error")

    failing_whisper = WhisperService(mock_transcriber=failing_transcribe)

    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        ingestion_service = IngestionService(
            audio_processor=AudioProcessor(whisper_service=failing_whisper),
            llm_service=LLMService(model_name="mock-memory-extractor"),
        )
        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
        )

        with pytest.raises(TranscriptionFailedError):
            await orchestrator.process_audio_ingestion_result(
                file_bytes=b"CORRUPTED_BYTES",
                filename="bad_audio.mp3",
                content_type="audio/mpeg",
                group_id=None,
                privacy=Privacy.ONLY_ME,
                allowed_users=[],
                current_user=CurrentUser(id="U_FAIL"),
                input_id=custom_input_id,
            )
        await session.commit()

    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)

        raw_rec = await raw_repo.get_by_id(custom_input_id)
        assert raw_rec is not None
        assert raw_rec.status == "failed"
        assert "TranscriptionFailedError" in raw_rec.error_message

        outputs = await phase1_repo.get_by_raw_input_id(custom_input_id)
        assert len(outputs) == 0


def test_audio_api_endpoint():
    """Verify POST /api/v1/memories/ingest/audio endpoint with multipart file upload."""
    mock_whisper = get_mock_whisper_service("Tested audio API endpoint in MindMesh.")
    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
        audio_processor=AudioProcessor(whisper_service=mock_whisper),
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )
    client = TestClient(app)

    file_data = io.BytesIO(b"OggS" + b"\x00" * 40)
    response = client.post(
        "/api/v1/memories/ingest/audio",
        data={
            "media_type": "audio",
            "group_id": "G_API_TEST",
            "privacy": "ONLY_ME",
            "allowed_users": "[]",
        },
        files={"file": ("test_audio.m4a", file_data, "audio/m4a")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.0"
    assert payload["system"]["media_type"] == "audio"
    assert payload["processing"]["source_modality"] == "audio"
    assert payload["processing"]["transcription_required"] is True
    assert response.headers.get("X-Raw-Input-Id") is not None
    assert response.headers.get("X-Phase1-Output-Id") is not None
    app.dependency_overrides.clear()


def test_dataset_manifest_parser_counts():
    """Verify parse_dataset_manifest correctly parses the 91 dataset rows."""
    samples = parse_dataset_manifest()
    assert len(samples) == 91

    text_samples = [s for s in samples if s.modality == "text"]
    image_samples = [s for s in samples if s.modality == "image"]
    audio_samples = [s for s in samples if s.modality == "audio"]

    assert len(text_samples) == 33
    assert len(image_samples) == 33
    assert len(audio_samples) == 25


def test_wer_metric_calculation():
    """Verify calculate_word_error_rate behaves correctly."""
    ref = "if you are going to goa definitely visit panjim"
    hyp_exact = "if you are going to goa definitely visit panjim"
    hyp_diff = "if you are heading to goa definitely visit panjim"

    assert calculate_word_error_rate(ref, hyp_exact) == 0.0
    wer = calculate_word_error_rate(ref, hyp_diff)
    assert 0.0 < wer < 0.2
