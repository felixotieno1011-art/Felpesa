from fastapi import APIRouter, HTTPException, status

from app.deps import SessionDep
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.common import RegisterResponse
from app.core.security import create_access_token
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(payload: RegisterRequest, db: SessionDep) -> RegisterResponse:
    try:
        user, wallet = await auth_service.register_user(
            db,
            phone=payload.phone,
            full_name=payload.full_name,
            password=payload.password,
        )
    except auth_service.UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone already registered",
        )
    return RegisterResponse(
        id=str(user.id),
        phone=user.phone,
        full_name=user.full_name,
        wallet_id=str(wallet.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: SessionDep) -> TokenResponse:
    try:
        user = await auth_service.authenticate_user(
            db, phone=payload.phone, password=payload.password
        )
    except auth_service.InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token)
