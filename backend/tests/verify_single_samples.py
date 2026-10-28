"""Incrementally verifies single real samples from the multimodal dataset:
1. One real TEXT sample
2. One real IMAGE sample
3. One real AUDIO sample (.m4a)
4. One real AUDIO (.bin / Ogg Opus) sample
Verifying DB-first flow, raw_inputs persistence, Phase 1 extraction, and phase1_outputs FK linkage.
"""

import asyncio
import io
import json
import os
from pathlib import Path
import sys

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set stdout to UTF-8
sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
from app.core.enums import MediaType, Privacy
from app.database.models.base import Base
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.raw_input_repo import RawInputRepository
from app.orchestration.orchestrator import MindMeshOrchestrator
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.services.audio_processor import AudioProcessor
from app.services.image_processor import ImageProcessor
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService
from app.services.whisper_service import WhisperService
from app.tools.dataset_runner import parse_dataset_manifest

DATASET_CSV = r"C:\Users\mehul\OneDrive\Desktop\Archive\combined_form_responses_local.csv"
DATASET_BASE = r"C:\Users\mehul\OneDrive\Desktop\Archive"


async def main():
    print("==================================================")
    print("MINDMESH PHASE 1 - SINGLE SAMPLE INCREMENTAL TEST")
    print("==================================================")

    # 1. Initialize in-memory SQLite DB for isolated end-to-end verification
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Parse dataset manifest
    samples = parse_dataset_manifest(DATASET_CSV, DATASET_BASE)
    print(f"Total manifest samples discovered: {len(samples)}")
    text_samples = [s for s in samples if s.modality == "text"]
    image_samples = [s for s in samples if s.modality == "image"]
    audio_samples = [s for s in samples if s.modality == "audio"]
    print(f"Counts: Text={len(text_samples)}, Image={len(image_samples)}, Audio={len(audio_samples)}")

    # 3. Setup services
    whisper = WhisperService()
    audio_processor = AudioProcessor(whisper_service=whisper)

    # Use live ImageProcessor if configured, otherwise fallback to mock descriptor
    if settings.openai_compatible_base_url and settings.image_understanding_model != "to-be-decided":
        image_processor = ImageProcessor()
        print(f"Using live ImageProcessor with model: {settings.image_understanding_model}")
    else:
        class MockImageProcessor(ImageProcessor):
            def _describe_image(self, file_bytes: bytes, content_type: str) -> str:
                return "A cozy restaurant scene with warm wooden interiors, hanging pendant lights, Japanese style decor, and seating tables."
        image_processor = MockImageProcessor()
        print("Using MockImageProcessor (live vision endpoint not configured in environment)")

    ingestion_service = IngestionService(
        audio_processor=audio_processor,
        image_processor=image_processor,
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )

    async with session_maker() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)
        orchestrator = MindMeshOrchestrator(
            raw_input_repo=raw_repo,
            phase1_output_repo=phase1_repo,
            ingestion_service=ingestion_service,
        )

        user = CurrentUser(id="U_VERIFICATION_USER")

        # ==================================================
        # TEST 1: Real TEXT Sample (Row 33)
        # ==================================================
        print("\n--- TEST 1: Real TEXT Sample ---")
        sample_text = text_samples[0]
        print(f"Sample ID: {sample_text.sample_id}, Text: {sample_text.text_content[:60]}...")
        text_req = TextIngestionRequest(text=sample_text.text_content, privacy=Privacy.ONLY_ME)
        res_text = await orchestrator.process_text_ingestion_result(text_req, user)
        await session.commit()

        # DB verification
        raw_text_rec = await raw_repo.get_by_id(res_text.raw_input_id)
        phase1_text_rec = await phase1_repo.get_by_id(res_text.phase1_output_id)
        assert raw_text_rec.status == "completed"
        assert phase1_text_rec.raw_input_id == raw_text_rec.id
        print(f"✓ TEXT Result: Memory ID = {res_text.memory.memory_id}")
        print(f"  raw_input_id: {res_text.raw_input_id}, status: {raw_text_rec.status}")
        print(f"  phase1_output_id: {res_text.phase1_output_id}")
        print(f"  Extracted People: {res_text.memory.entities.people}, Places: {res_text.memory.entities.places}")

        # ==================================================
        # TEST 2: Real IMAGE Sample (Row 0)
        # ==================================================
        print("\n--- TEST 2: Real IMAGE Sample ---")
        sample_img = image_samples[0]
        print(f"Sample ID: {sample_img.sample_id}, File: {sample_img.media_relative_path}")
        img_bytes = sample_img.media_absolute_path.read_bytes()
        res_img = await orchestrator.process_image_ingestion_result(
            file_bytes=img_bytes,
            filename=sample_img.media_absolute_path.name,
            content_type="image/jpeg",
            group_id=None,
            privacy=Privacy.ONLY_ME,
            allowed_users=[],
            current_user=user,
        )
        await session.commit()

        raw_img_rec = await raw_repo.get_by_id(res_img.raw_input_id)
        phase1_img_rec = await phase1_repo.get_by_id(res_img.phase1_output_id)
        assert raw_img_rec.status == "completed"
        assert phase1_img_rec.raw_input_id == raw_img_rec.id
        print(f"✓ IMAGE Result: Memory ID = {res_img.memory.memory_id}")
        print(f"  raw_input_id: {res_img.raw_input_id}, status: {raw_img_rec.status}")
        print(f"  phase1_output_id: {res_img.phase1_output_id}")
        print(f"  Clean Text Description: {res_img.memory.content.clean_text[:70]}...")

        # ==================================================
        # TEST 3: Real AUDIO Sample (.m4a) (Row 67 or 69)
        # ==================================================
        print("\n--- TEST 3: Real AUDIO Sample (.m4a) ---")
        # Find first .m4a audio sample
        m4a_sample = next(s for s in audio_samples if str(s.media_relative_path).endswith(".m4a"))
        print(f"Sample ID: {m4a_sample.sample_id}, File: {m4a_sample.media_relative_path}")
        audio_bytes_m4a = m4a_sample.media_absolute_path.read_bytes()
        res_audio_m4a = await orchestrator.process_audio_ingestion_result(
            file_bytes=audio_bytes_m4a,
            filename=m4a_sample.media_absolute_path.name,
            content_type="audio/m4a",
            group_id=None,
            privacy=Privacy.ONLY_ME,
            allowed_users=[],
            current_user=user,
        )
        await session.commit()

        raw_audio_rec = await raw_repo.get_by_id(res_audio_m4a.raw_input_id)
        phase1_audio_rec = await phase1_repo.get_by_id(res_audio_m4a.phase1_output_id)
        assert raw_audio_rec.status == "completed"
        assert phase1_audio_rec.raw_input_id == raw_audio_rec.id
        print(f"✓ AUDIO (.m4a) Result: Memory ID = {res_audio_m4a.memory.memory_id}")
        print(f"  raw_input_id: {res_audio_m4a.raw_input_id}, status: {raw_audio_rec.status}")
        print(f"  phase1_output_id: {res_audio_m4a.phase1_output_id}")
        print(f"  Transcript: {res_audio_m4a.memory.content.clean_text[:80]}...")
        if m4a_sample.ground_truth_caption:
            print(f"  Ground Truth: {m4a_sample.ground_truth_caption[:80]}...")

        # ==================================================
        # TEST 4: Real AUDIO .bin (Ogg Opus) Sample (Row 66)
        # ==================================================
        print("\n--- TEST 4: Real AUDIO .bin (Ogg Opus) Sample ---")
        bin_sample = next(s for s in audio_samples if str(s.media_relative_path).endswith(".bin"))
        print(f"Sample ID: {bin_sample.sample_id}, File: {bin_sample.media_relative_path}")
        audio_bytes_bin = bin_sample.media_absolute_path.read_bytes()
        print(f"  Header magic: {audio_bytes_bin[:4]}")
        res_audio_bin = await orchestrator.process_audio_ingestion_result(
            file_bytes=audio_bytes_bin,
            filename=bin_sample.media_absolute_path.name,
            content_type="audio/ogg",
            group_id=None,
            privacy=Privacy.ONLY_ME,
            allowed_users=[],
            current_user=user,
        )
        await session.commit()

        raw_bin_rec = await raw_repo.get_by_id(res_audio_bin.raw_input_id)
        phase1_bin_rec = await phase1_repo.get_by_id(res_audio_bin.phase1_output_id)
        assert raw_bin_rec.status == "completed"
        assert phase1_bin_rec.raw_input_id == raw_bin_rec.id
        print(f"✓ AUDIO (.bin) Result: Memory ID = {res_audio_bin.memory.memory_id}")
        print(f"  raw_input_id: {res_audio_bin.raw_input_id}, status: {raw_bin_rec.status}")
        print(f"  phase1_output_id: {res_audio_bin.phase1_output_id}")
        print(f"  Transcript: {res_audio_bin.memory.content.clean_text[:80]}...")

    await engine.dispose()
    print("\n==================================================")
    print("ALL INCREMENTAL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
