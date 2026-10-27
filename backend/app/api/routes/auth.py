from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection.session import get_db_session
from app.database.models.user import UserModel
from app.api.dependencies.auth import get_current_user, security
from app.services.auth_service import AuthService
from app.services.locker_service import LockerService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None


class LoginJsonRequest(BaseModel):
    username: str
    password: str


@router.post("/register", response_model=UserResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
):
    auth_service = AuthService(db)
    try:
        user = await auth_service.register_user(request.username, request.password)
        email_val = user.username if "@" in user.username else None
        name_val = request.full_name or (email_val.split("@")[0] if email_val else user.username)
        return UserResponse(
            id=user.id,
            username=user.username,
            email=email_val,
            full_name=name_val,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    username: Optional[str] = None
    password: Optional[str] = None

    # Check content-type to handle both form-data / x-www-form-urlencoded AND json
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        username = body.get("username")
        password = body.get("password")
    else:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required",
        )

    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(username, password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    raw_token, session = await auth_service.create_session(user.id)
    return TokenResponse(access_token=raw_token)


@router.post("/logout")
async def logout(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    credentials=Depends(security),
    db: AsyncSession = Depends(get_db_session),
):
    auth_service = AuthService(db)
    raw_token = credentials.credentials if credentials else None
    if raw_token:
        await auth_service.revoke_session(raw_token)

    # Revoke all active locker sessions on logout
    locker_service = LockerService(db)
    await locker_service.revoke_all_user_locker_sessions(current_user.id)

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    email_val = current_user.username if "@" in current_user.username else None
    name_val = email_val.split("@")[0] if email_val else current_user.username
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=email_val,
        full_name=name_val,
    )
