"""회귀계수 자연어 해석 — 모형 탐색 R4."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from app.ai.built_narrative import _human_name, _is_categorical, _rank_magnitudes
from app.recommendation.models import CoefficientNarrative

if TYPE_CHECKING:
    from app.built.schemas import RegressionCoeff, ResponseScale


def _format_amount_won(estimate: float, response_scale: str) -> str:
    if response_scale == "log":
        pct = (math.exp(estimate) - 1.0) * 100.0
        if abs(pct) >= 1:
            return f"약 {pct:+.1f}%"
        return f"약 {pct:+.2f}%"
    return f"약 **{abs(estimate):,.0f}만원**"


def _narrative_line(
    name: str,
    estimate: float,
    p_value: float | None,
    response_scale: str,
) -> str | None:
    label = _human_name(name)
    sig = p_value is not None and p_value < 0.05

    if _is_categorical(name):
        direction = "높" if estimate > 0 else "낮"
        amt = _format_amount_won(estimate, response_scale)
        base = (
            f"동일 조건에서는 **{label}**이(가) 기준 범주 대비 {amt} {direction}은 경향을 보입니다."
        )
        if not sig:
            base += " (통계적 유의성은 낮음)"
        return base

    if estimate > 0:
        base = f"**{label}** 증가가 다른 변수를 통제한 상태에서 거래금액 **상승**과 연관됩니다."
    elif estimate < 0:
        base = f"**{label}** 증가가 다른 변수를 통제한 상태에서 거래금액 **하락**과 연관됩니다."
    else:
        return None
    if not sig:
        base += " (통계적 유의성은 낮음)"
    return base


def build_coefficient_narratives(
    coefficients: list,
    *,
    response_scale: str,
    limit: int = 6,
) -> list[CoefficientNarrative]:
    if not coefficients:
        return []

    dicts = [c.model_dump() for c in coefficients]
    ranks = _rank_magnitudes(dicts)
    sig_sorted = sorted(
        [c for c in coefficients if c.p_value is not None and c.p_value < 0.05],
        key=lambda c: abs(c.estimate),
        reverse=True,
    )
    top_name = sig_sorted[0].name if sig_sorted else None

    ordered = sig_sorted + [
        c
        for c in sorted(coefficients, key=lambda x: abs(x.estimate), reverse=True)
        if c not in sig_sorted
    ]

    out: list[CoefficientNarrative] = []
    for c in ordered[:limit]:
        text = _narrative_line(c.name, c.estimate, c.p_value, response_scale)
        if not text:
            continue
        mag = ranks.get(c.name, "")
        if mag == "큼" and c.name == top_name and "가장" not in text:
            text = text.replace("연관됩니다.", "연관되며, 이번 모형에서 **가장 큰 기여** 후보입니다.")
            text = text.replace("경향을 보입니다.", "경향을 보이며, 이번 모형에서 **가장 큰 기여** 후보입니다.")
        out.append(
            CoefficientNarrative(
                name=c.name,
                label_ko=_human_name(c.name),
                text_ko=text,
                significant=c.p_value is not None and c.p_value < 0.05,
                is_top_contributor=c.name == top_name,
            )
        )
    return out
