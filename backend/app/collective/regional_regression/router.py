"""집합 지역회귀 API — 단지 1행. 유형은 기본통계와 같음(분양권 제외)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.collective.db import get_collective_db
from app.collective.regional_regression.engine import predict_regional, run_regional_regression
from app.collective.regional_regression.schemas import (
    RegionalRegressionPredictRequest,
    RegionalRegressionPredictResponse,
    RegionalRegressionRunRequest,
    RegionalRegressionRunResponse,
)

router = APIRouter(prefix="/analysis/regional-regression", tags=["집합부동산-지역회귀"])


@router.post("/run", response_model=RegionalRegressionRunResponse)
def regional_regression_run(
    body: RegionalRegressionRunRequest,
    db: Session = Depends(get_collective_db),
):
    if not body.addr1 or not body.addr2:
        raise HTTPException(400, detail="시·도를 선택하세요")
    if body.window_years not in (3, 5, 7):
        raise HTTPException(400, detail="통계 창은 3·5·7년만 지원합니다")
    try:
        return run_regional_regression(db.connection(), body)
    except RuntimeError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


class AptTwinRequest(BaseModel):
    addr1: str
    addr2: str
    addr4: str


class AptTwinListRequest(BaseModel):
    addr1: str
    addr2: str = ""
    addr4: str = ""
    region_code: str = ""


@router.post("/apt-twins")
def apt_twin_list(body: AptTwinListRequest, db: Session = Depends(get_collective_db)):
    """지역회귀 모달의 쌍둥이지역 탭. 아파트 재고·가격분포로 1–5위."""
    if not body.addr1.strip():
        raise HTTPException(400, detail="시·도를 선택하세요")
    from app.collective.regional_regression.apt_twin_lab import list_display_twins

    try:
        return list_display_twins(
            db.connection(),
            addr1=body.addr1,
            addr2=body.addr2,
            addr4=body.addr4,
            region_code=body.region_code,
        )
    except RuntimeError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


@router.post("/apt-twin")
def apt_twin_run(body: AptTwinRequest, db: Session = Depends(get_collective_db)):
    """관리자 실험. 아파트 재고 쌍둥이 1곳의 계수와 기준지역 CV-MAPE."""
    if not body.addr1.strip() or not body.addr2.strip() or not body.addr4.strip():
        raise HTTPException(400, detail="시도, 시군구, 읍면동을 입력하세요")
    from app.collective.regional_regression.apt_twin_lab import run_anchor

    try:
        return run_anchor(db.connection(), addr1=body.addr1, addr2=body.addr2, addr4=body.addr4)
    except RuntimeError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


@router.post("/predict", response_model=RegionalRegressionPredictResponse)
def regional_regression_predict(
    body: RegionalRegressionPredictRequest,
    db: Session = Depends(get_collective_db),
):
    try:
        raw = predict_regional(db.connection(), body, body.inputs)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    return RegionalRegressionPredictResponse(**raw)
