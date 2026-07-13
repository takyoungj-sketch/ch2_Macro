"""집합상가·공장 도로명 → 좌표 (VWorld Search)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any, Optional

_LOG = logging.getLogger(__name__)

VWORLD_SEARCH_URL = "https://api.vworld.kr/req/search"


def build_road_query(
    *,
    addr1: str,
    addr2: str,
    road_name: str,
    addr3: Optional[str] = None,
    addr4: Optional[str] = None,
) -> str:
    parts = [
        (addr1 or "").strip(),
        (addr2 or "").strip(),
        (addr3 or "").strip(),
        (addr4 or "").strip(),
        (road_name or "").strip(),
    ]
    return " ".join(p for p in parts if p)


def _parse_point(item: dict[str, Any]) -> tuple[float, float] | None:
    point = item.get("point")
    if isinstance(point, dict):
        try:
            return float(point["x"]), float(point["y"])
        except (KeyError, TypeError, ValueError):
            pass
    geom = item.get("geometry")
    if isinstance(geom, str) and "," in geom:
        # occasional "x,y"
        try:
            a, b = geom.split(",", 1)
            return float(a.strip()), float(b.strip())
        except ValueError:
            pass
    return None


def _vworld_search(
    *,
    api_key: str,
    query: str,
    category: str,
) -> dict[str, Any] | None:
    params = {
        "service": "search",
        "request": "search",
        "version": "2.0",
        "crs": "EPSG:4326",
        "size": "5",
        "page": "1",
        "query": query,
        "type": "address",
        "category": category,
        "format": "json",
        "errorformat": "json",
        "key": api_key,
    }
    url = f"{VWORLD_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ch2-macro-road-geocode/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise ValueError(f"VWorld search HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"VWorld search network error: {exc}") from exc

    response = raw.get("response") if isinstance(raw, dict) else None
    if not isinstance(response, dict):
        return None
    if response.get("status") != "OK":
        return None
    items = (response.get("result") or {}).get("items") or []
    if not items:
        return None
    first = items[0]
    if not isinstance(first, dict):
        return None
    xy = _parse_point(first)
    if not xy:
        return None
    lng, lat = xy
    title = first.get("title")
    addr = first.get("address")
    matched = None
    if isinstance(title, str) and title.strip():
        matched = title.strip()
    elif isinstance(addr, dict):
        matched = (
            addr.get("road")
            or addr.get("parcel")
            or addr.get("bldnm")
            or None
        )
        if matched is not None:
            matched = str(matched).strip() or None
    elif isinstance(addr, str) and addr.strip():
        matched = addr.strip()
    return {
        "longitude": lng,
        "latitude": lat,
        "matched_name": matched,
        "category": category,
    }


@lru_cache(maxsize=512)
def geocode_vworld_cached(
    api_key: str,
    query: str,
    categories: tuple[str, ...] = ("road", "parcel"),
) -> tuple[float, float, str | None, str] | None:
    """(lng, lat, matched_name, category) or None."""
    q = (query or "").strip()
    if not q or not api_key:
        return None
    for category in categories:
        try:
            hit = _vworld_search(api_key=api_key, query=q, category=category)
        except ValueError as exc:
            _LOG.warning("vworld geocode %s failed: %s", category, exc)
            continue
        if hit:
            return (
                float(hit["longitude"]),
                float(hit["latitude"]),
                hit.get("matched_name"),
                category,
            )
    return None


def geocode_road_cached(api_key: str, query: str) -> tuple[float, float, str | None, str] | None:
    """도로명 우선 (상업 Road-B)."""
    return geocode_vworld_cached(api_key, query, ("road", "parcel"))


def geocode_commercial_road(
    *,
    api_key: str,
    addr1: str,
    addr2: str,
    road_name: str,
    addr3: Optional[str] = None,
    addr4: Optional[str] = None,
) -> dict[str, Any]:
    query = build_road_query(
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr4=addr4,
        road_name=road_name,
    )
    if not query:
        return {"ok": False, "query": query, "error": "empty_query"}
    hit = geocode_road_cached(api_key.strip(), query)
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
