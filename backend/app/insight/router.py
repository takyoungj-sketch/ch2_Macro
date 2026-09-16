"""공개 Macro Insight. /lab/ 가 아님."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.insight.public import get_insight_01
from app.insight.public_02 import compute_insight_02_scatter, get_insight_02

router = APIRouter(prefix="/insight", tags=["macro-insight"])


@router.get("/01")
def insight_01():
    """전국 월 · 금리·M2 × 거래 건수·액. 랩 API를 프록시하지 않는다."""
    try:
        return get_insight_01()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/02")
def insight_02():
    """시군구 · 최근 3년 · 유형 로그 규모·단가 상관. 랩 API를 프록시하지 않는다."""
    try:
        return get_insight_02()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/02/scatter")
def insight_02_scatter(
    a: str = Query(..., min_length=1),
    b: str = Query(..., min_length=1),
    metric: str = Query("amount", pattern="^(amount|count|price)$"),
):
    try:
        return compute_insight_02_scatter(a, b, metric)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
