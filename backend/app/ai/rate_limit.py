"""AI API — 간단 in-memory rate limit (운영 시 Redis 권장)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request

from app.config import settings

_buckets: dict[str, Deque[float]] = defaultdict(deque)


def _limit_per_minute() -> int:
    return max(1, int(getattr(settings, "ai_rate_limit_per_minute", 30) or 30))


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def check_ai_rate_limit(request: Request) -> None:
    """분당 요청 상한 초과 시 429."""
    key = _client_key(request)
    now = time.time()
    window = 60.0
    limit = _limit_per_minute()
    q = _buckets[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"AI 요청 한도 초과(분당 {limit}회). 잠시 후 다시 시도해 주세요.",
        )
    q.append(now)
