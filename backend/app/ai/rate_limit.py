"""AI API 분당 요청 제한.

키: 로그인 사용자는 `user:<id>`(서명된 JWT 의 sub), 비로그인은 IP.
IP 는 직접 접속 주소가 신뢰 프록시(`AI_TRUSTED_PROXIES`, 기본 loopback)일 때만
nginx 가 넣는 `X-Real-IP` 를 쓴다. 클라이언트가 위조할 수 있는 X-Forwarded-For
첫 값은 쓰지 않는다.

저장소: 현재 단일 uvicorn 워커 전제의 프로세스 메모리(`MemoryRateStore`).
워커를 늘리기 전에 `RateStore` 를 Redis/플랫폼 DB 구현으로 교체해야 한다.
"""

from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from typing import Deque, Protocol

from fastapi import HTTPException, Request

from app.config import settings


class RateStore(Protocol):
    def hit(self, key: str, now: float, window: float, limit: int) -> bool:
        """요청을 기록하고 허용이면 True. 한도 초과면 기록하지 않고 False."""


class MemoryRateStore:
    def __init__(self) -> None:
        self._buckets: dict[str, Deque[float]] = defaultdict(deque)

    def hit(self, key: str, now: float, window: float, limit: int) -> bool:
        q = self._buckets[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


_store: RateStore = MemoryRateStore()


def set_rate_store(store: RateStore) -> None:
    global _store
    _store = store


def _limit_per_minute() -> int:
    return max(1, int(getattr(settings, "ai_rate_limit_per_minute", 30) or 30))


def _trusted_proxies() -> set[str]:
    raw = getattr(settings, "ai_trusted_proxies", "127.0.0.1,::1") or ""
    return {part.strip() for part in raw.split(",") if part.strip()}


def _valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _user_id(request: Request) -> str | None:
    from app.platform.jwt_util import COOKIE_NAME, decode_access_token

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except Exception:  # noqa: BLE001
        return None
    sub = str((payload or {}).get("sub") or "")
    return sub if sub.isdigit() else None


def _client_key(request: Request) -> str:
    user_id = _user_id(request)
    if user_id:
        return f"user:{user_id}"
    peer = request.client.host if request.client else ""
    if peer and peer in _trusted_proxies():
        real = (request.headers.get("x-real-ip") or "").strip()
        if real and _valid_ip(real):
            return f"ip:{real}"
    return f"ip:{peer or 'unknown'}"


def check_ai_rate_limit(request: Request) -> None:
    """분당 요청 상한 초과 시 429."""
    limit = _limit_per_minute()
    if not _store.hit(_client_key(request), time.time(), 60.0, limit):
        raise HTTPException(
            status_code=429,
            detail=f"AI 요청 한도 초과(분당 {limit}회). 잠시 후 다시 시도해 주세요.",
        )
