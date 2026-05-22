from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Security

from app.auth.jwt_tokens import create_access_token
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.auth.user_store import UserRecord, UserStore
from app.api.deps import check_auth_rate_limit, get_current_user
from app.auth.passwords import verify_password
from app.core.config import get_settings


def _get_user_store(request: Request) -> UserStore:
    store = getattr(request.app.state, "user_store", None)
    if store is None:
        raise RuntimeError("User store is not initialized")
    return store


def _to_public(user: UserRecord) -> UserPublic:
    return UserPublic(id=user.id, username=user.username, created_at=user.created_at)


def build_auth_router() -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post("/register", response_model=TokenResponse)
    async def register(
        body: RegisterRequest,
        request: Request,
        store: UserStore = Depends(_get_user_store),
        _: None = Depends(check_auth_rate_limit),
    ) -> TokenResponse:
        try:
            user = await store.create_user(body.username, body.password)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail="用户名已被注册") from exc
        settings = get_settings()
        token = create_access_token(user_id=user.id, settings=settings)
        return TokenResponse(
            access_token=token,
            user=_to_public(user),
        )

    @router.post("/login", response_model=TokenResponse)
    async def login(
        body: LoginRequest,
        request: Request,
        store: UserStore = Depends(_get_user_store),
        _: None = Depends(check_auth_rate_limit),
    ) -> TokenResponse:
        user = await store.get_by_username(body.username.strip())
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        settings = get_settings()
        token = create_access_token(user_id=user.id, settings=settings)
        return TokenResponse(
            access_token=token,
            user=_to_public(user),
        )

    @router.get("/me", response_model=UserPublic)
    async def me(
        current_user: UserRecord = Security(get_current_user),
    ) -> UserPublic:
        return _to_public(current_user)

    return router
