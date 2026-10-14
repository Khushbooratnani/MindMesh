import json
from pathlib import Path

rows = [json.loads(line) for line in Path('phase1_results.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]

def q(value):
    if value is None:
        return 'NULL'
    return "'" + str(value).replace("'", "''") + "'"

def qa(value):
    return q('{' + ','.join(str(x).replace('}', '').replace('{', '').replace(',', '\\,') for x in (value or [])) + '}')

sql = ['BEGIN;', 'TRUNCATE memory_embeddings, memory_embedding_jobs, memory_graph_jobs, memory_attributes, memory_moods, memory_activities, memory_topics, memory_entities, memories CASCADE;']
for row in rows:
    m = row['result']
    s, c, e, se, t = m['system'], m['content'], m['entities'], m['semantics'], m['temporal']
    p = m['processing']
    sql.append('INSERT INTO memories VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);' % (
        q(m['memory_id']), q(m['schema_version']), q(s['owner_id']), q(s['group_id']), q(s['media_type']), q(s['created_at']), q(s['privacy']), qa(s['allowed_users']), q(c['raw_text']), q(c['clean_text']), q(c['description']), q(c['summary']), q(se['sentiment']), qa(t['mentioned_dates']), q(t['inferred_time']), q(t['time_of_day']), q(p['status']), q(p['source_modality']), str(p['transcription_required']).upper(), str(p['image_understanding_required']).upper(), q(p['llm_provider']), q(p['llm_model']), qa(p['errors'])))
    for kind in ('people', 'places', 'locations', 'events', 'organizations'):
        for value in e.get(kind, []): sql.append('INSERT INTO memory_entities(memory_id,entity_type,entity_value) VALUES (%s,%s,%s);' % (q(m['memory_id']), q(kind[:-1] if kind != 'people' else 'person'), q(value)))
    for value in se.get('topics', []): sql.append('INSERT INTO memory_topics(memory_id,topic) VALUES (%s,%s);' % (q(m['memory_id']), q(value)))
    for value in se.get('activities', []): sql.append('INSERT INTO memory_activities(memory_id,activity) VALUES (%s,%s);' % (q(m['memory_id']), q(value)))
    for value in se.get('mood', []): sql.append('INSERT INTO memory_moods(memory_id,mood) VALUES (%s,%s);' % (q(m['memory_id']), q(value)))
    for a in m.get('additional_attributes', []): sql.append('INSERT INTO memory_attributes(memory_id,key,value_json,confidence,source) VALUES (%s,%s,%s::jsonb,%s,%s);' % (q(m['memory_id']), q(a['key']), q(json.dumps(a['value'], ensure_ascii=False)), a['confidence'], q(a['source'])))
sql.append('COMMIT;')
Path('/tmp/phase1_load.sql').write_text('\n'.join(sql), encoding='utf-8')
print('generated', len(rows), 'memory inserts')
