"""집합상가·공장 — 도로명 cluster → VWorld 도로중심선 (Road-A)."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.map.vworld_client import fetch_named_layer_features

_LOG = logging.getLogger(__name__)

# 도로명주소 도로 (LineString). 공공데이터포털 「국토부 도로명주소 도로」와 동일 원천.
VWORLD_ROAD_LAYER = "LT_L_SPRD"
ROAD_NAME_KEYS = ("rn", "rd_nm", "road_nm", "rn_nm", "sig_rd_nm", "name")
# 점 주변 검색 반경(~1.3km). 행정 bbox가 있으면 그걸 우선.
_POINT_BUFFER_DEG = 0.012
_MAX_FEATURES = 400

_SPACE_RE = re.compile(r"\s+")


def normalize_road_name(raw: str) -> str:
    return _SPACE_RE.sub("", (raw or "").strip())


def road_name_from_props(props: dict[str, Any]) -> str:
    for key in ROAD_NAME_KEYS:
        val = props.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    for key, val in props.items():
        if val is None:
            continue
        lk = str(key).lower()
        if lk in ROAD_NAME_KEYS or lk.endswith("_rn") or lk == "rn":
            text = str(val).strip()
            if text:
                return text
    return ""


def score_road_name(candidate: str, target: str) -> int:
    """정확 일치만 (부분 문자열은 '중앙로' vs '중앙로2길' 오탐)."""
    c = normalize_road_name(candidate)
    t = normalize_road_name(target)
    if c and t and c == t:
        return 100
    return 0


def filter_road_features(
    fc: dict[str, Any],
    *,
    road_name: str,
) -> dict[str, Any]:
    feats = [f for f in (fc.get("features") or []) if isinstance(f, dict)]
    scored: list[tuple[int, dict[str, Any]]] = []
    for feat in feats:
        props = feat.get("properties") or {}
        if not isinstance(props, dict):
            continue
        geom = feat.get("geometry")
        if not isinstance(geom, dict) or geom.get("type") not in {
            "LineString",
            "MultiLineString",
        }:
            continue
        score = score_road_name(road_name_from_props(props), road_name)
        if score:
            scored.append((score, feat))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return {"type": "FeatureCollection", "features": []}
    best = scored[0][0]
    keep = [f for s, f in scored if s == best]
    return {"type": "FeatureCollection", "features": keep}


def _box(west: float, south: float, east: float, north: float) -> str:
    return f"BOX({west},{south},{east},{north})"


def intersect_boxes(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    west = max(a[0], b[0])
    south = max(a[1], b[1])
    east = min(a[2], b[2])
    north = min(a[3], b[3])
    if east <= west or north <= south:
        return None
    return west, south, east, north


def resolve_search_box(
    *,
    west: Optional[float] = None,
    south: Optional[float] = None,
    east: Optional[float] = None,
    north: Optional[float] = None,
    longitude: Optional[float] = None,
    latitude: Optional[float] = None,
) -> tuple[float, float, float, float] | None:
    """행정 bbox ∩ 지오코딩 점 버퍼. 교집합이 비면 점 버퍼(또는 행정 bbox)만 쓴다."""
    admin: tuple[float, float, float, float] | None = None
    if (
        west is not None
        and south is not None
        and east is not None
        and north is not None
        and east > west
        and north > south
    ):
        admin = (west, south, east, north)
    point: tuple[float, float, float, float] | None = None
    if longitude is not None and latitude is not None:
        b = _POINT_BUFFER_DEG
        point = (longitude - b, latitude - b, longitude + b, latitude + b)
    if admin and point:
        return intersect_boxes(admin, point) or point
    return admin or point


def _liang_barsky(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    box: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    west, south, east, north = box
    dx, dy = x1 - x0, y1 - y0
    p = (-dx, dx, -dy, dy)
    q = (x0 - west, east - x0, y0 - south, north - y0)
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return None
            continue
        t = qi / pi
        if pi < 0:
            if t > u2:
                return None
            if t > u1:
                u1 = t
        else:
            if t < u1:
                return None
            if t < u2:
                u2 = t
    return x0 + u1 * dx, y0 + u1 * dy, x0 + u2 * dx, y0 + u2 * dy


def clip_linestring_to_box(
    coords: list,
    box: tuple[float, float, float, float],
) -> list[list[list[float]]]:
    """BOX로 자른 LineString 조각들 (각각 2점 이상)."""
    pts: list[tuple[float, float]] = []
    for pt in coords:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        try:
            pts.append((float(pt[0]), float(pt[1])))
        except (TypeError, ValueError):
            continue
    if len(pts) < 2:
        return []
    parts: list[list[list[float]]] = []
    current: list[list[float]] = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        clipped = _liang_barsky(x0, y0, x1, y1, box)
        if not clipped:
            if len(current) >= 2:
                parts.append(current)
            current = []
            continue
        cx0, cy0, cx1, cy1 = clipped
        if not current:
            current = [[cx0, cy0], [cx1, cy1]]
        else:
            last = current[-1]
            if last[0] != cx0 or last[1] != cy0:
                if len(current) >= 2:
                    parts.append(current)
                current = [[cx0, cy0], [cx1, cy1]]
            else:
                current.append([cx1, cy1])
    if len(current) >= 2:
        parts.append(current)
    return parts


def clip_feature_collection_to_box(
    fc: dict[str, Any],
    box: tuple[float, float, float, float],
) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    for feat in fc.get("features") or []:
        if not isinstance(feat, dict):
            continue
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            continue
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        rings: list[list] = []
        if gtype == "LineString" and isinstance(coords, list):
            rings = [coords]
        elif gtype == "MultiLineString" and isinstance(coords, list):
            rings = [c for c in coords if isinstance(c, list)]
        else:
            continue
        clipped: list[list[list[float]]] = []
        for ring in rings:
            clipped.extend(clip_linestring_to_box(ring, box))
        if not clipped:
            continue
        if len(clipped) == 1:
            new_geom: dict[str, Any] = {"type": "LineString", "coordinates": clipped[0]}
        else:
            new_geom = {"type": "MultiLineString", "coordinates": clipped}
        out.append(
            {
                "type": "Feature",
                "properties": dict(feat.get("properties") or {}),
                "geometry": new_geom,
            }
        )
    return {"type": "FeatureCollection", "features": out}


def fetch_road_line_collection(
    *,
    api_key: str,
    domain: str,
    road_name: str,
    west: Optional[float] = None,
    south: Optional[float] = None,
    east: Optional[float] = None,
    north: Optional[float] = None,
    longitude: Optional[float] = None,
    latitude: Optional[float] = None,
) -> dict[str, Any]:
    """bbox 또는 지오코딩 점 주변에서 도로명과 맞는 중심선을 고른다."""
    name = (road_name or "").strip()
    box = resolve_search_box(
        west=west,
        south=south,
        east=east,
        north=north,
        longitude=longitude,
        latitude=latitude,
    )
    if not name:
        return {"type": "FeatureCollection", "features": []}
    if not box:
        raise ValueError("bbox 또는 좌표가 필요합니다.")
    geom = _box(*box)

    raw_like = normalize_road_name(name)
    attempts: list[str | None] = [
        f"rn:=:{name}",
        f"rn:like:{raw_like}%",
        None,
    ]
    last: dict[str, Any] = {"type": "FeatureCollection", "features": []}
    matched: dict[str, Any] = last
    for attr in attempts:
        try:
            last = fetch_named_layer_features(
                api_key=api_key,
                domain=domain,
                data=VWORLD_ROAD_LAYER,
                attr_filter=attr,
                geom_filter=geom,
                size=_MAX_FEATURES,
            )
        except ValueError as exc:
            _LOG.info("VWorld road line %s: %s", attr or "bbox", exc)
            continue
        matched = filter_road_features(last, road_name=name)
        if matched["features"]:
            break
    return clip_feature_collection_to_box(matched, box)
