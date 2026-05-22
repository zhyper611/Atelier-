from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiosqlite

from app.auth.passwords import hash_password


@dataclass(frozen=True)
class UserRecord:
    id: str
    username: str
    password_hash: str
    created_at: datetime


class UserStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def open(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await self._conn.commit()

    async def close(self) -> None:
        await self._conn.close()

    def _row_to_record(self, row: aiosqlite.Row) -> UserRecord:
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return UserRecord(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            created_at=created_at,
        )

    async def create_user(self, username: str, password: str) -> UserRecord:
        user_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        password_hash = hash_password(password)
        try:
            await self._conn.execute(
                """
                INSERT INTO users (id, username, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, username, password_hash, created_at),
            )
            await self._conn.commit()
        except aiosqlite.IntegrityError as exc:
            raise ValueError("username already exists") from exc
        row = await self.get_by_id(user_id)
        if row is None:
            raise RuntimeError("failed to create user")
        return row

    async def get_by_username(self, username: str) -> UserRecord | None:
        cursor = await self._conn.execute(
            "SELECT id, username, password_hash, created_at FROM users WHERE username = ? COLLATE NOCASE",
            (username.strip(),),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    async def get_by_id(self, user_id: str) -> UserRecord | None:
        cursor = await self._conn.execute(
            "SELECT id, username, password_hash, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)
