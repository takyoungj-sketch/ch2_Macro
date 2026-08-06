"""연속 변수 외삽 등급 — 예측·경고 SSOT."""

from __future__ import annotations

from dataclasses import dataclass

from app.built.schemas import ResponseScale

SOFT_NORMAL_FRAC = 0.2
SOFT_WARN_FRAC = 0.5
BLOCK_RATIO = 10.0


@dataclass(frozen=True)
class ContinuousAssessment:
    name: str
    label: str
    lo: float
    hi: float
    value: float
    level: int
    bound_ratio: float
    message: str | None = None


def _span(lo: float, hi: float) -> float:
    return max(hi - lo, 1e-9)


def assess_continuous(
    name: str,
    label: str,
    lo: float,
    hi: float,
    value: float,
) -> ContinuousAssessment:
    """L0 in-range · L1 ±20% span · L2 ±50% · L3 2–10× · L4 ≥10×."""
    if lo <= value <= hi:
        return ContinuousAssessment(
            name=name,
            label=label,
            lo=lo,
            hi=hi,
            value=value,
            level=0,
            bound_ratio=1.0,
        )

    span = _span(lo, hi)
    if value < lo:
        gap = lo - value
        bound_ratio = lo / value if value > 0 else float("inf")
    else:
        gap = value - hi
        bound_ratio = value / hi if hi > 0 else float("inf")

    beyond_frac = gap / span
    if beyond_frac <= SOFT_NORMAL_FRAC:
        level = 1
    elif beyond_frac <= SOFT_WARN_FRAC:
        level = 2
    elif bound_ratio < BLOCK_RATIO:
        level = 3
    else:
        level = 4

    msg = (
        f"외삽 L{level} — {label} 학습 [{lo:,.1f}, {hi:,.1f}] "
        f"밖 (입력 {value:,.1f}, 약 {bound_ratio:.1f}×)"
    )
    return ContinuousAssessment(
        name=name,
        label=label,
        lo=lo,
        hi=hi,
        value=value,
        level=level,
        bound_ratio=bound_ratio,
        message=msg,
    )


def assess_prediction(
    continuous_ranges: dict[str, tuple[float, float]],
    inputs: dict[str, float | None],
    *,
    labels: dict[str, str] | None = None,
) -> tuple[int, list[ContinuousAssessment], list[str]]:
    """집계 등급 = 연속 변수 중 최대 level, 경고 문구 목록."""
    labels = labels or {}
    assessments: list[ContinuousAssessment] = []
    for col, (lo, hi) in continuous_ranges.items():
        val = inputs.get(col)
        if val is None:
            continue
        a = assess_continuous(col, labels.get(col, col), lo, hi, float(val))
        if a.level > 0:
            assessments.append(a)

    level = max((a.level for a in assessments), default=0)
    warnings: list[str] = []
    for a in assessments:
        if a.message:
            warnings.append(a.message)
    if level >= 3:
        warnings.insert(
            0,
            "학습 범위를 크게 벗어난 입력 — 예측은 참고용입니다.",
        )
    if level >= 4:
        warnings.insert(
            0,
            "극단 외삽 — semi-log(log 금액) 역변환값은 표시하지 않습니다. "
            "선형·log-log 모형 또는 범위 내 입력을 권장합니다.",
        )
    return level, assessments, warnings


def should_suppress_y_hat(level: int, response_scale: ResponseScale) -> bool:
    """L4 + semi-log — 비현실적 exp(ŷ) 숨김 (차단 아님)."""
    return level >= 4 and response_scale == "log"
