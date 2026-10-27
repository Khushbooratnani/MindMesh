import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.storage.file_storage import FileStorage
from app.api.dependencies.auth import get_current_user, get_active_locker_session
from app.database.connection.session import get_db_session
from app.database.models.user import UserModel
from app.database.models.raw_input import RawInputModel
from app.database.models.phase1_output import Phase1OutputModel
from app.core.enums import Privacy
from app.services.authz_service import AuthorizationService

router = APIRouter(prefix="/api/v1/media", tags=["media"])


@router.get("/{storage_key:path}")
async def get_media_file(
    storage_key: str,
    fastapi_req: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Retrieve original binary image or audio asset using durable FileStorage."""
    
    # Dialect-agnostic media asset lookup
    dialect_name = db.bind.dialect.name if db.bind else ""
    if dialect_name == "postgresql":
        stmt = select(RawInputModel).where(
            text("structured_payload->>'storage_key' = :key").bindparams(key=storage_key)
        )
        result = await db.execute(stmt)
        raw_input = result.scalars().first()
    else:
        # SQLite / in-memory testing lookup
        res = await db.execute(select(RawInputModel))
        all_raw = res.scalars().all()
        raw_input = None
        for r in all_raw:
            st = r.structured_payload or {}
            if st.get("storage_key") == storage_key or st.get("relative_path") == storage_key:
                raw_input = r
                break

    if not raw_input:
        # Check storage directory directly if unindexed file
        storage = FileStorage()
        try:
            file_path = storage.get_file_path(storage_key)
            if not file_path.exists() or not file_path.is_file():
                raise HTTPException(status_code=404, detail=f"File not found: {storage_key}")
            media_type, _ = mimetypes.guess_type(str(file_path))
            return FileResponse(path=file_path, media_type=media_type or "application/octet-stream")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Media asset not found")

    # Check authorization using Phase1 if available, otherwise raw input
    p1_stmt = select(Phase1OutputModel).where(Phase1OutputModel.raw_input_id == raw_input.id)
    p1_res = await db.execute(p1_stmt)
    phase1 = p1_res.scalars().first()

    locker_session_valid = False
    is_private_locker = (phase1 and phase1.privacy == Privacy.PRIVATE_LOCKER.value) or (
        not phase1 and raw_input.privacy == Privacy.PRIVATE_LOCKER.value
    )
    if is_private_locker:
        try:
            await get_active_locker_session(fastapi_req, current_user, db)
            locker_session_valid = True
        except Exception:
            raise HTTPException(status_code=403, detail="Unauthorized to access this private media")

    if phase1:
        if not await AuthorizationService.can_read_memory(db, current_user.id, phase1.memory_id, locker_session_valid):
            raise HTTPException(status_code=403, detail="Unauthorized to access this media")
    else:
        # Fallback if phase 1 is not complete yet
        if raw_input.privacy == Privacy.PRIVATE_LOCKER.value:
            if raw_input.owner_id != current_user.id or not locker_session_valid:
                raise HTTPException(status_code=403, detail="Unauthorized to access this private media")
        elif raw_input.group_id:
            try:
                import uuid
                from app.services.group_service import GroupService
                gid = uuid.UUID(str(raw_input.group_id))
                await GroupService.verify_membership(db, gid, current_user.id)
            except Exception:
                raise HTTPException(status_code=403, detail="Unauthorized to access this group media")
        elif raw_input.privacy != Privacy.PUBLIC.value and raw_input.owner_id != current_user.id and current_user.id != "U_DEVELOPMENT":
            raise HTTPException(status_code=403, detail="Unauthorized to access this media")

    storage = FileStorage()
    try:
        file_path = storage.get_file_path(storage_key)
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {storage_key}")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    media_type, _ = mimetypes.guess_type(str(file_path))
    if media_type is None:
        media_type = "application/octet-stream"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=Path(storage_key).name,
    )
