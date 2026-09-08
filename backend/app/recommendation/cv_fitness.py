"""CV-MAPE 등 = 해석 강도. 합격/부적합이 아님 (D-067, D-068).

예측형 1위 선정은 CV-MAPE.
읽는 강도는 예측 오차·설명력·검증 안정성·표본을 같이 본다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CvFitnessTone = Literal["accent", "elevated", "high", "fail", "neutral"]

TWIN_OFFER_CV = 60.0
TWIN_OFFER_GAP_PP = 10.0
CLEAR_IMPROVE_PP = 5.0

ADJ_R2_LOW = 0.30
ADJ_R2_HIGH = 0.60
STABILITY_GAP_PP = 10.0
SAMPLE_FAIL_N = 30
SAMPLE_ADEQUATE_N = 100
SAMPLE_DROP_RATIO = 0.5


class CvFitnessTier(BaseModel):
    tier: str
    label_ko: str
    tone: CvFitnessTone
    max_cv_mape: float | None = None


class AxisReading(BaseModel):
    tier: str
    label_ko: str
    tone: CvFitnessTone = "neutral"
    detail_ko: str = ""


class MacroDiagnosis(BaseModel):
    error: AxisReading
    explanation: AxisReading
    stability: AxisReading
    sample: AxisReading
    composite: AxisReading
    error_one_liner_ko: str = ""
    summary_ko: str = ""


# 상한은 미만(<). 30→보통, 45→높은 편, 60→높음.
_CV_TIERS: tuple[tuple[float, str, str, CvFitnessTone], ...] = (
    (30.0, "low", "낮음", "accent"),
    (45.0, "moderate", "보통", "accent"),
    (60.0, "elevated", "높은 편", "elevated"),
    (9999.0, "high", "높음", "high"),
)


def lookup_cv_fitness(cv_mape: float | None) -> CvFitnessTier:
    if cv_mape is None:
        return CvFitnessTier(tier="unknown", label_ko="CV 미산출", tone="neutral")
    for max_cv, tier, label, tone in _CV_TIERS:
        if cv_mape < max_cv:
            return CvFitnessTier(tier=tier, label_ko=label, tone=tone, max_cv_mape=max_cv)
    return CvFitnessTier(tier="high", label_ko="높음", tone="high")


def cv_mape_gap_pp(mape: float | None, cv_mape: float | None) -> float | None:
    if mape is None or cv_mape is None:
        return None
    return round(float(cv_mape) - float(mape), 2)


def lookup_adj_r2(adj_r_squared: float | None) -> AxisReading:
    if adj_r_squared is None:
        return AxisReading(tier="unknown", label_ko="미산출", tone="neutral")
    v = float(adj_r_squared)
    if v < ADJ_R2_LOW:
        return AxisReading(tier="low", label_ko="낮음", tone="elevated")
    if v < ADJ_R2_HIGH:
        return AxisReading(tier="moderate", label_ko="보통", tone="accent")
    return AxisReading(tier="high", label_ko="높은 편", tone="accent")


def lookup_stability(mape: float | None, cv_mape: float | None) -> AxisReading:
    gap = cv_mape_gap_pp(mape, cv_mape)
    if gap is None:
        return AxisReading(tier="unknown", label_ko="미산출", tone="neutral")
    if mape is not None and cv_mape is not None:
        detail = f"MAPE {mape:.1f}% → CV-MAPE {cv_mape:.1f}%"
    else:
        detail = ""
    if gap >= STABILITY_GAP_PP:
        return AxisReading(
            tier="caution",
            label_ko="주의",
            tone="elevated",
            detail_ko=detail,
        )
    return AxisReading(tier="ok", label_ko="양호", tone="accent", detail_ko=detail)


def lookup_sample(
    *,
    fit_n: int,
    scope_n_tx: int,
    selection_n: int | None = None,
) -> AxisReading:
    n = int(fit_n or 0)
    scope = int(scope_n_tx or 0)
    drop = scope > 0 and n / scope < SAMPLE_DROP_RATIO
    if scope > 0:
        detail = f"분석 표본 {n}건 — 거래 {scope}건 중 {n}건만 회귀에 사용"
    else:
        detail = f"분석 표본 {n}건"
    if n < SAMPLE_FAIL_N:
        return AxisReading(
            tier="insufficient",
            label_ko="표본 부족",
            tone="fail",
            detail_ko=detail,
        )
    if n < SAMPLE_ADEQUATE_N or drop:
        return AxisReading(
            tier="caution",
            label_ko="표본 주의",
            tone="elevated",
            detail_ko=detail,
        )
    _ = selection_n
    return AxisReading(tier="adequate", label_ko="표본 충분", tone="accent", detail_ko=detail)


def error_one_liner(cv_tier: str) -> str:
    if cv_tier == "low":
        return "구조적 관계가 비교적 안정적입니다."
    if cv_tier == "moderate":
        return (
            "개별 거래가격의 예측에는 한계가 있지만, 현재 지역의 거래가격 구조를 탐색하는 데 "
            "활용할 수 있습니다."
        )
    if cv_tier == "elevated":
        return (
            "개별 거래가격의 차이를 정밀하게 설명하기에는 오차가 큰 편입니다. "
            "다만 본 분석은 AVM이 아닌 지역 거래가격의 구조적 관계를 탐색하기 위한 것이므로, "
            "변수의 방향과 상대적 영향 중심으로 해석할 수 있습니다."
        )
    if cv_tier == "high":
        return (
            "가격 예측보다는 탐색적 분석에 적합합니다. "
            "계수의 방향과 상대적 영향을 중심으로 해석하세요."
        )
    return "CV-MAPE를 산출할 수 없어 해석 강도를 정하기 어렵습니다."


def lookup_macro_composite(
    *,
    error: CvFitnessTier,
    explanation: AxisReading,
    stability: AxisReading,
    sample: AxisReading,
) -> AxisReading:
    """CV 단독 판정이 아님. 숨은 점수 없이 표와 같은 규칙."""
    _ = explanation
    if sample.tier == "insufficient":
        return AxisReading(tier="analysis_limit", label_ko="분석 한계", tone="fail")
    if error.tier in {"low", "moderate"}:
        if sample.tier == "adequate" and stability.tier != "caution":
            return AxisReading(tier="stable", label_ko="안정적", tone="accent")
        return AxisReading(tier="usable", label_ko="활용 가능", tone="accent")
    if error.tier == "elevated":
        return AxisReading(tier="careful", label_ko="신중 활용", tone="elevated")
    if error.tier == "high":
        return AxisReading(tier="exploratory", label_ko="탐색적 활용", tone="high")
    if sample.tier == "adequate":
        return AxisReading(tier="careful", label_ko="신중 활용", tone="elevated")
    return AxisReading(tier="usable", label_ko="활용 가능", tone="accent")


def macro_summary_ko(
    *,
    composite: AxisReading,
    sample: AxisReading,
    fit_n: int,
    scope_n_tx: int,
) -> str:
    n = int(fit_n or 0)
    scope = int(scope_n_tx or 0)
    sample_note = ""
    if sample.tier in {"caution", "insufficient"} and scope > 0:
        sample_note = (
            f" 분석 표본 {n}건 — 전체 거래 {scope}건 중 {n}건만 회귀에 사용되었습니다. "
            "결과 해석 시 표본 구성에 주의하세요."
        )
    if composite.tier == "analysis_limit":
        return (
            f"분석 표본 {n}건으로는 회귀 결과를 일반화하기 어렵습니다."
            f"{sample_note} 계수 크기보다 변수의 방향만 참고하세요."
        )
    if composite.tier == "usable":
        return (
            "현재 변수 구성에서 지역 거래가격과 관련된 구조적 관계가 확인됩니다. "
            f"다만 분석 표본이 {n}건으로 제한되어 있으므로 개별 계수의 크기보다는 "
            "변수의 방향과 반복적으로 나타나는 관계를 중심으로 해석하는 것이 적절합니다."
        )
    if composite.tier == "stable":
        return (
            "현재 변수 구성에서 구조적 관계가 비교적 안정적으로 확인됩니다. "
            "계수의 방향과 상대적 영향을 중심으로 해석하세요. "
            "개별 물건의 적정가격으로 읽지 마세요."
        )
    if composite.tier == "careful":
        return (
            "개별 거래가격의 차이를 정밀하게 설명하기에는 오차가 큰 편입니다. "
            "본 분석은 AVM이 아닌 지역 거래가격의 구조적 관계를 탐색하기 위한 것이므로, "
            "변수의 방향과 상대적 영향 중심으로 해석할 수 있습니다."
            f"{sample_note}"
        )
    if composite.tier == "exploratory":
        return (
            "오차는 높은 편이지만, 충분한 거래를 기반으로 구조적 관계를 탐색할 수 있습니다. "
            "예측값보다 계수 방향·변수 조합을 중심으로 읽으세요."
            f"{sample_note}"
        )
    return error_one_liner("unknown")


def build_macro_diagnosis(
    *,
    cv_mape: float | None,
    mape: float | None,
    adj_r_squared: float | None,
    fit_n: int,
    scope_n_tx: int,
    selection_n: int | None = None,
) -> MacroDiagnosis:
    error = lookup_cv_fitness(cv_mape)
    explanation = lookup_adj_r2(adj_r_squared)
    stability = lookup_stability(mape, cv_mape)
    sample = lookup_sample(fit_n=fit_n, scope_n_tx=scope_n_tx, selection_n=selection_n)
    composite = lookup_macro_composite(
        error=error, explanation=explanation, stability=stability, sample=sample
    )
    return MacroDiagnosis(
        error=AxisReading(
            tier=error.tier,
            label_ko=error.label_ko,
            tone=error.tone,
            detail_ko=f"CV-MAPE {cv_mape:.1f}%" if cv_mape is not None else "CV 미산출",
        ),
        explanation=explanation,
        stability=stability,
        sample=sample,
        composite=composite,
        error_one_liner_ko=error_one_liner(error.tier),
        summary_ko=macro_summary_ko(
            composite=composite, sample=sample, fit_n=fit_n, scope_n_tx=scope_n_tx
        ),
    )


def offer_structure_twin(
    *,
    has_twins: bool,
    cv_mape: float | None,
    mape: float | None,
    selection_n: int,
    scope_n_tx: int,
    fit_n: int,
    min_local_n: int,
    min_fit_n: int,
    admin_level: str | None = None,
) -> bool:
    """Twin은 오차 불합격의 구원이 아니다. Local만으로 구조가 충분히 안 보일 때.

    이웃 후보 전달 여부(has_twins)는 실행 가능 여부이지 권고 조건이 아니다.
    시군구·구에서는 Twin을 권고하지 않는다.
    """
    _ = has_twins
    if (admin_level or "").strip().lower() in {"sigungu", "gu"}:
        return False
    if selection_n < min_local_n or scope_n_tx < min_local_n:
        return True
    if fit_n < min_fit_n:
        return True
    if cv_mape is not None and cv_mape >= TWIN_OFFER_CV:
        return True
    gap = cv_mape_gap_pp(mape, cv_mape)
    if gap is not None and gap >= TWIN_OFFER_GAP_PP:
        return True
    return False
