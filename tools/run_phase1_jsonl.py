#!/usr/bin/env python3
"""Submit a Phase 1 JSONL manifest and write one result per input record."""

import argparse
import json
import mimetypes
import uuid
from pathlib import Path
from urllib.request import Request, urlopen


def post_json(url, item):
    payload = json.dumps(item).encode()
    request = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=180) as response:
        return response.status, json.loads(response.read())


def post_file(url, item, file_path):
    boundary = f"----Phase1{uuid.uuid4().hex}"
    parts = []
    for key in ("media_type", "group_id", "privacy"):
        if key in item:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{item[key]}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"allowed_users\"\r\n\r\n{json.dumps(item.get('allowed_users', []))}\r\n".encode())
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_path.name}\"\r\nContent-Type: {content_type}\r\n\r\n".encode() + file_path.read_bytes() + b"\r\n")
    body = b"".join(parts) + f"--{boundary}--\r\n".encode()
    request = Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    with urlopen(request, timeout=300) as response:
        return response.status, json.loads(response.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_jsonl", type=Path)
    parser.add_argument("--output", type=Path, default=Path("phase1_results.jsonl"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    root = Path.cwd()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_handle, args.input_jsonl.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            item = json.loads(line)
            result = {"record_number": index, "input": item}
            try:
                if item["media_type"] == "text":
                    status, payload = post_json(f"{args.base_url}/api/v1/memories/ingest", item)
                elif item["media_type"] == "image":
                    path = Path(item["file_path"])
                    path = path if path.is_absolute() else root / path
                    status, payload = post_file(f"{args.base_url}/api/v1/memories/ingest/image", item, path)
                elif item["media_type"] == "audio":
                    path = Path(item["file_path"])
                    path = path if path.is_absolute() else root / path
                    status, payload = post_file(f"{args.base_url}/api/v1/memories/ingest/audio", item, path)
                else:
                    raise ValueError(f"Unsupported media_type: {item['media_type']}")
                result.update({"status": "success", "http_status": status, "result": payload})
            except Exception as exc:
                result.update({"status": "error", "error": str(exc)})
            output_handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            output_handle.flush()
            print(f"{index}: {result['status']} ({item['media_type']})")
    print(f"Wrote {args.output} with {index} results")


if __name__ == "__main__":
    main()
