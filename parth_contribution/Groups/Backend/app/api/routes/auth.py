from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection.session import get_db_session
from app.database.models.user import UserModel
from app.api.dependencies.auth import get_current_user, security
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class UserResponse(BaseModel):
    id: str
    username: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RegisterRequest(BaseModel):
    username: str
    password: str


@router.post("/register", response_model=UserResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db_session)
):
    auth_service = AuthService(db)
    try:
        user = await auth_service.register_user(request.username, request.password)
        return UserResponse(id=user.id, username=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session)
):
    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
        
    raw_token, session = await auth_service.create_session(user.id)
    
    return TokenResponse(access_token=raw_token)


@router.post("/logout")
async def logout(
    current_user: UserModel = Depends(get_current_user),
    credentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
):
    auth_service = AuthService(db)
    await auth_service.revoke_session(credentials.credentials)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    return UserResponse(id=current_user.id, username=current_user.username)
