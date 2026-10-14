# Phase 2 Orchestration Engine (Embedding & Semantic Search)

This package contains the complete, self-contained **Phase 2 Orchestration Engine** for MindMesh, designed specifically for **dual-vector embedding generation, storage, and semantic search**.

> **Note on Location:**  
> All location-based services (geocoding, GPS coordinates, distance calculations, and dedicated location tables) have been completely removed from this package. Search is purely driven by BAAI/bge-m3 semantic cosine similarity.

---

## 📂 Directory Structure

```
phase2_orchestration/
│
├── orchestrator.py           # 🚀 Primary Orchestrator facade (Main Entry Point)
├── config.py                 # Configuration settings (Model, Dimensions, DB URL)
├── sample_payloads.json      # 3 ready-to-use MemoryV1 JSON payloads for testing
├── test_orchestration.py     # Live verification test script
│
├── services/
│   ├── embedding_service.py  # BAAI/bge-m3 dual 1024-dim vector generation (Content + Context)
│   ├── phase2_service.py     # Orchestrates Ingestion: MemoryV1 -> Embeddings -> DB Storage
│   ├── search_service.py     # Orchestrates Retrieval: Query -> Vector Cosine Match -> Answer
│   └── llm_service.py        # Generates natural answers grounded in retrieved memories
│
├── storage/
│   ├── db_models.py          # MemoryTable (JSONB payload + dual 1024-dim vector columns)
│   ├── db_session.py         # SQLAlchemy engine & session (PostgreSQL pgvector / SQLite fallback)
│   └── memory_repository.py  # Upsert and weighted vector cosine similarity search
│
├── schemas/
│   ├── phase2_schemas.py     # Pydantic response models for embedding & processing
│   └── search_schemas.py     # Pydantic request & response models for search
│
└── api/
    └── router.py             # FastAPI APIRouter with POST /process and POST /search endpoints
```

---

## 🚀 Quick Start & Verification

Run the self-contained test script to verify both embedding generation and semantic search:

```bash
python phase2_orchestration/test_orchestration.py
```

---

## 💡 How to Use the Orchestrator

### 1. In Python Code (Direct Import)

```python
from phase2_orchestration.orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# --- A. Ingest & Embed MemoryV1 (from Phase 1) ---
memory_payload = {
    "memory_id": "M_12345",
    "schema_version": "1.0",
    "system": {"owner_id": "U_MEHUL_01", "privacy": "GROUP", "allowed_users": []},
    "content": {"clean_text": "Met with Akshat at Blue Tokai to plan MindMesh Phase 2."},
    "entities": {"people": ["Akshat"], "places": ["Blue Tokai"]},
    "semantics": {"topics": ["MindMesh", "Phase 2", "Architecture"]}
}

res = orchestrator.ingest_memory(memory_payload)
print(f"Memory stored: {res.stored}, Vector dimensions: {res.embeddings.content.dimension}")

# --- B. Semantic Search ---
search_result = orchestrator.search_memories(
    query="Where did I meet Akshat?",
    user_id="U_MEHUL_01",
    top_k=5
)

print(f"AI Answer: {search_result.answer}")
for item in search_result.results:
    print(f"- {item.memory_id} (Score: {item.similarity_score}): {item.summary}")
```

### 2. Plug Into a FastAPI Web App

Mount the router into your existing FastAPI application:

```python
from fastapi import FastAPI
from phase2_orchestration.api.router import router as phase2_router

app = FastAPI()
app.include_router(phase2_router)
```

**Exposed Endpoints:**
- `POST /api/v1/memories/process`: Accepts Phase 1 `MemoryV1` JSON payload and returns embedding status.
- `POST /api/v1/memories/search`: Accepts `{"query": "...", "top_k": 5}` and returns ranked results + AI answer.
- `GET /api/v1/memories/{memory_id}`: Retrieves a single memory by ID.

---

## ⚙️ Configuration & Database

- By default, it connects to PostgreSQL at `postgresql://postgres:postgres@localhost:5432/mind_mesh`.
- If PostgreSQL is not active, it automatically falls back to a local SQLite database (`mind_mesh_orchestration.db`) so development and testing never break.
- Uses `BAAI/bge-m3` (1024-dimensional vectors). If offline, it provides deterministic mock vectors for testing.
