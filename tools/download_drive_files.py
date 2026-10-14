#!/usr/bin/env python3
"""Download Google Drive files referenced by a CSV and update their paths.

Example:
    python tools/download_drive_files.py combined_form_responses.csv
"""

import argparse
import csv
import mimetypes
import re
import shutil
import sys
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener


DRIVE_ID_RE = re.compile(r"[A-Za-z0-9_-]{20,}")
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp", "image/heic": ".heic"}


def drive_file_id(value: str) -> str | None:
    parsed = urlparse(value.strip())
    query_id = parse_qs(parsed.query).get("id", [None])[0]
    match = DRIVE_ID_RE.fullmatch(query_id or "") or DRIVE_ID_RE.search(parsed.path)
    return match.group(0) if match else None


def download_drive_file(file_id: str, destination: Path, opener) -> str:
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(request, timeout=60) as response:
        content_type = response.headers.get_content_type()
        payload = response.read()

    if content_type == "text/html" or payload.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        token = re.search(rb"confirm=([0-9A-Za-z_-]+)", payload)
        if token:
            confirm_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm={token.group(1).decode()}"
            with opener.open(Request(confirm_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as response:
                content_type = response.headers.get_content_type()
                payload = response.read()
        if content_type == "text/html" or payload.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            raise RuntimeError("Google Drive returned HTML instead of the file; check sharing or authentication")

    extension = EXTENSIONS.get(content_type) or mimetypes.guess_extension(content_type) or ".bin"
    target = destination.with_suffix(extension)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as output:
        output.write(payload)
    return target.name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path, nargs="+")
    parser.add_argument("--output-csv", type=Path, help="Output CSV; defaults to <input>_local.csv")
    parser.add_argument("--media-dir", type=Path, default=Path("media"), help="Root folder for downloaded files")
    parser.add_argument("--columns", nargs="+", default=["image", "audio"], help="CSV columns containing Drive URLs")
    args = parser.parse_args()

    output_csv = args.output_csv or args.input_csv[0].with_name(f"{args.input_csv[0].stem}_local.csv")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    fields = []
    rows = []
    for input_csv in args.input_csv:
        with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for field in reader.fieldnames or []:
                if field not in fields:
                    fields.append(field)
            rows.extend(reader)
    missing_columns = [column for column in args.columns if column not in fields]
    if missing_columns:
        raise SystemExit(f"CSV column(s) not found: {', '.join(missing_columns)}")

    downloaded = skipped = failed = 0
    for row_number, row in enumerate(rows, start=2):
        for column in args.columns:
            source = (row.get(column) or "").strip()
            if not source:
                continue
            file_id = drive_file_id(source)
            if not file_id:
                print(f"Row {row_number}: skipped non-Drive URL in {column}: {source}", file=sys.stderr)
                skipped += 1
                continue
            try:
                folder = args.media_dir / ("audio" if column == "audio" else "images")
                filename = download_drive_file(file_id, folder / f"drive_{file_id}", opener)
                row[column] = (folder / filename).as_posix()
                downloaded += 1
            except Exception as exc:
                print(f"Row {row_number}: download failed for {file_id}: {exc}", file=sys.stderr)
                failed += 1

    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {output_csv}")
    print(f"Downloaded: {downloaded}; skipped: {skipped}; failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
