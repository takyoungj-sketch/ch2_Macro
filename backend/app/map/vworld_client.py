"""VWorld Data API 2.0 — 행정 경계 GeoJSON (서버 프록시)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_LOG = logging.getLogger(__name__)

VWORLD_DATA_URL = "https://api.vworld.kr/req/data"

# (data layer, attribute field for region code)
LAYER_BY_LEVEL: dict[str, tuple[str, str]] = {
    "sido": ("LT_C_ADSIDO_INFO", "ctprvn_cd"),
    "sigungu": ("LT_C_ADSIGG_INFO", "sig_cd"),
    "eupmyeondong": ("LT_C_ADEMD_INFO", "emd_cd"),
    # 법정동(…00) → 읍면동 8자리 emd_cd, 리 → LT_C_ADRI_INFO li_cd
    "beopjungri": ("LT_C_ADEMD_INFO", "emd_cd"),
    "beopjungri_ri": ("LT_C_ADRI_INFO", "li_cd"),
}

# 선택 지역 bbox 버퍼(도) — 상위 경계를 넘는 동일 레벨 이웃 보강 (~5km)
_NEIGHBOR_BUFFER_DEG = 0.05
_NEIGHBOR_FETCH_SIZE = 500
# 선택 지역 대비 bbox 면적이 이 배수 초과인 읍·면 등은
# 선택과 떨어져 있으면 제외(시내 줌 거미줄 방지).
# 선택과 맞닿거나 겹치면 인접 선택용으로 유지.
_MAX_CONTEXT_BBOX_AREA_RATIO = 10.0
# 인접 판정용 선택 bbox 패딩(~200m)
_PRUNE_KEEP_NEAR_PAD_DEG = 0.002


def _first_numeric_depth(coords: Any, depth: int = 0) -> int:
    """좌표 배열에서 첫 숫자(경도)까지의 깊이. Point=1, Ring=2, Polygon=3, MultiPolygon=4."""
    if not isinstance(coords, (list, tuple)) or not coords:
        return depth
    head = coords[0]
    if isinstance(head, (int, float)):
        return depth + 1
    return _first_numeric_depth(head, depth + 1)


def _fix_geometry(geom: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    GeoJSON 타입과 좌표 깊이가 어긋나면 MapLibre line 이 거미줄처럼 깨짐.
    - MultiPolygon 인데 ring 목록(깊이 3)만 온 경우 → 한 polygon 으로 감쌈
    - Polygon 인데 MultiPolygon 깊이(4)인 경우 → MultiPolygon 으로 승격
    이미 올바른 MultiPolygon(깊이 4)은 건드리지 않음.
    """
    if not geom or not isinstance(geom, dict):
        return geom
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "MultiPolygon" and isinstance(coords, list) and coords:
        depth = _first_numeric_depth(coords)
        if depth == 3:
            # [ring, ring, ...] (Polygon 형태) → [[ring, ring, ...]]
            return {"type": "MultiPolygon", "coordinates": [coords]}
        # depth == 4 → 정상 MultiPolygon, 그대로 둠
    if gtype == "Polygon" and isinstance(coords, list) and coords:
        depth = _first_numeric_depth(coords)
        if depth == 4:
            return {"type": "MultiPolygon", "coordinates": coords}
        # depth == 3 → 정상 Polygon
    if gtype == "GeometryCollection":
        geoms = geom.get("geometries") or []
        return {
            "type": "GeometryCollection",
            "geometries": [_fix_geometry(g) or g for g in geoms if isinstance(g, dict)],
        }
    return geom


def _normalize_features(raw: dict[str, Any]) -> dict[str, Any]:
    response = raw.get("response") or {}
    status = response.get("status")
    if status != "OK":
        err = response.get("error") if isinstance(response.get("error"), dict) else {}
        code = err.get("code") or status or "ERROR"
        text = err.get("text") or "VWorld status not OK"
        raise ValueError(f"VWorld {code}: {text}")
    result = response.get("result") or {}
    fc = result.get("featureCollection") or {}
    if fc.get("type") != "FeatureCollection":
        raise ValueError("VWorld response missing FeatureCollection")
    features = fc.get("features") or []
    out_features: list[dict[str, Any]] = []
    for feat in features:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        geom = _fix_geometry(feat.get("geometry"))
        if not geom:
            continue
        out_features.append(
            {
                "type": "Feature",
                "geometry": geom,
                "properties": dict(props),
            }
        )
    return {"type": "FeatureCollection", "features": out_features}


def fetch_features(
    *,
    api_key: str,
    domain: str,
    level: str,
    attr_filter: str | None = None,
    geom_filter: str | None = None,
    size: int = 1000,
) -> dict[str, Any]:
    layer, _ = LAYER_BY_LEVEL.get(level, ("", ""))
    if not layer:
        raise ValueError(f"unsupported level: {level}")

    params: dict[str, str] = {
        "service": "data",
        "request": "GetFeature",
        "data": layer,
        "key": api_key,
        "domain": domain,
        "format": "json",
        "size": str(min(max(size, 1), 1000)),
        "crs": "EPSG:4326",
    }
    if attr_filter:
        params["attrFilter"] = attr_filter
    if geom_filter:
        params["geomFilter"] = geom_filter

    url = f"{VWORLD_DATA_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ch2-macro-map/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        raise ValueError(f"VWorld HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"VWorld network error: {exc}") from exc

    return _normalize_features(raw)


def fetch_features_soft(
    *,
    api_key: str,
    domain: str,
    level: str,
    attr_filter: str | None = None,
    geom_filter: str | None = None,
    size: int = 1000,
) -> dict[str, Any]:
    """NOT_FOUND 등 빈 결과는 빈 FeatureCollection 으로 반환."""
    try:
        return fetch_features(
            api_key=api_key,
            domain=domain,
            level=level,
            attr_filter=attr_filter,
            geom_filter=geom_filter,
            size=size,
        )
    except ValueError as exc:
        msg = str(exc)
        if "NOT_FOUND" in msg or "status not OK" in msg:
            _LOG.info("VWorld soft empty: %s", msg)
            return {"type": "FeatureCollection", "features": []}
        raise


def _code_filter(level: str, code: str) -> str:
    _, field = LAYER_BY_LEVEL[level]
    c = code.strip()
    return f"{field}:=:{c}"


def _prefix_filter(level: str, prefix: str) -> str:
    _, field = LAYER_BY_LEVEL[level]
    p = prefix.strip()
    # VWorld attrFilter like — SQL 와일드카드 `%` (`*` 아님)
    return f"{field}:like:{p}%"


def _visit_coords(coords: Any, xs: list[float], ys: list[float]) -> None:
    if not coords:
        return
    if isinstance(coords[0], (int, float)) and len(coords) >= 2:
        xs.append(float(coords[0]))
        ys.append(float(coords[1]))
        return
    if isinstance(coords, (list, tuple)):
        for c in coords:
            _visit_coords(c, xs, ys)


def bbox_from_features(features: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for feat in features:
        geom = feat.get("geometry") or {}
        if geom.get("type") == "GeometryCollection":
            for g in geom.get("geometries") or []:
                if "coordinates" in g:
                    _visit_coords(g["coordinates"], xs, ys)
        elif "coordinates" in geom:
            _visit_coords(geom["coordinates"], xs, ys)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def bbox_area(bbox: tuple[float, float, float, float] | None) -> float:
    if not bbox:
        return 0.0
    west, south, east, north = bbox
    return max(0.0, east - west) * max(0.0, north - south)


def feature_bbox_area(feat: dict[str, Any]) -> float:
    return bbox_area(bbox_from_features([feat]))


def bboxes_touch_or_overlap(
    a: tuple[float, float, float, float] | None,
    b: tuple[float, float, float, float] | None,
) -> bool:
    """축정렬 bbox가 겹치거나 변·꼭짓점에서 맞닿으면 True."""
    if not a or not b:
        return False
    aw, as_, ae, an = a
    bw, bs, be, bn = b
    return not (ae < bw or be < aw or an < bs or bn < as_)


def _prune_oversized_features(
    fc: dict[str, Any],
    *,
    selected: list[str],
    max_ratio: float = _MAX_CONTEXT_BBOX_AREA_RATIO,
    near_pad_deg: float = _PRUNE_KEEP_NEAR_PAD_DEG,
) -> dict[str, Any]:
    """
    선택 지역보다 훨씬 큰 읍·면 polygon 중, 선택과 떨어진 것만 제외.
    인접(bbox 접촉·겹침)한 거대 면·읍은 지도 선택용으로 유지.
    """
    features = list(fc.get("features") or [])
    if not features or not selected:
        return fc
    selected_set = set(selected)
    selected_feats = [f for f in features if _feature_code(f) in selected_set]
    if not selected_feats:
        return fc
    sel_bbox = bbox_from_features(selected_feats)
    sel_area = bbox_area(sel_bbox)
    if sel_area <= 0 or not sel_bbox:
        return fc
    near_bbox = expand_bbox(sel_bbox, near_pad_deg)
    limit = sel_area * max_ratio
    kept: list[dict[str, Any]] = []
    dropped = 0
    kept_near_oversized = 0
    for feat in features:
        code = _feature_code(feat)
        if code in selected_set:
            kept.append(feat)
            continue
        area = feature_bbox_area(feat)
        if area > limit:
            feat_bbox = bbox_from_features([feat])
            if bboxes_touch_or_overlap(feat_bbox, near_bbox):
                kept.append(feat)
                kept_near_oversized += 1
                continue
            dropped += 1
            continue
        kept.append(feat)
    if dropped or kept_near_oversized:
        _LOG.info(
            "pruned oversized context features=%d kept_near_oversized=%d "
            "(sel_area=%.6f limit=%.6f) remain=%d",
            dropped,
            kept_near_oversized,
            sel_area,
            limit,
            len(kept),
        )
    return {"type": "FeatureCollection", "features": kept}


def expand_bbox(
    bbox: tuple[float, float, float, float],
    buffer_deg: float,
) -> tuple[float, float, float, float]:
    west, south, east, north = bbox
    return (west - buffer_deg, south - buffer_deg, east + buffer_deg, north + buffer_deg)


def box_geom_filter(bbox: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox
    return f"BOX({west},{south},{east},{north})"


def _stamp_ch2_codes(
    features: list[dict[str, Any]],
    *,
    request_level: str,
    effective_level: str,
) -> None:
    _, code_field = LAYER_BY_LEVEL.get(effective_level, ("", "code"))
    for feat in features:
        props = feat.setdefault("properties", {})
        raw_code = (
            props.get(code_field)
            or props.get("li_cd")
            or props.get("emd_cd")
            or props.get("sig_cd")
            or props.get("ctprvn_cd")
            or props.get("ch2_code")
        )
        if raw_code is None:
            continue
        code_str = str(raw_code).strip()
        if request_level == "beopjungri" and effective_level == "eupmyeondong" and len(code_str) == 8:
            props["ch2_code"] = code_str + "00"
        else:
            props["ch2_code"] = code_str


def _feature_code(feat: dict[str, Any]) -> str | None:
    props = feat.get("properties") or {}
    code = props.get("ch2_code")
    if code is None:
        return None
    s = str(code).strip()
    return s or None


def merge_feature_collections(
    *collections: dict[str, Any],
) -> dict[str, Any]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    anon = 0
    for fc in collections:
        for feat in fc.get("features") or []:
            code = _feature_code(feat)
            if code:
                if code in seen:
                    continue
                seen.add(code)
            else:
                anon += 1
                code = f"__anon_{anon}"
            out.append(feat)
    return {"type": "FeatureCollection", "features": out}


def _resolve_effective_level_and_filter(
    level: str,
    selected: list[str],
    context_sido_code: str | None,
    context_sigungu_code: str | None,
) -> tuple[str, str | None]:
    """기본 맥락 범위 — 리만 시군구 단위로 확대."""
    if level == "sido":
        if context_sido_code:
            return "sido", _code_filter("sido", context_sido_code)
        if selected:
            return "sido", _code_filter("sido", selected[0][:2])
        return "sido", None

    if level == "sigungu":
        sido_prefix = (context_sido_code or (selected[0][:2] if selected else ""))[:2]
        if sido_prefix:
            return "sigungu", _prefix_filter("sigungu", sido_prefix)
        return "sigungu", None

    if level == "eupmyeondong":
        prefix = context_sigungu_code or (selected[0][:5] if selected else "")
        if prefix:
            return "eupmyeondong", _prefix_filter("eupmyeondong", prefix[:5])
        return "eupmyeondong", None

    if level == "beopjungri":
        if selected and not selected[0].endswith("00"):
            # 리: 같은 시·군·구 전체 리 (읍면 한정 → 시군구로 확대)
            sig5 = (context_sigungu_code or selected[0][:5])[:5]
            if sig5:
                return "beopjungri_ri", _prefix_filter("beopjungri_ri", sig5)
            return "beopjungri_ri", None
        prefix = context_sigungu_code or (selected[0][:5] if selected else "")
        if prefix:
            return "eupmyeondong", _prefix_filter("eupmyeondong", prefix[:5])
        return "eupmyeondong", None

    return level, None


def _ensure_selected_features(
    *,
    api_key: str,
    domain: str,
    request_level: str,
    effective_level: str,
    selected: list[str],
    base_fc: dict[str, Any],
) -> dict[str, Any]:
    """선택 코드가 base 에 없으면 단건 조회로 보강 (bbox 산출용)."""
    present = {_feature_code(f) for f in (base_fc.get("features") or [])}
    missing = [c for c in selected if c not in present]
    if not missing:
        return base_fc

    extras: list[dict[str, Any]] = []
    for code in missing[:20]:
        filt: str | None = None
        fetch_level = effective_level
        if request_level == "beopjungri" and code.endswith("00") and len(code) >= 8:
            fetch_level = "eupmyeondong"
            filt = _code_filter("eupmyeondong", code[:8])
        elif request_level == "beopjungri" and not code.endswith("00"):
            fetch_level = "beopjungri_ri"
            filt = _code_filter("beopjungri_ri", code)
        elif request_level == "eupmyeondong":
            filt = _code_filter("eupmyeondong", code)
        elif request_level == "sigungu":
            filt = _code_filter("sigungu", code)
        elif request_level == "sido":
            filt = _code_filter("sido", code)
        if not filt:
            continue
        part = fetch_features_soft(
            api_key=api_key,
            domain=domain,
            level=fetch_level,
            attr_filter=filt,
            size=5,
        )
        _stamp_ch2_codes(
            part.get("features") or [],
            request_level=request_level,
            effective_level=fetch_level,
        )
        extras.append(part)

    if not extras:
        return base_fc
    return merge_feature_collections(base_fc, *extras)


def _append_neighbor_ring(
    *,
    api_key: str,
    domain: str,
    request_level: str,
    effective_level: str,
    selected: list[str],
    context_sigungu_code: str | None,
    base_fc: dict[str, Any],
) -> dict[str, Any]:
    """
    선택 지역 bbox+버퍼로 동일 레벨 이웃 추가.
    상위 행정구역이 달라도 경계 너머 인접 구역을 포함.
    (인접 시군구 전체 로드는 거대 읍·면 윤곽이 시내를 가로질러 제외 — geomFilter 만 사용)
    """
    if request_level == "sido" or not selected:
        return base_fc

    selected_set = set(selected)
    selected_feats = [
        f for f in (base_fc.get("features") or []) if _feature_code(f) in selected_set
    ]
    if not selected_feats:
        return base_fc

    bbox = bbox_from_features(selected_feats)
    if not bbox:
        return base_fc

    buffered = expand_bbox(bbox, _NEIGHBOR_BUFFER_DEG)
    geom = box_geom_filter(buffered)
    neighbor = fetch_features_soft(
        api_key=api_key,
        domain=domain,
        level=effective_level,
        geom_filter=geom,
        size=_NEIGHBOR_FETCH_SIZE,
    )
    _stamp_ch2_codes(
        neighbor.get("features") or [],
        request_level=request_level,
        effective_level=effective_level,
    )
    merged = merge_feature_collections(base_fc, neighbor)

    # 거대 읍·면이 버퍼에 살짝 걸려도 전체 윤곽이 시내를 가로지르므로
    # 최종 prune 은 fetch_context_collection 에서 수행.
    n = len(merged.get("features") or []) - len(base_fc.get("features") or [])
    if n > 0:
        _LOG.info(
            "neighbor ring level=%s effective=%s added≈%d total=%d",
            request_level,
            effective_level,
            n,
            len(merged.get("features") or []),
        )
    return merged


def fetch_context_collection(
    *,
    api_key: str,
    domain: str,
    level: str,
    selected_codes: list[str],
    context_sido_code: str | None,
    context_sigungu_code: str | None,
) -> dict[str, Any]:
    """
    동일 행정 레벨 경계 FeatureCollection.

    - 기본: 상위 범위 내 격자 (리는 시군구 단위)
    - 보강: 선택 지역 bbox+버퍼로 상위 경계를 넘는 이웃 포함
    """
    selected = [c.strip() for c in selected_codes if c and c.strip()]
    if not selected and not context_sido_code and not context_sigungu_code:
        return {"type": "FeatureCollection", "features": []}

    effective_level, attr_filter = _resolve_effective_level_and_filter(
        level, selected, context_sido_code, context_sigungu_code
    )

    fc = fetch_features(
        api_key=api_key,
        domain=domain,
        level=effective_level,
        attr_filter=attr_filter,
        size=1000,
    )
    _stamp_ch2_codes(
        fc.get("features") or [],
        request_level=level,
        effective_level=effective_level,
    )

    fc = _ensure_selected_features(
        api_key=api_key,
        domain=domain,
        request_level=level,
        effective_level=effective_level,
        selected=selected,
        base_fc=fc,
    )

    fc = _append_neighbor_ring(
        api_key=api_key,
        domain=domain,
        request_level=level,
        effective_level=effective_level,
        selected=selected,
        context_sigungu_code=context_sigungu_code,
        base_fc=fc,
    )

    if selected:
        fc = _prune_oversized_features(fc, selected=selected)

    return fc


def parse_bbox_param(raw: str | None) -> tuple[float, float, float, float] | None:
    """'west,south,east,north' → bbox."""
    if not raw or not str(raw).strip():
        return None
    parts = [p.strip() for p in str(raw).split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be west,south,east,north")
    try:
        west, south, east, north = (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
    except ValueError as exc:
        raise ValueError("bbox values must be numbers") from exc
    if east <= west or north <= south:
        raise ValueError("bbox east>west and north>south required")
    return (west, south, east, north)


def fetch_viewport_collection(
    *,
    api_key: str,
    domain: str,
    level: str,
    bbox: tuple[float, float, float, float],
    selected_codes: list[str],
    pad_deg: float = 0.01,
) -> dict[str, Any]:
    """
    Display SSOT — viewport bbox 내 동일 레벨 경계.
    선택 코드는 뷰 밖이어도 반드시 포함.
    """
    selected = [c.strip() for c in selected_codes if c and c.strip()]
    request_level = level.strip().lower()
    if request_level not in ("sido", "sigungu", "eupmyeondong", "beopjungri"):
        raise ValueError(f"unsupported level: {level}")

    # 리는 ADRI, 법정동(…00) 요청은 EMD 레이어
    if request_level == "beopjungri" and selected and not selected[0].endswith("00"):
        effective_level = "beopjungri_ri"
    elif request_level == "beopjungri":
        effective_level = "eupmyeondong"
    else:
        effective_level = request_level

    padded = expand_bbox(bbox, pad_deg)
    geom = box_geom_filter(padded)
    fc = fetch_features_soft(
        api_key=api_key,
        domain=domain,
        level=effective_level,
        geom_filter=geom,
        size=1000,
    )
    _stamp_ch2_codes(
        fc.get("features") or [],
        request_level=request_level,
        effective_level=effective_level,
    )

    if selected:
        fc = _ensure_selected_features(
            api_key=api_key,
            domain=domain,
            request_level=request_level,
            effective_level=effective_level,
            selected=selected,
            base_fc=fc,
        )
    return fc
