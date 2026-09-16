"""Insight 02 공개 페이로드. 시장규모 랩 compute를 내부에서만 쓴다."""

from __future__ import annotations

import threading
from typing import Any

from app.regional_profile.market_size_lab import MIX_TYPES, PRICE_TYPES, compute_market_size

_CACHE: dict[str, Any] | None = None
_LOCK = threading.Lock()

_PROFILE_VERSION = "v2.1-national"
_WINDOW_YEARS = 3
_REGION_LEVEL = "sigungu"


def _corr(block: Any) -> dict[str, Any]:
    if not isinstance(block, dict):
        return {"n": 0, "r": None, "n_pop": 0, "r_pop": None}
    return {
        "n": int(block.get("n") or 0),
        "r": block.get("r"),
        "n_pop": int(block.get("n_pop") or 0),
        "r_pop": block.get("r_pop"),
    }


def public_insight_02(raw: dict[str, Any]) -> dict[str, Any]:
    """랩 JSON에서 시군구 규모·단가 상관만 남긴다. share·lab·내부를 밖으로 안 낸다."""
    pairs_out: list[dict[str, Any]] = []
    for row in raw.get("pairs") or []:
        if not isinstance(row, dict):
            continue
        pairs_out.append(
            {
                "a": row.get("a"),
                "b": row.get("b"),
                "amount": _corr(row.get("amount")),
                "count": _corr(row.get("count")),
            }
        )
    price_out: list[dict[str, Any]] = []
    for row in raw.get("price_pairs") or []:
        if not isinstance(row, dict):
            continue
        price = row.get("price") if isinstance(row.get("price"), dict) else {}
        price_out.append(
            {
                "a": row.get("a"),
                "b": row.get("b"),
                "n": int(price.get("n") or 0),
                "r": price.get("r"),
            }
        )
    as_of = raw.get("as_of_month")
    if hasattr(as_of, "isoformat"):
        as_of = as_of.isoformat()
    return {
        "id": "02",
        "status": "open",
        "grain": "sigungu",
        "window_years": int(raw.get("window_years") or _WINDOW_YEARS),
        "as_of": as_of,
        "n": int(raw.get("n") or 0),
        "universe_n": int(raw.get("universe_n") or 0),
        "types": list(raw.get("types") or MIX_TYPES),
        "price_types": list(raw.get("price_types") or PRICE_TYPES),
        "price_missing_types": list(raw.get("price_missing_types") or []),
        "presence": list(raw.get("presence") or []),
        "pairs": pairs_out,
        "price_pairs": price_out,
        "note": "시군구 단면. 같은 3년 창. 상관이지 인과가 아니다. 결론이 아니다. 구성비가 아니다.",
    }


def _open_collective():
    from app.collective.db import get_collective_session_factory

    factory = get_collective_session_factory()
    if factory is None:
        raise FileNotFoundError("collective_stats DB 미연결")
    return factory()


def compute_insight_02() -> dict[str, Any]:
    db = _open_collective()
    try:
        raw = compute_market_size(
            db,
            profile_version=_PROFILE_VERSION,
            window_years=_WINDOW_YEARS,
            region_level=_REGION_LEVEL,
        )
        return public_insight_02(raw)
    finally:
        db.close()


def get_insight_02(*, force: bool = False) -> dict[str, Any]:
    global _CACHE
    if not force:
        with _LOCK:
            if _CACHE is not None:
                return _CACHE
    payload = compute_insight_02()
    with _LOCK:
        _CACHE = payload
    return payload


def compute_insight_02_scatter(a: str, b: str, metric: str) -> dict[str, Any]:
    sa = (a or "").strip()
    sb = (b or "").strip()
    met = metric if metric in ("amount", "count", "price") else "amount"
    if not sa or not sb or sa == sb:
        raise ValueError("유형 쌍이 필요합니다.")
    if met == "price":
        if sa not in PRICE_TYPES or sb not in PRICE_TYPES:
            raise ValueError("단가 산점도는 토지를 제외한 유형만 됩니다.")
    else:
        if sa not in MIX_TYPES or sb not in MIX_TYPES:
            raise ValueError("규모 산점도는 8유형만 됩니다.")
    db = _open_collective()
    try:
        raw = compute_market_size(
            db,
            profile_version=_PROFILE_VERSION,
            window_years=_WINDOW_YEARS,
            region_level=_REGION_LEVEL,
            scatter_a=sa,
            scatter_b=sb,
            scatter_metric=met,
        )
    finally:
        db.close()
    scatter = raw.get("scatter")
    if not isinstance(scatter, dict):
        raise LookupError("산점도를 만들지 못했습니다.")
    return {
        "a": scatter.get("a"),
        "b": scatter.get("b"),
        "metric": scatter.get("metric"),
        "log": True,
        "n_positive": int(scatter.get("n_positive") or 0),
        "points": list(scatter.get("points") or []),
    }
