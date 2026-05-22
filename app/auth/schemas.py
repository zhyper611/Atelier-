from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("username is required")
        if not cleaned.replace("_", "").replace("-", "").isalnum():
            raise ValueError("username may only contain letters, numbers, _ and -")
        return cleaned


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: str
    username: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
