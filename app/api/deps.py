from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_tokens import decode_access_token
from app.auth.user_store import UserRecord, UserStore
from app.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)


async def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserRecord:
    settings = get_settings()
    if not settings.auth_enabled:
        return UserRecord(
            id=settings.auth_bypass_user_id,
            username="test",
            password_hash="",
            created_at=datetime.now(UTC),
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = decode_access_token(credentials.credentials, settings)
    store: UserStore | None = getattr(request.app.state, "user_store", None)
    if store is None:
        raise RuntimeError("User store is not initialized")
    user = await store.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


async def check_rate_limit(request: Request, key: str) -> None:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        return
    allowed = await limiter.check(key)
    if not allowed:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


async def check_auth_rate_limit(request: Request) -> None:
    client = request.client
    host = client.host if client else "unknown"
    await check_rate_limit(request, f"auth:{host}")
