#!/usr/bin/env python3
import json
from pathlib import Path
from urllib.error import HTTPError
from run_phase1_jsonl import post_file

results_path = Path('phase1_results.jsonl')
rows = [json.loads(line) for line in results_path.read_text(encoding='utf-8').splitlines() if line.strip()]
updated = 0
for row in rows:
    item = row.get('input', {})
    if item.get('media_type') != 'audio' or row.get('status') == 'success':
        continue
    original = Path(item['file_path'])
    candidates = [original]
    if original.suffix == '.bin':
        candidates.insert(0, original.with_suffix('.ogg'))
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        row.update({'status': 'error', 'error': f'Audio file not found: {candidates[0]}'})
        continue
    item['file_path'] = path.as_posix()
    try:
        status, payload = post_file('http://127.0.0.1:8000/api/v1/memories/ingest/audio', item, path)
        row.update({'status': 'success', 'http_status': status, 'result': payload})
        row.pop('error', None)
        updated += 1
        print(row['record_number'], 'success')
    except Exception as exc:
        row.update({'status': 'error', 'error': str(exc)})
        print(row['record_number'], 'error:', exc)
with results_path.open('w', encoding='utf-8') as handle:
    for row in rows:
        handle.write(json.dumps(row, ensure_ascii=False) + '\n')
print('updated:', updated)
