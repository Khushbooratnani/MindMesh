#!/usr/bin/env python3
"""Convert form-response CSV data into the Phase 1 JSONL dataset format."""

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("phase1_dataset.jsonl"))
    parser.add_argument("--group-id", default=None)
    parser.add_argument("--privacy", default="ONLY_ME", choices=["ONLY_ME", "GROUP", "SELECTED_USERS"])
    parser.add_argument("--allowed-users", nargs="*", default=[])
    args = parser.parse_args()

    with args.input_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    output_rows = []
    for row_number, row in enumerate(rows, start=2):
        common = {"group_id": args.group_id, "privacy": args.privacy, "allowed_users": args.allowed_users}
        common = {key: value for key, value in common.items() if value is not None}
        text = (row.get("text input") or "").strip()
        image = (row.get("image") or "").strip()
        audio = (row.get("audio") or "").strip()
        caption = (row.get("caption") or "").strip()

        if text:
            output_rows.append({"media_type": "text", "text": text, **common})
        if image:
            output_rows.append({"media_type": "image", "file_path": image, "caption": caption, **common})
        if audio:
            output_rows.append({"media_type": "audio", "file_path": audio, "caption": caption, **common})
        if not (text or image or audio):
            print(f"Skipping empty row {row_number}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for item in output_rows:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    counts = {kind: sum(item["media_type"] == kind for item in output_rows) for kind in ("text", "image", "audio")}
    print(f"Wrote {args.output} ({len(output_rows)} JSONL records)")
    print("Counts:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
