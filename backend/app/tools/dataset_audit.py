"""MindMesh Dataset Coverage & Deterministic Deduplication Audit Tool.

Inspects all 91 dataset rows (33 Image, 33 Text, 25 Audio) against PostgreSQL
database records (raw_inputs and phase1_outputs) using deterministic matching rules.
"""

import asyncio
import os
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
from app.database.connection.session import create_async_engine_instance
from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.raw_input import RawInputModel
from app.tools.dataset_runner import DatasetSample, parse_dataset_manifest


def get_dataset_samples(
    csv_path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> list[DatasetSample]:
    """Parse all 91 dataset samples."""
    return parse_dataset_manifest(csv_path, base_dir)


async def perform_dataset_audit(
    database_url: str | None = None,
    csv_path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Perform deterministic matching of 91 dataset rows against DB records."""
    samples = get_dataset_samples(csv_path, base_dir)
    db_url = database_url or settings.database_url

    engine = create_async_engine_instance(database_url=db_url)

    async with engine.connect() as conn:
        from sqlalchemy.ext.asyncio import AsyncSession
        session = AsyncSession(bind=conn)

        # Fetch all raw_inputs with joined phase1_outputs
        stmt = (
            select(RawInputModel)
            .options(selectinload(RawInputModel.phase1_outputs))
            .order_by(RawInputModel.received_at.asc())
        )
        result = await session.execute(stmt)
        all_raw_inputs = result.scalars().all()

    # Index database records for fast deterministic lookup
    # 1. Text records: normalized raw_payload -> list of (raw_input, phase1_output)
    text_records: dict[str, list[tuple[RawInputModel, Phase1OutputModel]]] = {}
    # 2. Media records: filename -> list of (raw_input, phase1_output)
    media_records: dict[str, list[tuple[RawInputModel, Phase1OutputModel]]] = {}

    manual_test_records: list[tuple[RawInputModel, Phase1OutputModel | None]] = []
    total_phase1_outputs_count = 0

    for raw in all_raw_inputs:
        phase1_out = raw.phase1_outputs[0] if raw.phase1_outputs else None
        if phase1_out:
            total_phase1_outputs_count += len(raw.phase1_outputs)

        if raw.media_type == "text":
            norm_text = raw.raw_payload.strip()
            if norm_text not in text_records:
                text_records[norm_text] = []
            if phase1_out:
                text_records[norm_text].append((raw, phase1_out))
            else:
                manual_test_records.append((raw, None))

        elif raw.media_type in ("image", "audio"):
            struct = raw.structured_payload or {}
            orig_fname = struct.get("original_filename") or struct.get("filename")
            
            # If filename not in structured payload, extract from raw_payload string
            if not orig_fname:
                import re
                match = re.search(r"filename=([^\s,]+)", raw.raw_payload)
                if match:
                    orig_fname = match.group(1)

            if orig_fname:
                norm_fname = Path(orig_fname).name
                if norm_fname not in media_records:
                    media_records[norm_fname] = []
                if phase1_out:
                    media_records[norm_fname].append((raw, phase1_out))
                else:
                    manual_test_records.append((raw, None))
            else:
                manual_test_records.append((raw, phase1_out))

    # Audit each of the 91 dataset samples
    audit_rows: list[dict[str, Any]] = []
    already_present_count = 0
    missing_count = 0
    failed_count = 0
    matched_raw_ids: set[str] = set()
    matched_phase1_ids: set[str] = set()

    for sample in samples:
        sample_id = sample.sample_id
        modality = sample.modality
        status = "MISSING"
        raw_id = None
        phase1_id = None
        context_verified = False

        if modality == "text":
            identifier = (sample.text_content[:45] + "...") if sample.text_content and len(sample.text_content) > 45 else str(sample.text_content)
            norm_text = sample.text_content.strip() if sample.text_content else ""

            matches = text_records.get(norm_text, [])
            # Also check partial/whitespace stripped matches if exact key not found
            if not matches:
                for k, v in text_records.items():
                    if k.strip() == norm_text:
                        matches = v
                        break

            if matches:
                valid_match = next((m for m in matches if m[1].processing_status == "completed"), None)
                if valid_match:
                    raw_rec, p1_rec = valid_match
                    status = "ALREADY_PRESENT"
                    raw_id = str(raw_rec.id)
                    phase1_id = str(p1_rec.id)
                    matched_raw_ids.add(raw_id)
                    matched_phase1_ids.add(phase1_id)
                    already_present_count += 1
                else:
                    status = "FAILED_OR_INCOMPLETE"
                    raw_rec, p1_rec = matches[0]
                    raw_id = str(raw_rec.id)
                    phase1_id = str(p1_rec.id) if p1_rec else None
                    failed_count += 1
            else:
                status = "MISSING"
                missing_count += 1

        elif modality == "image":
            filename = Path(sample.media_relative_path).name if sample.media_relative_path else f"sample_{sample_id}.jpg"
            identifier = filename

            matches = media_records.get(filename, [])
            if matches:
                valid_match = next((m for m in matches if m[1].processing_status == "completed"), None)
                if valid_match:
                    raw_rec, p1_rec = valid_match
                    status = "ALREADY_PRESENT"
                    raw_id = str(raw_rec.id)
                    phase1_id = str(p1_rec.id)
                    matched_raw_ids.add(raw_id)
                    matched_phase1_ids.add(phase1_id)
                    already_present_count += 1

                    # Check context preservation
                    struct = raw_rec.structured_payload or {}
                    saved_ctx = struct.get("user_context")
                    if sample.ground_truth_caption:
                        context_verified = (saved_ctx == sample.ground_truth_caption)
                    else:
                        context_verified = True
                else:
                    status = "FAILED_OR_INCOMPLETE"
                    raw_rec, p1_rec = matches[0]
                    raw_id = str(raw_rec.id)
                    phase1_id = str(p1_rec.id) if p1_rec else None
                    failed_count += 1
            else:
                status = "MISSING"
                missing_count += 1

        elif modality == "audio":
            filename = Path(sample.media_relative_path).name if sample.media_relative_path else f"sample_{sample_id}.audio"
            identifier = filename

            matches = media_records.get(filename, [])
            if matches:
                valid_match = next((m for m in matches if m[1].processing_status == "completed"), None)
                if valid_match:
                    raw_rec, p1_rec = valid_match
                    status = "ALREADY_PRESENT"
                    raw_id = str(raw_rec.id)
                    phase1_id = str(p1_rec.id)
                    matched_raw_ids.add(raw_id)
                    matched_phase1_ids.add(phase1_id)
                    already_present_count += 1
                else:
                    status = "FAILED_OR_INCOMPLETE"
                    raw_rec, p1_rec = matches[0]
                    raw_id = str(raw_rec.id)
                    phase1_id = str(p1_rec.id) if p1_rec else None
                    failed_count += 1
            else:
                status = "MISSING"
                missing_count += 1

        audit_rows.append({
            "row_index": sample_id,
            "modality": modality,
            "identifier": identifier,
            "status": "MATCHED" if status == "ALREADY_PRESENT" else status,
            "raw_input_id": raw_id,
            "phase1_output_id": phase1_id,
            "duplicate_count": max(0, len(matches) - 1) if matches else 0,
            "context_verified": context_verified,
        })

    # Non-dataset records (manual iPhone tests, etc.)
    non_dataset_phase1_count = total_phase1_outputs_count - len(matched_phase1_ids)
    total_duplicate_dataset_rows = sum(1 for r in audit_rows if r["duplicate_count"] > 0)

    return {
        "total_dataset_rows": len(samples),
        "matched_dataset_rows": already_present_count,
        "missing_dataset_rows": missing_count,
        "failed_dataset_rows": failed_count,
        "duplicate_dataset_rows": total_duplicate_dataset_rows,
        "dataset_coverage": f"{already_present_count}/{len(samples)}",
        "total_db_phase1_records": total_phase1_outputs_count,
        "non_dataset_records_count": non_dataset_phase1_count,
        "audit_rows": audit_rows,
    }


def print_audit_report(result: dict[str, Any]) -> None:
    """Print clean formatted Markdown table and summary of the audit."""
    print("=" * 95)
    print("                      MINDMESH DATASET COVERAGE & AUDIT REPORT")
    print("=" * 95)
    print(f"Total Dataset Rows In Manifest       : {result['total_dataset_rows']}")
    print(f"Matched Dataset Rows                 : {result['matched_dataset_rows']}")
    print(f"Missing Dataset Rows                 : {result['missing_dataset_rows']}")
    print(f"Duplicate Dataset Rows               : {result['duplicate_dataset_rows']}")
    print(f"Dataset Coverage                     : {result['dataset_coverage']}")
    print(f"Total Completed Phase 1 Rows In DB   : {result['total_db_phase1_records']}")
    print(f"Non-Dataset / Manual iPhone Test Rows: {result['non_dataset_records_count']}")
    print("-" * 95)
    print("| Row | Modality | Dataset Identifier | Status | raw_input_id | phase1_output_id | Duplicates |")
    print("| :---: | :---: | :--- | :---: | :---: | :---: | :---: |")
    for r in result["audit_rows"]:
        raw_id_short = r["raw_input_id"][:8] + "..." if r["raw_input_id"] else "—"
        p1_id_short = r["phase1_output_id"][:8] + "..." if r["phase1_output_id"] else "—"
        print(f"| {r['row_index']:02d} | {r['modality'].upper():5s} | {r['identifier']:35s} | {r['status']:7s} | {raw_id_short:12s} | {p1_id_short:12s} | {r['duplicate_count']:10d} |")
    print("=" * 95)



if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else None
    res = asyncio.run(perform_dataset_audit(database_url=db_url))
    print_audit_report(res)
