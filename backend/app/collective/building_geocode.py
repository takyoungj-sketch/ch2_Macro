"""주거 집합 건물 지번 → 좌표 (VWorld Search · parcel 우선)."""

from __future__ import annotations

from typing import Any

from app.collective_commercial.road_geocode import geocode_vworld_cached


def _clean(value: str | None) -> str:
    s = (value or "").strip()
    if not s or s == "—":
        return ""
    return s


def build_building_query(
    *,
    addr1: str,
    addr2: str,
    jibun_address: str | None = None,
    road_address: str | None = None,
) -> str:
    jibun = _clean(jibun_address)
    road = _clean(road_address)
    hint = jibun or road
    parts = [_clean(addr1), _clean(addr2), hint]
    return " ".join(p for p in parts if p)


def geocode_collective_building(
    *,
    api_key: str,
    addr1: str,
    addr2: str,
    jibun_address: str | None = None,
    road_address: str | None = None,
) -> dict[str, Any]:
    query = build_building_query(
        addr1=addr1,
        addr2=addr2,
        jibun_address=jibun_address,
        road_address=road_address,
    )
    if not query:
        return {"ok": False, "query": query, "error": "empty_query"}
    # 지번이 있으면 parcel 우선, 도로명만 있으면 road 우선
    jibun = _clean(jibun_address)
    categories = ("parcel", "road") if jibun else ("road", "parcel")
    hit = geocode_vworld_cached(api_key.strip(), query, categories)
    if not hit:
        return {"ok": False, "query": query, "error": "not_found"}
    lng, lat, matched, category = hit
    return {
        "ok": True,
        "query": query,
        "longitude": lng,
        "latitude": lat,
        "matched_name": matched,
        "category": category,
        "error": None,
    }
