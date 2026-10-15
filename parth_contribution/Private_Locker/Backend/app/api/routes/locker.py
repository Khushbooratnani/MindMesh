from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection.session import get_db_session
from app.database.models.user import UserModel
from app.api.dependencies.auth import get_current_user, get_active_locker_session
from app.services.locker_service import LockerService

router = APIRouter(prefix="/api/v1/locker", tags=["locker"])


class CreateLockerRequest(BaseModel):
    password: str

class CreateLockerResponse(BaseModel):
    locker_id: str
    recovery_key: str

class UnlockRequest(BaseModel):
    password: str

class UnlockResponse(BaseModel):
    locker_token: str

class StatusResponse(BaseModel):
    has_locker: bool
    locked_out: bool

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class RecoverRequest(BaseModel):
    recovery_key: str
    new_password: str


@router.post("/create", response_model=CreateLockerResponse)
async def create_locker(
    request: CreateLockerRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    locker_service = LockerService(db)
    try:
        locker, recovery_key = await locker_service.create_locker(current_user.id, request.password)
        return CreateLockerResponse(locker_id=locker.id, recovery_key=recovery_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/unlock", response_model=UnlockResponse)
async def unlock_locker(
    request: UnlockRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    locker_service = LockerService(db)
    try:
        token = await locker_service.unlock(current_user.id, request.password)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect locker password",
            )
        return UnlockResponse(locker_token=token)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/lock")
async def lock_locker(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    locker_token = request.headers.get("X-Locker-Token")
    if not locker_token:
        raise HTTPException(status_code=400, detail="Missing X-Locker-Token")
        
    locker_service = LockerService(db)
    await locker_service.lock(current_user.id, locker_token)
    return {"message": "Locker locked successfully"}


@router.get("/status", response_model=StatusResponse)
async def get_status(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    locker_service = LockerService(db)
    status_dict = await locker_service.get_locker_status(current_user.id)
    return StatusResponse(**status_dict)

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    locker_service = LockerService(db)
    success = await locker_service.change_password(current_user.id, request.old_password, request.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid old password")
    return {"message": "Password changed successfully"}

@router.post("/recover")
async def recover_locker(
    request: RecoverRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    locker_service = LockerService(db)
    success = await locker_service.recover_password(current_user.id, request.recovery_key, request.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid recovery key")
    return {"message": "Password recovered successfully"}
