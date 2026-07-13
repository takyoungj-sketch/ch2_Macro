"""Map Hub API — VWorld 경계 GeoJSON · neighbor 그래프."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.map.neighbors import (
    canonicalize_code_for_level,
    fetch_neighbor_codes,
    neighbor_edge_count,
    normalize_neighbor_level,
    union_neighbor_codes,
)
from app.map.vworld_client import (
    fetch_context_collection,
    fetch_viewport_collection,
    parse_bbox_param,
)

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/config")
def map_config(db: Session = Depends(get_db)):
    key = (settings.vworld_api_key or "").strip()
    edges = neighbor_edge_count(db)
    return {
        "vworld_configured": bool(key),
        "tile_base": "https://api.vworld.kr/req/wmts/1.0.0",
        "neighbor_graph_ready": edges > 0,
        "neighbor_edge_count": edges,
    }


def _resolve_selected(request: Request, selected: list[str]) -> list[str]:
    """selected=… 및 axios 기본 selected[]=… 모두 수용."""
    out = [c.strip() for c in selected if c and str(c).strip()]
    if out:
        return out
    bracketed = request.query_params.getlist("selected[]")
    return [c.strip() for c in bracketed if c and str(c).strip()]


@router.get("/boundaries")
def map_boundaries(
    request: Request,
    level: str = Query(..., description="sido | sigungu | eupmyeondong | beopjungri"),
    selected: list[str] = Query(default=[]),
    context_sido_code: str | None = Query(None),
    context_sigungu_code: str | None = Query(None),
    bbox: str | None = Query(
        None,
        description="Display: west,south,east,north (viewport). 있으면 viewport 로드.",
    ),
):
    """
    동일 행정 레벨 경계 FeatureCollection.

    - bbox 있음 → Display SSOT (viewport)
    - bbox 없음 → 레거시 context(시군구+이웃링) 폴백
    """
    key = (settings.vworld_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="VWORLD_API_KEY가 설정되지 않았습니다. backend/.env 를 확인하세요.",
        )
    domain = (settings.vworld_api_domain or "localhost").strip()
    norm_level = level.strip().lower()
    if norm_level not in ("sido", "sigungu", "eupmyeondong", "beopjungri"):
        raise HTTPException(status_code=400, detail="지원하지 않는 level 입니다.")

    selected_codes = _resolve_selected(request, selected)

    try:
        bbox_t = parse_bbox_param(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        if bbox_t is not None:
            fc = fetch_viewport_collection(
                api_key=key,
                domain=domain,
                level=norm_level,
                bbox=bbox_t,
                selected_codes=selected_codes,
            )
            mode = "viewport"
        else:
            fc = fetch_context_collection(
                api_key=key,
                domain=domain,
                level=norm_level,
                selected_codes=selected_codes,
                context_sido_code=context_sido_code,
                context_sigungu_code=context_sigungu_code,
            )
            mode = "context"
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "level": norm_level,
        "selected": selected_codes,
        "mode": mode,
        "feature_collection": fc,
    }


@router.get("/neighbors")
def map_neighbors(
    request: Request,
    db: Session = Depends(get_db),
    level: str = Query(..., description="eupmyeondong | beopjungri"),
    codes: list[str] = Query(default=[]),
):
    """Selection SSOT — 선택 코드들의 위상 이웃 합집합."""
    try:
        lv = normalize_neighbor_level(level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raw_codes = [c.strip() for c in codes if c and str(c).strip()]
    if not raw_codes:
        bracketed = request.query_params.getlist("codes[]")
        raw_codes = [c.strip() for c in bracketed if c and str(c).strip()]

    canon = [canonicalize_code_for_level(lv, c) for c in raw_codes]
    canon = [c for c in canon if c]
    by_code = fetch_neighbor_codes(db, level=lv, codes=canon)
    union = union_neighbor_codes(db, level=lv, codes=canon)
    edges = neighbor_edge_count(db, level=lv)
    return {
        "level": lv,
        "codes": canon,
        "neighbors_by_code": by_code,
        "neighbor_codes": union,
        "graph_ready": edges > 0,
        "edge_count": edges,
    }
