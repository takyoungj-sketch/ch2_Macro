"""관리자 비밀번호 로그인 — 값은 env에만 두고 git에 넣지 않는다."""

from __future__ import annotations

import secrets
import time
from collections import defaultdict

from fastapi import Request

STAFF_SESSION_MINUTES = 7 * 24 * 60
_MAX_ATTEMPTS = 5
_WINDOW_SEC = 15 * 60

_attempts: dict[str, list[float]] = defaultdict(list)


def staff_password_configured(password: str) -> bool:
    return bool((password or "").strip())


def passwords_match(expected: str, submitted: str) -> bool:
    exp = expected or ""
    sub = submitted or ""
    if not exp or not sub:
        return False
    try:
        return secrets.compare_digest(exp, sub)
    except (TypeError, ValueError):
        return False


def client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def too_many_attempts(ip: str) -> bool:
    now = time.monotonic()
    kept = [t for t in _attempts[ip] if now - t < _WINDOW_SEC]
    _attempts[ip] = kept
    return len(kept) >= _MAX_ATTEMPTS


def record_failure(ip: str) -> None:
    _attempts[ip].append(time.monotonic())


def clear_failures(ip: str) -> None:
    _attempts.pop(ip, None)
