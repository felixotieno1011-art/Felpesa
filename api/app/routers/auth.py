from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.core.auth_limits import client_ip, enforce
from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.security import create_access_token
from app.deps import SessionDep
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.common import RegisterResponse
from app.services import auth_service, refresh_service

router = APIRouter(prefix="/auth", tags=["auth"])
RedisDep = Annotated[Redis, Depends(get_redis)]
COOKIE = "felpesa_refresh"


def _set_cookie(response, raw: str) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE, raw, max_age=s.refresh_token_ttl_days * 86400, httponly=True,
        secure=s.app_env == "prod", samesite="strict", path="/",
    )


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    payload: RegisterRequest, request: Request, db: SessionDep, redis_client: RedisDep
) -> RegisterResponse:
    await enforce(redis_client, scope="register-ip", identity=client_ip(request))
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
async def login(
    payload: LoginRequest, request: Request, response: Response,
    db: SessionDep, redis_client: RedisDep,
) -> TokenResponse:
    await enforce(redis_client, scope="login-ip", identity=client_ip(request))
    await enforce(redis_client, scope="login-phone", identity=payload.phone)
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
    _set_cookie(response, await refresh_service.issue(db, user.id))
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request, response: Response, db: SessionDep, redis_client: RedisDep,
    felpesa_refresh: Annotated[str | None, Cookie()] = None,
):
    await enforce(redis_client, scope="refresh-ip", identity=client_ip(request))
    try:
        if not felpesa_refresh:
            raise refresh_service.InvalidRefresh
        user, new_raw = await refresh_service.rotate(db, felpesa_refresh)
    except refresh_service.InvalidRefresh:
        bad = JSONResponse(status_code=401, content={"detail": "Invalid refresh token"})
        bad.delete_cookie(COOKIE, path="/")
        return bad
    _set_cookie(response, new_raw)
    return TokenResponse(access_token=create_access_token(subject=str(user.id), role=user.role))


@router.post("/logout")
async def logout(
    response: Response, db: SessionDep,
    felpesa_refresh: Annotated[str | None, Cookie()] = None,
) -> dict:
    if felpesa_refresh:
        await refresh_service.revoke(db, felpesa_refresh)
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}
