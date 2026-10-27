from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.media import router as media_router
from app.api.routes.memories import router as memories_router
from app.core.errors import IngestionError
from app.core.logging import configure_logging


configure_logging()

app = FastAPI(title="Mind Mesh Memory Ingestion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Raw-Input-Id", "X-Phase1-Output-Id"],
)

app.include_router(memories_router)
app.include_router(media_router)


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
