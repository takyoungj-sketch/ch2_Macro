"""2단계 헤도닉 API — 품질지수·특성회귀 (실험)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.collective.db import get_collective_db
from app.collective.hedonic.schemas import (
    AttributeEffectsResponse,
    AttributeEffectsRunRequest,
    BuildingQualityResponse,
    MacroEffectsResponse,
    QualityIndexAnalysisResponse,
)
from app.collective.hedonic.service import (
    fetch_attribute_effects_mart,
    fetch_building_quality,
    fetch_macro_effects_mart,
    fetch_quality_index_analysis,
    run_attribute_effects_live,
)

router = APIRouter(prefix="/collective/analysis/hedonic", tags=["집합부동산-헤도닉(실험)"])


@router.get("/quality-index", response_model=QualityIndexAnalysisResponse)
def analysis_quality_index(
    db: Session = Depends(get_collective_db),
    as_of_month: Optional[date] = Query(None),
    window_years: int = Query(5, ge=1, le=7),
    sigungu_code: Optional[str] = Query(None, min_length=5, max_length=5),
    limit: int = Query(500, ge=1, le=5000),
):
    return fetch_quality_index_analysis(
        db.connection(),
        as_of_month=as_of_month,
        window_years=window_years,
        sigungu_code=sigungu_code,
        limit=limit,
    )


@router.get("/buildings/{building_key}/quality", response_model=BuildingQualityResponse)
def building_quality(
    building_key: str,
    db: Session = Depends(get_collective_db),
    as_of_month: Optional[date] = Query(None),
    window_years: int = Query(5, ge=1, le=7),
):
    return fetch_building_quality(
        db.connection(),
        building_key,
        as_of_month=as_of_month,
        window_years=window_years,
    )


@router.get("/attribute-effects", response_model=AttributeEffectsResponse)
def analysis_attribute_effects(
    db: Session = Depends(get_collective_db),
    as_of_month: Optional[date] = Query(None),
    window_years: int = Query(5, ge=1, le=7),
    spec: str = Query("A", pattern="^[ABC]$"),
    scope_level: str = Query("national"),
    scope_code: Optional[str] = Query(None),
    include_location: bool = Query(False),
    term_kind: Optional[str] = Query(None, description="brand|builder|scale|… 필터(응답 후 클라이언트 필터 권장)"),
):
    resp = fetch_attribute_effects_mart(
        db.connection(),
        as_of_month=as_of_month,
        window_years=window_years,
        spec=spec,
        scope_level=scope_level,
        scope_code=scope_code,
        include_location=include_location,
    )
    if term_kind:
        resp.coefficients = [c for c in resp.coefficients if c.term_kind == term_kind]
    return resp


@router.post("/attribute-effects/run", response_model=AttributeEffectsResponse)
def analysis_attribute_effects_run(
    body: AttributeEffectsRunRequest,
    db: Session = Depends(get_collective_db),
):
    return run_attribute_effects_live(db.connection(), body)


@router.get("/macro-effects", response_model=MacroEffectsResponse)
def analysis_macro_effects(
    db: Session = Depends(get_collective_db),
    as_of_month: Optional[date] = Query(None),
    window_years: int = Query(5, ge=1, le=7),
):
    return fetch_macro_effects_mart(
        db.connection(),
        as_of_month=as_of_month,
        window_years=window_years,
    )
