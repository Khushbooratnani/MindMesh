from fastapi import APIRouter, Depends, HTTPException

from app.schemas.ingestion_request import CurrentUser
from app.schemas.retrieval import (
    EmbeddingRunRequest,
    EmbeddingRunResponse,
    GraphSyncRequest,
    GraphSyncResponse,
    NearbySearchRequest,
    SearchRequest,
    SearchResponse,
)
from app.services.embedding_worker import EmbeddingWorker
from app.services.graph_sync_worker import GraphSyncWorker
from app.services.query_orchestrator import QueryOrchestrator
from app.services.geocoding_service import GeocodingError, LocationIQGeocoder
from app.api.routes.memories import get_current_user

router = APIRouter(prefix="/api/v1", tags=["phase2"])


def get_embedding_worker() -> EmbeddingWorker:
    return EmbeddingWorker()


def get_graph_sync_worker() -> GraphSyncWorker:
    return GraphSyncWorker()


def get_query_orchestrator() -> QueryOrchestrator:
    return QueryOrchestrator()


def get_geocoder() -> LocationIQGeocoder:
    return LocationIQGeocoder()


@router.post("/phase2/embeddings/run", response_model=EmbeddingRunResponse)
def run_embeddings(
    request: EmbeddingRunRequest,
    worker: EmbeddingWorker = Depends(get_embedding_worker),
) -> EmbeddingRunResponse:
    return EmbeddingRunResponse(
        **worker.run(limit=request.limit, memory_ids=request.memory_ids)
    )


@router.post("/phase2/graph/sync", response_model=GraphSyncResponse)
def sync_graph(
    request: GraphSyncRequest,
    worker: GraphSyncWorker = Depends(get_graph_sync_worker),
) -> GraphSyncResponse:
    return GraphSyncResponse(
        **worker.run(limit=request.limit, memory_ids=request.memory_ids)
    )


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: QueryOrchestrator = Depends(get_query_orchestrator),
    geocoder: LocationIQGeocoder = Depends(get_geocoder),
) -> SearchResponse:
    if request.location_query:
        try:
            coordinates = geocoder.geocode(request.location_query)
        except GeocodingError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        latitude = coordinates["latitude"]
        longitude = coordinates["longitude"]
        radius_km = request.radius_km or 10
        return SearchResponse(
            mode=request.mode,
            results=orchestrator.location_aware_search(
                query=request.query, owner_id=current_user.id,
                latitude=float(latitude), longitude=float(longitude),
                radius_km=radius_km, limit=request.limit,
            ),
        )
    if any(value is not None for value in (request.latitude, request.longitude, request.radius_km)):
        if request.latitude is None or request.longitude is None or request.radius_km is None:
            raise HTTPException(status_code=422, detail="latitude, longitude, and radius_km must be provided together")
        return SearchResponse(
            mode=request.mode,
            results=orchestrator.location_aware_search(
                query=request.query, owner_id=current_user.id,
                latitude=request.latitude, longitude=request.longitude,
                radius_km=request.radius_km, limit=request.limit,
            ),
        )
    if request.mode == "graph":
        return SearchResponse(
            mode=request.mode,
            results=orchestrator.graph_search(
                query=request.query,
                owner_id=current_user.id,
                limit=request.limit,
            ),
        )
    if request.mode == "hybrid":
        return SearchResponse(
            mode=request.mode,
            results=orchestrator.hybrid_search(
                query=request.query,
                owner_id=current_user.id,
                limit=request.limit,
            ),
        )

    return SearchResponse(
        mode=request.mode,
        results=orchestrator.vector_search(
            query=request.query,
            owner_id=current_user.id,
            limit=request.limit,
        ),
    )


@router.post("/search/nearby", response_model=SearchResponse)
def nearby_search(
    request: NearbySearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: QueryOrchestrator = Depends(get_query_orchestrator),
) -> SearchResponse:
    return SearchResponse(
        mode="hybrid",
        results=orchestrator.nearby_search(
            owner_id=current_user.id,
            latitude=request.latitude,
            longitude=request.longitude,
            radius_km=request.radius_km,
            limit=request.limit,
        ),
    )
