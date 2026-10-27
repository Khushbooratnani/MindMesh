from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.locker import router as locker_router
from app.api.routes.media import router as media_router
from app.api.routes.memories import router as memories_router
from app.api.routes.groups import router as groups_router
from app.api.routes.comments import router as comments_router
from app.local_first.routes import auth_router as local_first_auth_router, ai_router as local_first_ai_router
from app.config import settings
from app.database.models.user import UserModel
from app.api.dependencies.auth import get_current_user
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
    expose_headers=["X-Raw-Input-Id", "X-Phase1-Output-Id", "X-Locker-Token"],
)

async def verify_local_first_access(current_user: UserModel = Depends(get_current_user)):
    """
    Server-enforced allowlist gate for experimental Package B routes:
    1. Global feature flag must be enabled.
    2. Server-side allowlist check (default deny): The authenticated user ID from JWT
       must be explicitly listed in settings.local_first_test_user_allowlist.
    """
    if not getattr(settings, "enable_local_first_locker", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local-First Private Locker feature is disabled by default.",
        )
    allowlist = getattr(settings, "local_first_test_user_allowlist", [])
    if not allowlist or current_user.id not in allowlist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized for experimental Local-First Private Locker features.",
        )

app.include_router(auth_router)
app.include_router(locker_router)
app.include_router(memories_router)
app.include_router(media_router)
app.include_router(groups_router)
app.include_router(comments_router)
app.include_router(local_first_auth_router, dependencies=[Depends(verify_local_first_access)])
app.include_router(local_first_ai_router, dependencies=[Depends(verify_local_first_access)])


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
