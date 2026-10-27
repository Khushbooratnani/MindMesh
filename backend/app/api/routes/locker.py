from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection.session import get_db_session
from app.database.models.user import UserModel
from app.database.models.locker import LockerSessionModel
from app.database.repositories.raw_input_repo import RawInputRepository
from app.api.dependencies.auth import get_current_user, get_active_locker_session
from app.services.locker_service import LockerService
from app.services.crypto_service import locker_crypto

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
    exists: bool = False
    status: str = "locked"

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class RecoverRequest(BaseModel):
    recovery_key: str
    new_password: str

class RecoverResponse(BaseModel):
    message: str
    new_recovery_key: str


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
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    locker_service = LockerService(db)
    status_dict = await locker_service.get_locker_status(current_user.id)
    has_locker = status_dict.get("has_locker", False)
    locked_out = status_dict.get("locked_out", False)

    is_unlocked = False
    locker_token = request.headers.get("X-Locker-Token")
    if locker_token and has_locker and not locked_out:
        active_sess = await locker_service.get_active_locker_session(current_user.id, locker_token)
        if active_sess:
            is_unlocked = True

    status_str = "unlocked" if is_unlocked else "locked"

    return StatusResponse(
        has_locker=has_locker,
        locked_out=locked_out,
        exists=has_locker,
        status=status_str,
    )


@router.get("/memories")
async def get_locker_memories(
    limit: int = 200,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_user),
    locker_session: LockerSessionModel = Depends(get_active_locker_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Secure endpoint returning only private locker memories belonging to the authenticated locker owner."""
    repo = RawInputRepository(db)
    raw_inputs = await repo.get_private_locker_memories(
        user_id=current_user.id, limit=limit, offset=offset
    )

    items = []
    for r in raw_inputs:
        st = r.structured_payload or {}
        storage_key = st.get("storage_key")
        media_url = f"/api/v1/media/{storage_key}" if storage_key else None
        decrypted_payload = locker_crypto.decrypt(r.raw_payload) if r.raw_payload else ""

        items.append({
            "id": str(r.id),
            "media_type": r.media_type,
            "raw_payload": decrypted_payload,
            "structured_payload": st,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "status": r.status,
            "user_context": st.get("user_context"),
            "original_filename": st.get("original_filename") or st.get("filename"),
            "storage_key": storage_key,
            "media_url": media_url,
            "group_id": r.group_id,
            "privacy": r.privacy,
        })

    return {
        "total_count": len(items),
        "items": items,
    }


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    locker_service = LockerService(db)
    try:
        success = await locker_service.change_password(current_user.id, request.old_password, request.new_password)
        if not success:
            raise HTTPException(status_code=400, detail="Invalid old password")
        return {"message": "Password changed successfully"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/recover", response_model=RecoverResponse)
async def recover_locker(
    request: RecoverRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    locker_service = LockerService(db)
    try:
        success, new_key = await locker_service.recover_password(
            current_user.id, request.recovery_key, request.new_password
        )
        if not success or not new_key:
            raise HTTPException(status_code=400, detail="Invalid recovery key")
        return RecoverResponse(
            message="Password recovered successfully. A new recovery key has been generated.",
            new_recovery_key=new_key,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

