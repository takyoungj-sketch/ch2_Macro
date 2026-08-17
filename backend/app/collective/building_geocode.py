"""주거 집합 건물 지번 → 좌표 (VWorld Search · parcel 우선)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

_GEOCODE_TABLES = frozenset({"collective_building_geocodes", "rent_building_geocodes"})

from app.collective_commercial.road_geocode import geocode_vworld_cached


def _clean(value: str | None) -> str:
    s = (value or "").strip()
    if not s or s == "—":
        return ""
    return s


def address_is_masked(*parts: str | None) -> bool:
    """국토부 지번 가림(`1**`)은 필지를 특정할 수 없어 지도에 찍지 않는다."""
    return any("*" in (p or "") for p in parts)


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
    if address_is_masked(query, jibun_address, road_address):
        return {"ok": False, "query": query, "error": "masked_address"}
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


def _normalize_address(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def resolve_building_map_points(
    conn: Connection,
    *,
    api_key: str,
    buildings: list[dict[str, Any]],
    table_name: str = "collective_building_geocodes",
) -> tuple[list[dict[str, Any]], list[str]]:
    """주소를 지오코딩하고 결과를 DB에 캐시한다.

    지도 최초 조회에서만 VWorld를 호출하고, 이후에는 building_key 캐시를
    사용한다. 호출량을 제한하기 위해 API 스키마에서 최대 100건을 받는다.
    """
    if table_name not in _GEOCODE_TABLES:
        raise RuntimeError(f"unsupported geocode table: {table_name}")
    table = conn.execute(
        text("SELECT to_regclass(:reg)::text"),
        {"reg": f"public.{table_name}"},
    ).scalar()
    if not table:
        raise RuntimeError(f"{table_name} 테이블이 없습니다. DDL 적용 필요")

    keys = [str(item["building_key"]).strip() for item in buildings if str(item.get("building_key") or "").strip()]
    cached: dict[str, Any] = {}
    if keys:
        cached = {
            str(row["building_key"]): row
            for row in conn.execute(
                text(
                    f"""
                    SELECT building_key, label, longitude, latitude, status
                    FROM {table_name}
                    WHERE building_key IN :keys
                    """
                ).bindparams(bindparam("keys", expanding=True)),
                {"keys": keys},
            ).mappings()
        }

    points: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for item in buildings:
        key = str(item["building_key"]).strip()
        label = _normalize_address(str(item.get("label") or "")) or key
        jibun = _normalize_address(item.get("jibun_address"))
        road = _normalize_address(item.get("road_address"))
        if address_is_masked(jibun, road, label):
            unresolved.append(key)
            continue
        row = cached.get(key)
        if row and row["status"] == "ok" and row["longitude"] is not None:
            points.append(
                {
                    "building_key": key,
                    "label": str(row["label"] or label),
                    "longitude": float(row["longitude"]),
                    "latitude": float(row["latitude"]),
                }
            )
            continue

        result = geocode_collective_building(
            api_key=api_key,
            addr1=_normalize_address(item.get("addr1")),
            addr2=_normalize_address(item.get("addr2")),
            jibun_address=jibun or None,
            road_address=road or None,
        )
        status = "ok" if result.get("ok") else "not_found"
        conn.execute(
            text(
                f"""
                INSERT INTO {table_name} (
                    building_key, label, jibun_address, normalized_address,
                    longitude, latitude, matched_name, category, status,
                    error, geocoded_at, updated_at
                ) VALUES (
                    :key, :label, :jibun, :normalized, :longitude, :latitude,
                    :matched, :category, :status, :error,
                    CASE WHEN :ok THEN NOW() ELSE NULL END, NOW()
                )
                ON CONFLICT (building_key) DO UPDATE SET
                    label = EXCLUDED.label,
                    jibun_address = EXCLUDED.jibun_address,
                    normalized_address = EXCLUDED.normalized_address,
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
                "jibun": jibun or None,
                "normalized": " ".join(
                    p
                    for p in (
                        _normalize_address(item.get("addr1")),
                        _normalize_address(item.get("addr2")),
                        jibun or road,
                    )
                    if p
                ),
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
                    "building_key": key,
                    "label": label,
                    "longitude": float(result["longitude"]),
                    "latitude": float(result["latitude"]),
                }
            )
        else:
            unresolved.append(key)

    conn.commit()
    return points, unresolved
