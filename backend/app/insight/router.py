"""공개 Macro Insight. /lab/ 가 아님."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.insight.public import get_insight_01

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
