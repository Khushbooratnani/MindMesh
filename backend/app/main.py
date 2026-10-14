from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.memories import router as memories_router
from app.api.routes.phase2 import router as phase2_router
from app.core.errors import IngestionError
from app.core.logging import configure_logging


configure_logging()

app = FastAPI(title="Mind Mesh Memory Ingestion API")
app.include_router(memories_router)
app.include_router(phase2_router)


@app.exception_handler(IngestionError)
async def ingestion_error_handler(
    request: Request,
    exc: IngestionError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
