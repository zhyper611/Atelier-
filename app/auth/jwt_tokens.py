from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException

from app.core.config import Settings


def create_access_token(*, user_id: str, settings: Settings) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    user_id = payload.get("sub")
    if not user_id or not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id
