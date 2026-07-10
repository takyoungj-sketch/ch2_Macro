"""Map Hub API — VWorld 경계 GeoJSON."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.config import settings
from app.map.vworld_client import fetch_context_collection

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/config")
def map_config():
    key = (settings.vworld_api_key or "").strip()
    return {
        "vworld_configured": bool(key),
        "tile_base": "https://api.vworld.kr/req/wmts/1.0.0",
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
):
    """
    동일 행정 레벨 경계 FeatureCollection.
    `selected` — highlight 대상 코드.
    기본 맥락은 상위 행정 범위(리는 시군구) + 선택 bbox 버퍼로 경계 너머 이웃 보강.
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
        fc = fetch_context_collection(
            api_key=key,
            domain=domain,
            level=norm_level,
            selected_codes=selected_codes,
            context_sido_code=context_sido_code,
            context_sigungu_code=context_sigungu_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "level": norm_level,
        "selected": selected_codes,
        "feature_collection": fc,
    }
