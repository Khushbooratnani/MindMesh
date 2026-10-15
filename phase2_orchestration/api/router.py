from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any
from phase2_orchestration.orchestrator import Phase2Orchestrator, get_orchestrator
from phase2_orchestration.schemas.phase2_schemas import Phase2ProcessResponse
from phase2_orchestration.schemas.search_schemas import MemorySearchRequest, MemorySearchResponse

router = APIRouter(prefix="/api/v1/memories", tags=["Phase 2 - Orchestration Engine"])

@router.post("/process", response_model=Phase2ProcessResponse)
async def process_and_embed_memory(
    payload: Dict[str, Any] = Body(...),
    orchestrator: Phase2Orchestrator = Depends(get_orchestrator)
):
    """
    Ingests Phase 1 MemoryV1 JSON, generates dual embeddings, and stores in DB.
    """
    try:
        return orchestrator.ingest_memory(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    request: MemorySearchRequest,
    orchestrator: Phase2Orchestrator = Depends(get_orchestrator)
):
    """
    Searches memories using dual-vector semantic cosine similarity and generates an AI answer.
    """
    try:
        return orchestrator.search_memories(
            query=request.query,
            user_id=request.user_id or "U_DEVELOPMENT",
            top_k=request.top_k,
            content_weight=request.content_weight,
            context_weight=request.context_weight
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{memory_id}")
async def get_memory_record(
    memory_id: str,
    orchestrator: Phase2Orchestrator = Depends(get_orchestrator)
):
    """
    Retrieves a stored memory record by its memory_id.
    """
    record = orchestrator.get_memory(memory_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")
    return {"success": True, "memory_id": memory_id, "memory": record}
