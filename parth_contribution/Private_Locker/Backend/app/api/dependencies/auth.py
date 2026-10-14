from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection.session import get_db_session
from app.database.models.user import UserModel
from app.services.auth_service import AuthService
from app.services.locker_service import LockerService

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> UserModel:
    """Validates the Authorization Bearer token and returns the current user."""
    auth_service = AuthService(db)
    user = await auth_service.get_active_user_from_token(credentials.credentials)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_active_locker_session(
    request: Request,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> None:
    """
    Validates X-Locker-Token for Private Locker endpoints.
    If the endpoint processes PRIVATE_LOCKER data, this dependency must succeed.
    Raises 401 if missing, invalid, or idle-timed-out.
    """
    locker_token = request.headers.get("X-Locker-Token")
    
    if not locker_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Private Locker token required in X-Locker-Token header",
        )
        
    locker_service = LockerService(db)
    session = await locker_service.get_active_locker_session(user.id, locker_token)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Private Locker session is invalid, revoked, or expired due to inactivity",
        )
