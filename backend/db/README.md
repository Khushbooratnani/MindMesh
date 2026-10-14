# Phase 2 PostgreSQL Inputs

These SQL files create PostgreSQL inputs for Phase 2 retrieval testing.

- `backend/db/seeds/sample_memories.sql` contains the original two-memory smoke test.
- `backend/db/seeds/phase2_pipeline_payloads.sql` is generated from `PHASE_2_PIPELINE_PAYLOADS.md` and contains 22 memories: 11 text memories and 11 image memories.

Run in order:

```bash
psql "$DATABASE_URL" -f backend/db/schema.sql
psql "$DATABASE_URL" -f backend/db/seeds/sample_memories.sql
psql "$DATABASE_URL" -f backend/db/queries/phase2_embedding_inputs.sql
```

To use the full Phase 2 markdown dataset instead of the small sample:

```bash
cd /Users/khushboo/Desktop/projects/Major
python3 backend/tools/build_phase2_seed.py
docker exec -i pgvector-db psql -U postgres -d mindmesh < backend/db/schema.sql
docker exec -i pgvector-db psql -U postgres -d mindmesh < backend/db/seeds/phase2_pipeline_payloads.sql
```

The full dataset seed truncates existing memory, embedding job, graph job, entity, topic, activity, mood, attribute, and embedding rows before loading the 22 memories. Clear Neo4j before re-syncing this dataset if you want the graph to contain only the new payloads:

```cypher
MATCH (n) DETACH DELETE n;
```

Verify the PostgreSQL load:

```bash
psql -h 127.0.0.1 -p 5433 -U postgres -d mindmesh \
  -c "SELECT media_type, count(*) FROM memories GROUP BY media_type ORDER BY media_type;"
```

Expected result:

```text
 image | 11
 text  | 11
```

Phase 2 embedding generation should read from the `memory_embedding_inputs` view. The important column is `text_for_embedding`, which combines the memory summary, description, clean content, entities, topics, activities, mood, sentiment, and time context into one textual payload.

Embedding workers should use Ollama `bge-m3:latest` and store generated vectors in the pgvector-backed `memory_embeddings.embedding` column.

Neo4j graph constraints are in `backend/db/graph_constraints.cypher`.

Start the API:

```bash
cd /Users/khushboo/Desktop/projects/Major/backend
.venv/bin/uvicorn app.main:app --reload
```

Run embedding generation:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/phase2/embeddings/run \
  -H "Content-Type: application/json" \
  -d '{"limit": 25, "memory_ids": []}'
```

Run graph sync:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/phase2/graph/sync \
  -H "Content-Type: application/json" \
  -d '{"limit": 25, "memory_ids": []}'
```

Run vector, graph, or hybrid search:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "coffee memories in Goa", "mode": "vector", "limit": 5}'

curl -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Which memories mention Neo4j architecture?", "mode": "hybrid", "limit": 5}'
```
