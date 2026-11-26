"""집합2 접근. 관리자이거나 COLLECTIVE_NEXT_ALLOW 에 있는 계정만 연다."""

from __future__ import annotations

import os

from fastapi import HTTPException, Request

from app.feature_gates import COLLECTIVE_NEXT, HIDDEN_DETAIL, feature_mode, is_admin


def caller_user_id(request: Request) -> str | None:
    from app.platform.jwt_util import COOKIE_NAME, decode_access_token

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = str(payload.get("sub", "")).strip()
    return user_id if user_id.isdigit() else None


def allowlist() -> set[str]:
    raw = os.getenv("COLLECTIVE_NEXT_ALLOW", "")
    return {part.strip() for part in raw.split(",") if part.strip()}


def collective_next_allowed(request: Request) -> bool:
    mode = feature_mode(COLLECTIVE_NEXT)
    if mode == "off":
        return False
    if mode == "public":
        return True
    if is_admin(request):
        return True
    user_id = caller_user_id(request)
    return bool(user_id) and user_id in allowlist()


def require_collective_next(request: Request) -> None:
    if not collective_next_allowed(request):
        raise HTTPException(403, HIDDEN_DETAIL)
