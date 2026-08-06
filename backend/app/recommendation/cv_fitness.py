"""CV-MAPE 예측 적합 등급 — UI 표시용 (R3.5)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CvFitnessTone = Literal["positive", "neutral", "warning", "negative"]


class CvFitnessTier(BaseModel):
    tier: str
    label_ko: str
    tone: CvFitnessTone
    max_cv_mape: float | None = None


_TIERS: tuple[tuple[float, str, str, CvFitnessTone], ...] = (
    (15.0, "excellent", "매우 우수", "positive"),
    (25.0, "good", "우수", "positive"),
    (40.0, "fair", "보통", "neutral"),
    (60.0, "caution", "주의", "warning"),
    (9999.0, "unsuitable", "예측 부적합", "negative"),
)


def lookup_cv_fitness(cv_mape: float | None) -> CvFitnessTier:
    if cv_mape is None:
        return CvFitnessTier(tier="unknown", label_ko="CV 미산출", tone="neutral")
    for max_cv, tier, label, tone in _TIERS:
        if cv_mape < max_cv:
            return CvFitnessTier(tier=tier, label_ko=label, tone=tone, max_cv_mape=max_cv)
    return CvFitnessTier(tier="unsuitable", label_ko="예측 부적합", tone="negative")
