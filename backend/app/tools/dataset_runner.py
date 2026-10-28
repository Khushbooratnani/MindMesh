"""Dataset Manifest Parser and Evaluation Runner.

This is a test/validation tool for executing the 91-row multimodal dataset
(33 Text, 33 Image, 25 Audio) as an HTTP test client against the MindMesh
Phase 1 FastAPI API.
"""

import argparse
from dataclasses import asdict, dataclass
import json
import logging
import mimetypes
import os
from pathlib import Path
import sys
from typing import Any

import httpx
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logger = logging.getLogger(__name__)

DEFAULT_DEBIAN_BASE = Path("/home/coeai/mindmesh/data/dataset")
DEFAULT_DEBIAN_CSV = DEFAULT_DEBIAN_BASE / "combined_form_responses_local.csv"

DEFAULT_WINDOWS_BASE = Path(r"C:\Users\mehul\OneDrive\Desktop\Archive")
DEFAULT_WINDOWS_CSV = DEFAULT_WINDOWS_BASE / "combined_form_responses_local.csv"


def get_default_dataset_paths() -> tuple[Path, Path]:
    """Detect appropriate default dataset paths based on OS and filesystem existence."""
    if DEFAULT_DEBIAN_CSV.exists() or Path("/home/coeai").exists():
        return DEFAULT_DEBIAN_CSV, DEFAULT_DEBIAN_BASE
    return DEFAULT_WINDOWS_CSV, DEFAULT_WINDOWS_BASE


@dataclass
class DatasetSample:
    sample_id: int
    modality: str  # "text", "image", "audio"
    timestamp: str | None
    text_content: str | None
    media_relative_path: str | None
    media_absolute_path: Path | None
    ground_truth_caption: str | None
    extra_modalities: list[str]


@dataclass
class EvaluationResult:
    sample_id: int
    modality: str
    input_file_or_text: str
    status: str  # "success", "failed"
    http_status: int | None = None
    raw_input_id: str | None = None
    phase1_output_id: str | None = None
    memory_id: str | None = None
    transcript: str | None = None
    ground_truth: str | None = None
    wer_or_match_metric: float | None = None
    error_message: str | None = None


def parse_dataset_manifest(
    csv_path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> list[DatasetSample]:
    """Parses the CSV manifest and discovers all samples and their modalities."""
    def_csv, def_base = get_default_dataset_paths()
    csv_path = Path(csv_path) if csv_path else def_csv
    base_dir = Path(base_dir) if base_dir else def_base

    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset manifest CSV not found at: {csv_path}")

    df = pd.read_csv(csv_path)
    samples: list[DatasetSample] = []

    for idx, row in df.iterrows():
        timestamp = str(row.get("Timestamp")) if pd.notnull(row.get("Timestamp")) else None
        image_val = row.get("image") if pd.notnull(row.get("image")) else None
        caption_val = row.get("caption") if pd.notnull(row.get("caption")) else None
        text_val = row.get("text input") if pd.notnull(row.get("text input")) else None
        audio_val = row.get("audio") if pd.notnull(row.get("audio")) else None

        active_modalities = []
        if image_val:
            active_modalities.append("image")
        if audio_val:
            active_modalities.append("audio")
        if text_val:
            active_modalities.append("text")

        # Determine primary modality deterministically
        if image_val:
            primary_modality = "image"
            media_rel = str(image_val)
            media_abs = base_dir / media_rel.replace("/", os.sep)
            text_input = None
            gt = str(caption_val) if caption_val else None
        elif audio_val:
            primary_modality = "audio"
            media_rel = str(audio_val)
            media_abs = base_dir / media_rel.replace("/", os.sep)
            text_input = None
            gt = str(caption_val) if caption_val else None
        elif text_val:
            primary_modality = "text"
            media_rel = None
            media_abs = None
            text_input = str(text_val)
            gt = str(text_val)
        else:
            logger.warning("Row %d has no identifiable modality, skipping", idx)
            continue

        extra = [m for m in active_modalities if m != primary_modality]

        samples.append(
            DatasetSample(
                sample_id=idx,
                modality=primary_modality,
                timestamp=timestamp,
                text_content=text_input,
                media_relative_path=media_rel,
                media_absolute_path=media_abs,
                ground_truth_caption=gt,
                extra_modalities=extra,
            )
        )

    return samples


def calculate_word_error_rate(reference: str, hypothesis: str) -> float:
    """Calculate simple Word Error Rate (WER) using Levenshtein distance on word tokens."""
    ref_words = reference.lower().strip().split()
    hyp_words = hypothesis.lower().strip().split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    dp = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]

    for i in range(len(ref_words) + 1):
        dp[i][0] = i
    for j in range(len(hyp_words) + 1):
        dp[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # deletion
                    dp[i][j - 1],      # insertion
                    dp[i - 1][j - 1],  # substitution
                )

    return float(dp[len(ref_words)][len(hyp_words)]) / len(ref_words)


def run_dataset_via_api(
    api_base_url: str = "http://127.0.0.1:8001",
    csv_path: str | Path | None = None,
    base_dir: str | Path | None = None,
    timeout_seconds: float = 120.0,
    output_json_path: str | Path | None = None,
    modality: str | None = None,
    sample_ids: list[int] | None = None,
) -> list[EvaluationResult]:
    """Executes the dataset via HTTP requests to the FastAPI endpoints."""
    samples = parse_dataset_manifest(csv_path, base_dir)
    if modality:
        samples = [s for s in samples if s.modality == modality]
    if sample_ids is not None:
        samples = [s for s in samples if s.sample_id in sample_ids]
    api_base_url = api_base_url.rstrip("/")

    print("=" * 60)
    print(f"MINDMESH DATASET EVALUATION RUNNER (HTTP CLIENT)")
    print(f"Target API Endpoint : {api_base_url}")
    print(f"Total CSV Samples   : {len(samples)}")
    print("=" * 60)

    # 1. Health check to ensure FastAPI is up and reachable
    health_url = f"{api_base_url}/health"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(health_url)
            if resp.status_code != 200:
                raise RuntimeError(f"Health check failed with HTTP {resp.status_code}")
            print(f"[OK] FastAPI health check passed at {health_url}")
    except Exception as exc:
        raise RuntimeError(f"Cannot reach FastAPI server at {health_url}: {exc}")

    results: list[EvaluationResult] = []

    with httpx.Client(timeout=timeout_seconds) as client:
        for idx, sample in enumerate(samples, start=1):
            sample_desc = sample.text_content[:40] if sample.text_content else sample.media_relative_path
            print(f"[{idx:02d}/{len(samples)}] Row {sample.sample_id:02d} | Modality: {sample.modality.upper():5s} | {sample_desc} ...", end=" ", flush=True)

            try:
                if sample.modality == "text":
                    url = f"{api_base_url}/api/v1/memories/ingest"
                    payload = {
                        "media_type": "text",
                        "privacy": "ONLY_ME",
                        "text": sample.text_content,
                        "group_id": None,
                        "allowed_users": [],
                    }
                    resp = client.post(url, json=payload)

                elif sample.modality == "image":
                    url = f"{api_base_url}/api/v1/memories/ingest/image"
                    if not sample.media_absolute_path or not sample.media_absolute_path.exists():
                        raise FileNotFoundError(f"Image file missing: {sample.media_absolute_path}")

                    mime_type = mimetypes.guess_type(str(sample.media_absolute_path))[0] or "image/jpeg"
                    with open(sample.media_absolute_path, "rb") as f:
                        file_bytes = f.read()

                    files = {"file": (sample.media_absolute_path.name, file_bytes, mime_type)}
                    data = {
                        "media_type": "image",
                        "privacy": "ONLY_ME",
                        "group_id": "",
                        "allowed_users": "[]",
                    }
                    if sample.ground_truth_caption:
                        data["context"] = sample.ground_truth_caption
                    resp = client.post(url, data=data, files=files)

                elif sample.modality == "audio":
                    url = f"{api_base_url}/api/v1/memories/ingest/audio"
                    if not sample.media_absolute_path or not sample.media_absolute_path.exists():
                        raise FileNotFoundError(f"Audio file missing: {sample.media_absolute_path}")

                    mime_type = mimetypes.guess_type(str(sample.media_absolute_path))[0] or "audio/ogg"
                    with open(sample.media_absolute_path, "rb") as f:
                        file_bytes = f.read()

                    files = {"file": (sample.media_absolute_path.name, file_bytes, mime_type)}
                    data = {
                        "media_type": "audio",
                        "privacy": "ONLY_ME",
                        "group_id": "",
                        "allowed_users": "[]",
                    }
                    resp = client.post(url, data=data, files=files)

                else:
                    raise ValueError(f"Unknown modality: {sample.modality}")

                http_code = resp.status_code
                if http_code == 200:
                    body = resp.json()
                    raw_id = resp.headers.get("X-Raw-Input-Id")
                    phase1_id = resp.headers.get("X-Phase1-Output-Id")
                    mem_id = body.get("memory_id")
                    transcript = body.get("content", {}).get("clean_text") if sample.modality == "audio" else None

                    wer = None
                    if sample.modality == "audio" and sample.ground_truth_caption and transcript:
                        wer = calculate_word_error_rate(sample.ground_truth_caption, transcript)

                    results.append(
                        EvaluationResult(
                            sample_id=sample.sample_id,
                            modality=sample.modality,
                            input_file_or_text=str(sample_desc),
                            status="success",
                            http_status=http_code,
                            raw_input_id=raw_id,
                            phase1_output_id=phase1_id,
                            memory_id=mem_id,
                            transcript=transcript,
                            ground_truth=sample.ground_truth_caption,
                            wer_or_match_metric=wer,
                        )
                    )
                    print(f"-> SUCCESS (HTTP {http_code}, mem={mem_id})")
                else:
                    err_msg = f"HTTP {http_code}: {resp.text[:120]}"
                    results.append(
                        EvaluationResult(
                            sample_id=sample.sample_id,
                            modality=sample.modality,
                            input_file_or_text=str(sample_desc),
                            status="failed",
                            http_status=http_code,
                            error_message=err_msg,
                        )
                    )
                    print(f"-> FAILED ({err_msg})")

            except Exception as exc:
                err_msg = f"{type(exc).__name__}: {str(exc)}"
                results.append(
                    EvaluationResult(
                        sample_id=sample.sample_id,
                        modality=sample.modality,
                        input_file_or_text=str(sample_desc),
                        status="failed",
                        error_message=err_msg,
                    )
                )
                print(f"-> ERROR ({err_msg})")

    # Print Summary Table
    total = len(results)
    successes = sum(1 for r in results if r.status == "success")
    failures = sum(1 for r in results if r.status == "failed")

    text_res = [r for r in results if r.modality == "text"]
    image_res = [r for r in results if r.modality == "image"]
    audio_res = [r for r in results if r.modality == "audio"]

    print("\n" + "=" * 60)
    print("                EXECUTION SUMMARY")
    print("=" * 60)
    print(f"TOTAL SAMPLES PROCESSED : {total}")
    print(f"  TEXT SAMPLES (33)     : {sum(1 for r in text_res if r.status == 'success')}/{len(text_res)} succeeded")
    print(f"  IMAGE SAMPLES (33)    : {sum(1 for r in image_res if r.status == 'success')}/{len(image_res)} succeeded")
    print(f"  AUDIO SAMPLES (25)    : {sum(1 for r in audio_res if r.status == 'success')}/{len(audio_res)} succeeded")
    print(f"OVERALL SUCCESSES       : {successes}/{total}")
    print(f"OVERALL FAILURES        : {failures}/{total}")
    print("=" * 60)

    if output_json_path:
        out_path = Path(output_json_path)
        out_path.write_text(json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")
        print(f"Detailed JSON results written to: {out_path}")

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MindMesh Dataset HTTP Evaluation Runner")
    parser.add_argument("--api-url", type=str, default="http://127.0.0.1:8001", help="Base URL for FastAPI")
    parser.add_argument("--csv", type=str, default=None, help="Path to manifest CSV")
    parser.add_argument("--base-dir", type=str, default=None, help="Base directory for media files")
    parser.add_argument(
        "--modality",
        "-m",
        type=str,
        default=None,
        choices=["text", "image", "audio"],
        help="Filter by modality (image, text, or audio)",
    )
    parser.add_argument("--output", "-o", type=str, default="dataset_evaluation_results.json", help="Path to save output JSON")
    return parser


def main(argv: list[str] | None = None) -> list[EvaluationResult]:
    parser = build_parser()
    args = parser.parse_args(argv)

    return run_dataset_via_api(
        api_base_url=args.api_url,
        csv_path=args.csv,
        base_dir=args.base_dir,
        modality=args.modality,
        output_json_path=args.output,
    )


if __name__ == "__main__":
    main()
