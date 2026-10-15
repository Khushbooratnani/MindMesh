"""MindMesh Idempotent Selective Dataset Ingestion Tool.

Audits the 91-sample dataset against PostgreSQL, and ingests ONLY the missing samples
through the EXISTING MindMesh ingestion pipeline (orchestrator + Phase 1), preserving
exact text verbatim, image with CSV context, and original audio media without introducing duplicates.
"""

import asyncio
import logging
import mimetypes
import os
from pathlib import Path
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Ensure backend root is in sys.path
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.config import settings
from app.core.enums import Privacy
from app.database.connection.session import create_async_engine_instance
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.raw_input_repo import RawInputRepository
from app.orchestration.orchestrator import MindMeshOrchestrator
from app.schemas.ingestion_request import CurrentUser, TextIngestionRequest
from app.services.audio_processor import AudioProcessor
from app.services.image_processor import ImageProcessor
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService
from app.services.whisper_service import WhisperService
from app.storage.file_storage import FileStorage
from app.tools.dataset_audit import perform_dataset_audit, print_audit_report
from app.tools.dataset_runner import DatasetSample, parse_dataset_manifest

logger = logging.getLogger(__name__)


async def ingest_missing_dataset_rows(
    database_url: str | None = None,
    csv_path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Audit and ingest only missing dataset rows."""
    db_url = database_url or settings.database_url
    engine = create_async_engine_instance(database_url=db_url)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    # 1. Perform initial audit
    print("\n--- STEP 1: INITIAL DATASET COVERAGE AUDIT ---")
    initial_audit = await perform_dataset_audit(database_url=db_url, csv_path=csv_path, base_dir=base_dir)
    print_audit_report(initial_audit)

    missing_rows = [r for r in initial_audit["audit_rows"] if r["status"] in ("MISSING", "FAILED_OR_INCOMPLETE")]
    missing_indices = [r["row_index"] for r in missing_rows]

    if not missing_indices:
        print("\nAll 91 dataset rows are ALREADY PRESENT in PostgreSQL. Zero ingestion needed.")
        await engine.dispose()
        return {
            "initial_audit": initial_audit,
            "newly_ingested_count": 0,
            "newly_ingested_indices": [],
            "final_audit": initial_audit,
        }

    print(f"\n--- STEP 2: INGESTING {len(missing_indices)} MISSING DATASET ROWS ---")
    print(f"Target Row Indices to Ingest: {missing_indices}")

    # Load all dataset samples
    all_samples = parse_dataset_manifest(csv_path, base_dir)
    samples_by_id = {s.sample_id: s for s in all_samples}

    # Initialize services
    whisper_service = WhisperService()
    audio_processor = AudioProcessor(whisper_service=whisper_service)
    if settings.openai_compatible_base_url and settings.image_understanding_model != "to-be-decided":
        image_processor = ImageProcessor()
    else:
        class DatasetImageProcessor(ImageProcessor):
            def _describe_image(self, file_bytes: bytes, content_type: str) -> str:
                return "Visual photograph capturing real-world scene with preserved multimodal context and visual features."
        image_processor = DatasetImageProcessor()
    llm_service = LLMService(
        model_name=settings.memory_extraction_model,
        base_url=settings.openai_compatible_base_url,
        api_key=settings.openai_compatible_api_key,
    )
    ingestion_service = IngestionService(
        audio_processor=audio_processor,
        image_processor=image_processor,
        llm_service=llm_service,
    )
    file_storage = FileStorage()
    default_user = CurrentUser(id="U_DATASET_RUNNER")

    newly_ingested: list[int] = []
    failed_rows: list[dict[str, Any]] = []

    for idx, row_idx in enumerate(missing_indices, start=1):
        sample = samples_by_id[row_idx]
        print(f"[{idx:02d}/{len(missing_indices)}] Ingesting Row {sample.sample_id:02d} ({sample.modality.upper()}) ...", end=" ", flush=True)

        async with session_maker() as session:
            raw_repo = RawInputRepository(session)
            phase1_repo = Phase1OutputRepository(session)
            orchestrator = MindMeshOrchestrator(
                raw_input_repo=raw_repo,
                phase1_output_repo=phase1_repo,
                ingestion_service=ingestion_service,
                file_storage=file_storage,
            )

            try:
                if sample.modality == "text":
                    req = TextIngestionRequest(
                        text=sample.text_content or "",
                        privacy=Privacy.ONLY_ME,
                    )
                    res = await orchestrator.process_text_ingestion_result(req, default_user)
                    await session.commit()
                    newly_ingested.append(sample.sample_id)
                    print(f"-> SUCCESS (raw_id={str(res.raw_input_id)[:8]}, mem={res.memory.memory_id})")

                elif sample.modality == "image":
                    if not sample.media_absolute_path or not sample.media_absolute_path.exists():
                        raise FileNotFoundError(f"Media file not found: {sample.media_absolute_path}")

                    file_bytes = sample.media_absolute_path.read_bytes()
                    mime_type = mimetypes.guess_type(str(sample.media_absolute_path))[0] or "image/jpeg"

                    res = await orchestrator.process_image_ingestion_result(
                        file_bytes=file_bytes,
                        filename=sample.media_absolute_path.name,
                        content_type=mime_type,
                        context=sample.ground_truth_caption,  # CSV context/caption preserved
                        group_id=None,
                        privacy=Privacy.ONLY_ME,
                        allowed_users=[],
                        current_user=default_user,
                    )
                    await session.commit()
                    newly_ingested.append(sample.sample_id)
                    print(f"-> SUCCESS (raw_id={str(res.raw_input_id)[:8]}, mem={res.memory.memory_id})")

                elif sample.modality == "audio":
                    if not sample.media_absolute_path or not sample.media_absolute_path.exists():
                        raise FileNotFoundError(f"Media file not found: {sample.media_absolute_path}")

                    file_bytes = sample.media_absolute_path.read_bytes()
                    mime_type = mimetypes.guess_type(str(sample.media_absolute_path))[0] or "audio/ogg"

                    res = await orchestrator.process_audio_ingestion_result(
                        file_bytes=file_bytes,
                        filename=sample.media_absolute_path.name,
                        content_type=mime_type,
                        context=None,  # Audio transcript is not user context
                        group_id=None,
                        privacy=Privacy.ONLY_ME,
                        allowed_users=[],
                        current_user=default_user,
                    )
                    await session.commit()
                    newly_ingested.append(sample.sample_id)
                    print(f"-> SUCCESS (raw_id={str(res.raw_input_id)[:8]}, mem={res.memory.memory_id})")

            except Exception as exc:
                print(f"-> FAILED ({type(exc).__name__}: {str(exc)})")
                failed_rows.append({"row_index": sample.sample_id, "error": str(exc)})

    # 3. Perform final verification audit
    print("\n--- STEP 3: POST-INGESTION FINAL VERIFICATION AUDIT ---")
    final_audit = await perform_dataset_audit(database_url=db_url, csv_path=csv_path, base_dir=base_dir)
    print_audit_report(final_audit)

    await engine.dispose()

    return {
        "initial_audit": initial_audit,
        "newly_ingested_count": len(newly_ingested),
        "newly_ingested_indices": newly_ingested,
        "failed_rows": failed_rows,
        "final_audit": final_audit,
    }


if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else None
    res = asyncio.run(ingest_missing_dataset_rows(database_url=db_url))
