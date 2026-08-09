"""집합 meta DISTINCT 결과 TTL 캐시 — 시도 목록 등 반복 스캔 비용 완화."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")

_DEFAULT_TTL_SEC = 3600.0
_store: dict[str, tuple[float, object]] = {}


def get_ttl_cached(key: str, factory: Callable[[], T], *, ttl_sec: float = _DEFAULT_TTL_SEC) -> T:
    now = time.monotonic()
    hit = _store.get(key)
    if hit is not None:
        ts, value = hit
        if now - ts < ttl_sec:
            return value  # type: ignore[return-value]
    value = factory()
    _store[key] = (now, value)
    return value


def clear_meta_cache() -> None:
    _store.clear()
