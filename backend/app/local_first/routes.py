"""
FastAPI routing layer for v2 Local-First Locker Authentication and Ephemeral AI Services.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.database.models.user import UserModel
from app.local_first.database import get_locker_auth_session
from app.local_first.service import LockerAuthService
from app.local_first.temporary_processing import EphemeralAiService
from app.local_first.schemas import (
    LocalFirstRegisterRequest,
    LocalFirstRegisterResponse,
    LocalFirstUnlockRequest,
    LocalFirstUnlockResponse,
    LocalFirstChangePasswordRequest,
    LocalFirstRecoverRequest,
    LocalFirstRecoverResponse,
    LocalFirstStatusResponse,
    EphemeralExtractionRequest,
    EphemeralExtractionResponse,
    EphemeralEmbeddingRequest,
    EphemeralEmbeddingResponse,
    EphemeralQaRequest,
    EphemeralQaResponse,
)

auth_router = APIRouter(prefix="/api/v2/locker-auth", tags=["local-first-auth"])
ai_router = APIRouter(prefix="/api/v2/ephemeral-ai", tags=["local-first-ephemeral-ai"])


# --- Local-First Auth Endpoints ---

@auth_router.post("/register", response_model=LocalFirstRegisterResponse)
async def register_local_locker(
    req: LocalFirstRegisterRequest,
    current_user: UserModel = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_locker_auth_session),
):
    service = LockerAuthService(auth_db)
    try:
        identity, recovery_key = await service.register_locker(current_user.id, req.password)
        return LocalFirstRegisterResponse(identity_id=identity.id, recovery_key=recovery_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@auth_router.post("/unlock", response_model=LocalFirstUnlockResponse)
async def unlock_local_locker(
    req: LocalFirstUnlockRequest,
    current_user: UserModel = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_locker_auth_session),
):
    service = LockerAuthService(auth_db)
    try:
        token = await service.authenticate_and_create_session(current_user.id, req.password)
        return LocalFirstUnlockResponse(token=token, expires_in_seconds=120)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@auth_router.post("/lock")
async def lock_local_locker(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_locker_auth_session),
):
    token = request.headers.get("X-Locker-Token")
    if token:
        service = LockerAuthService(auth_db)
        await service.revoke_session(token)
    return {"message": "Locker session revoked successfully"}


@auth_router.get("/status", response_model=LocalFirstStatusResponse)
async def get_local_locker_status(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_locker_auth_session),
):
    service = LockerAuthService(auth_db)
    status_dict = await service.get_status(current_user.id)
    token = request.headers.get("X-Locker-Token")
    if token and status_dict.get("exists") and not status_dict.get("locked_out"):
        active_sess = await service.validate_session(current_user.id, token)
        if active_sess:
            status_dict["status"] = "unlocked"
    return LocalFirstStatusResponse(**status_dict)


@auth_router.post("/change-password")
async def change_local_locker_password(
    req: LocalFirstChangePasswordRequest,
    current_user: UserModel = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_locker_auth_session),
):
    service = LockerAuthService(auth_db)
    try:
        await service.change_password(current_user.id, req.old_password, req.new_password)
        return {"message": "Password changed successfully; active sessions revoked"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=404, detail=str(e))


@auth_router.post("/recover", response_model=LocalFirstRecoverResponse)
async def recover_local_locker(
    req: LocalFirstRecoverRequest,
    current_user: UserModel = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_locker_auth_session),
):
    service = LockerAuthService(auth_db)
    try:
        new_recovery_key = await service.recover_locker(current_user.id, req.recovery_key, req.new_password)
        return LocalFirstRecoverResponse(
            message="Locker password successfully recovered; new recovery key issued",
            new_recovery_key=new_recovery_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Ephemeral AI Endpoints (Consented, Zero-Persistence) ---

def get_ephemeral_ai_service() -> EphemeralAiService:
    return EphemeralAiService()


@ai_router.post("/extract", response_model=EphemeralExtractionResponse)
async def ephemeral_extract(
    req: EphemeralExtractionRequest,
    current_user: UserModel = Depends(get_current_user),
    ai_service: EphemeralAiService = Depends(get_ephemeral_ai_service),
):
    return await ai_service.extract_semantic_metadata(req, current_user.id)


@ai_router.post("/embed", response_model=EphemeralEmbeddingResponse)
async def ephemeral_embed(
    req: EphemeralEmbeddingRequest,
    current_user: UserModel = Depends(get_current_user),
    ai_service: EphemeralAiService = Depends(get_ephemeral_ai_service),
):
    return await ai_service.generate_local_embeddings(req)


@ai_router.post("/qa", response_model=EphemeralQaResponse)
async def ephemeral_qa(
    req: EphemeralQaRequest,
    current_user: UserModel = Depends(get_current_user),
    ai_service: EphemeralAiService = Depends(get_ephemeral_ai_service),
):
    return await ai_service.answer_from_approved_context(req)
