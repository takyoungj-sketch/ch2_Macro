"""Insight 01 공개 페이로드. G3 compute_macro_ts를 내부에서만 쓴다."""

from __future__ import annotations

import threading
from typing import Any

from app.regional_profile.macro_ts_lab import compute_macro_ts

_CACHE: dict[str, Any] | None = None
_LOCK = threading.Lock()


def public_insight_01(raw: dict[str, Any]) -> dict[str, Any]:
    """랩 JSON에서 공개 창에 올릴 월 시계열·상관만 남긴다. lab 필드를 밖으로 안 낸다."""
    periods = [str(p) for p in (raw.get("periods") or [])]
    as_of = periods[-1] if periods else None
    period_start = periods[0] if periods else None
    rates_out: dict[str, Any] = {}
    for rid, block in (raw.get("rates") or {}).items():
        if not isinstance(block, dict):
            continue
        rates_out[str(rid)] = {
            "id": block.get("id") or rid,
            "label": block.get("label"),
            "role": block.get("role"),
            "unit": block.get("unit"),
            "values": list(block.get("values") or []),
            "d_pp": list(block.get("d_pp") or []),
        }
    m2 = raw.get("m2")
    m2_out = None
    if isinstance(m2, dict):
        m2_out = {
            "id": "m2",
            "label": m2.get("label") or "M2(평잔, 계절조정)",
            "unit": m2.get("unit"),
            "values": list(m2.get("values") or []),
            "yoy_pct": list(m2.get("yoy_pct") or []),
        }
    series_out: dict[str, Any] = {}
    for name, block in (raw.get("series") or {}).items():
        if not isinstance(block, dict):
            continue
        series_out[str(name)] = {
            "count": list(block.get("count") or []),
            "amount": list(block.get("amount") or []),
            "yoy_count": list(block.get("yoy_count") or []),
            "yoy_amount": list(block.get("yoy_amount") or []),
        }
    return {
        "id": "01",
        "status": "open",
        "grain": "calendar_month",
        "as_of": as_of,
        "period_start": period_start,
        "period_end": as_of,
        "default_rate": raw.get("default_rate") or "cd_91",
        "lags": list(raw.get("lags") or [0, 1, 3, 6]),
        "types": list(raw.get("types") or []),
        "rates": rates_out,
        "m2": m2_out,
        "series": series_out,
        "pairs": list(raw.get("pairs") or []),
        "coverage_notes": list(raw.get("coverage_notes") or []),
        "missing": list(raw.get("missing") or []),
        "note": "월·작년 같은 달 비교. 상관이지 인과가 아니다. 결론이 아니다.",
    }


def compute_insight_01() -> dict[str, Any]:
    from app.macro_ts.db import get_macro_ts_session_factory

    factory = get_macro_ts_session_factory()
    mts = factory() if factory is not None else None
    try:
        raw = compute_macro_ts(
            land_db=None,
            built_db=None,
            coll_db=None,
            macro_ts_db=mts,
            grain="calendar_month",
        )
        return public_insight_01(raw)
    finally:
        if mts is not None:
            mts.close()


def get_insight_01(*, force: bool = False) -> dict[str, Any]:
    global _CACHE
    if not force:
        with _LOCK:
            if _CACHE is not None:
                return _CACHE
    payload = compute_insight_01()
    with _LOCK:
        _CACHE = payload
    return payload
