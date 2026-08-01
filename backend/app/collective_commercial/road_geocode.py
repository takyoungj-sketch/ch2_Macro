"""집합상가·공장 도로명 → 좌표 (VWorld Search)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

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


def resolve_commercial_map_points(
    conn: Connection,
    *,
    api_key: str,
    roads: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """도로명 cluster 대표점을 지오코딩하고 DB에 캐시한다."""
    table = conn.execute(
        text("SELECT to_regclass('public.collective_commercial_map_geocodes')::text")
    ).scalar()
    if not table:
        raise RuntimeError(
            "collective_commercial_map_geocodes 테이블이 없습니다. "
            "db/030 적용 필요"
        )

    keys = [str(item["cluster_key"]).strip() for item in roads]
    cached = {
        str(row["cluster_key"]): row
        for row in conn.execute(
            text(
                """
                SELECT cluster_key, label, longitude, latitude, status
                FROM collective_commercial_map_geocodes
                WHERE cluster_key = ANY(:keys)
                """
            ),
            {"keys": keys},
        ).mappings()
    }

    points: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for item in roads:
        key = str(item["cluster_key"]).strip()
        label = str(item.get("label") or item.get("road_name") or key).strip()
        row = cached.get(key)
        if row and row["status"] == "ok" and row["longitude"] is not None:
            points.append(
                {
                    "cluster_key": key,
                    "label": str(row["label"] or label),
                    "longitude": float(row["longitude"]),
                    "latitude": float(row["latitude"]),
                }
            )
            continue

        query = build_road_query(
            addr1=str(item.get("addr1") or ""),
            addr2=str(item.get("addr2") or ""),
            addr3=str(item.get("addr3") or ""),
            addr4=str(item.get("addr4") or ""),
            road_name=str(item.get("road_name") or ""),
        )
        result = geocode_commercial_road(
            api_key=api_key,
            addr1=str(item.get("addr1") or ""),
            addr2=str(item.get("addr2") or ""),
            addr3=str(item.get("addr3") or ""),
            addr4=str(item.get("addr4") or ""),
            road_name=str(item.get("road_name") or ""),
        )
        status = "ok" if result.get("ok") else "not_found"
        conn.execute(
            text(
                """
                INSERT INTO collective_commercial_map_geocodes (
                    cluster_key, label, normalized_query, longitude, latitude,
                    matched_name, category, status, error, geocoded_at, updated_at
                ) VALUES (
                    :key, :label, :query, :longitude, :latitude, :matched,
                    :category, :status, :error,
                    CASE WHEN :ok THEN NOW() ELSE NULL END, NOW()
                )
                ON CONFLICT (cluster_key) DO UPDATE SET
                    label = EXCLUDED.label,
                    normalized_query = EXCLUDED.normalized_query,
                    longitude = EXCLUDED.longitude,
                    latitude = EXCLUDED.latitude,
                    matched_name = EXCLUDED.matched_name,
                    category = EXCLUDED.category,
                    status = EXCLUDED.status,
                    error = EXCLUDED.error,
                    geocoded_at = EXCLUDED.geocoded_at,
                    updated_at = NOW()
                """
            ),
            {
                "key": key,
                "label": label,
                "query": query,
                "longitude": result.get("longitude"),
                "latitude": result.get("latitude"),
                "matched": result.get("matched_name"),
                "category": result.get("category"),
                "status": status,
                "error": result.get("error"),
                "ok": bool(result.get("ok")),
            },
        )
        if result.get("ok") and result.get("longitude") is not None:
            points.append(
                {
                    "cluster_key": key,
                    "label": label,
                    "longitude": float(result["longitude"]),
                    "latitude": float(result["latitude"]),
                }
            )
        else:
            unresolved.append(key)

    conn.commit()
    return points, unresolved
