#!/usr/bin/env python3
import json
from pathlib import Path
from run_phase1_jsonl import post_file

results_path = Path('phase1_results.jsonl')
rows = [json.loads(line) for line in results_path.read_text(encoding='utf-8').splitlines() if line.strip()]
updated = 0
for row in rows:
    item = row.get('input', {})
    if item.get('media_type') != 'image' or row.get('status') == 'success':
        continue
    path = Path(item['file_path'])
    if not path.exists():
        row.update({'status': 'error', 'error': f'Image file not found: {path}'})
        continue
    try:
        status, payload = post_file('http://127.0.0.1:8000/api/v1/memories/ingest/image', item, path)
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
