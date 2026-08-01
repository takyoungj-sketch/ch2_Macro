"""플랫폼 FastAPI 의존성."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.db import get_platform_db
from app.platform.jwt_util import COOKIE_NAME, decode_access_token


@dataclass
class CurrentUser:
    id: int
    email: str
    nickname: str
    role: str


def get_optional_user(
    request: Request,
    ch2_session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    db: Session = Depends(get_platform_db),
) -> CurrentUser | None:
    token = ch2_session
    if not token:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None
    user_id = int(payload["sub"])
    row = db.execute(
        text("SELECT id, email, nickname, role FROM users WHERE id = :id"),
        {"id": user_id},
    ).mappings().first()
    if not row:
        return None
    return CurrentUser(
        id=int(row["id"]),
        email=str(row["email"]),
        nickname=str(row["nickname"]),
        role=str(row["role"]),
    )


def require_user(user: CurrentUser | None = Depends(get_optional_user)) -> CurrentUser:
    if user is None:
        raise HTTPException(401, "로그인이 필요합니다.")
    return user
