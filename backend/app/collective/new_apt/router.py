"""신규아파트 회귀 실험 API — 기존 건물 회귀 엔진과 분리."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.collective.db import get_collective_db
from app.collective.new_apt.constants import SIDO_DAEJEON, SUPPORTED_SIDOS
from app.collective.new_apt.schemas import NewAptExperimentResponse, NewAptRegionCompareResponse
from app.collective.new_apt.service import load_experiment, load_region_compare

router = APIRouter(prefix="/analysis/new-apt", tags=["집합부동산-신규아파트(실험)"])


@router.get("/experiment", response_model=NewAptExperimentResponse)
def new_apt_experiment(
    db: Session = Depends(get_collective_db),
    sido_code: str = Query(SIDO_DAEJEON, min_length=2, max_length=2),
):
    if sido_code not in SUPPORTED_SIDOS:
        raise HTTPException(400, detail="대전(30)·충북(43)만 지원합니다")
    try:
        return load_experiment(db.connection(), sido_code=sido_code)
    except RuntimeError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


@router.get("/region-compare", response_model=NewAptRegionCompareResponse)
def new_apt_region_compare(db: Session = Depends(get_collective_db)):
    try:
        return load_region_compare(db.connection())
    except RuntimeError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
