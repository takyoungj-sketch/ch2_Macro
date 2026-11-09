"""관리자·랩 API 접근 판정.

`/api/admin/*`, `/api/lab/*` 는 관리자 세션(`users.role == "admin"`)이 있거나,
`QA_AUDIT_TOKEN` 이 설정되어 있고 `X-Qa-Audit-Token` 이 일치할 때만 연다.
토큰이 설정되지 않았으면 토큰 경로는 열리지 않는다(예전처럼 통과하지 않는다).
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request

from app.config import settings

ADMIN_PREFIXES = ("/api/admin/", "/api/lab/")


def is_admin_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in ADMIN_PREFIXES)


def _token_ok(request: Request) -> bool:
    expected = (settings.qa_audit_token or "").strip()
    if not expected:
        return False
    sent = (request.headers.get("x-qa-audit-token") or "").strip()
    return bool(sent) and hmac.compare_digest(sent, expected)


def caller_role(request: Request) -> str | None:
    """로그인 사용자의 role. 비로그인·플랫폼 DB 없음이면 None."""
    from app.platform.db import get_platform_session_factory
    from app.platform.jwt_util import COOKIE_NAME, decode_access_token
    from sqlalchemy import text

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not str(payload.get("sub", "")).isdigit():
        return None
    factory = get_platform_session_factory()
    if factory is None:
        return None
    try:
        with factory() as db:
            row = db.execute(text("SELECT role FROM users WHERE id = :id"),
                             {"id": int(payload["sub"])}).first()
    except Exception:  # noqa: BLE001 — DB 장애 시 열지 않는다
        return None
    return str(row[0] or "") if row else None


def admin_access_status(request: Request) -> int | None:
    """None 이면 허용. 401(비로그인) 또는 403(관리자 아님)."""
    if _token_ok(request):
        return None
    role = caller_role(request)
    if role == "admin":
        return None
    return 401 if role is None else 403


def require_admin_access(request: Request) -> None:
    """FastAPI 의존성. 미들웨어 게이트와 같은 기준을 라우터에서 한 번 더 확인한다."""
    status = admin_access_status(request)
    if status == 401:
        raise HTTPException(401, "관리자 로그인이 필요합니다.")
    if status == 403:
        raise HTTPException(403, "관리자만 이용할 수 있습니다.")
