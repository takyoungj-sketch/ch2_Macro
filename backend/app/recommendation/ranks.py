"""dual rank — explanatory vs predictive (R1)."""

from __future__ import annotations

from app.built.regression.selection.best_subset import CompareCandidate
from app.built.regression.selection.blocks import spec_from_blocks
from app.built.regression.selection.service import _fit_metrics
from app.recommendation.coefficients import coefficients_from_block_fit
from app.built.regression.selection.fit import BlockFitResult, CvPhase
from app.built.schemas import CandidateCvReport, CvCoverage, ModelCandidate, ModelMetrics
from app.recommendation.satisfaction import built_min_fit_n


def _coverage(phase: CvPhase) -> CvCoverage:
    return CvCoverage(
        mape=phase.mape,
        folds=phase.folds,
        n_trades=phase.n_trades,
        years=list(phase.years),
    )


def candidate_from_compare(c: CompareCandidate) -> ModelCandidate:
    fit = c.fit
    return ModelCandidate(
        rank=c.rank,
        blocks=list(c.blocks),
        variables=spec_from_blocks(c.blocks),
        response_scale=fit.response_scale,
        metrics=_fit_metrics(fit),
        model_comparison=c.model_comparison,  # type: ignore[arg-type]
        aic=fit.aic,
        bic=fit.bic,
        joint_f_tests=fit.joint_f_tests,
        coefficients=coefficients_from_block_fit(fit),
        cv_report=CandidateCvReport(
            search=_coverage(fit.cv_search),
            confirm=_coverage(fit.cv_confirm),
        ),
    )


def pick_primary_predictive(
    by_cv_mape: list[CompareCandidate],
    by_mape: list[CompareCandidate],
    by_aic: list[CompareCandidate],
) -> CompareCandidate | None:
    """예측형 1위 — CV-MAPE → MAPE → AIC 순 fallback."""
    if by_cv_mape:
        return by_cv_mape[0]
    if by_mape:
        return by_mape[0]
    return by_aic[0] if by_aic else None


def pick_alternate_explanatory(by_aic: list[CompareCandidate]) -> CompareCandidate | None:
    return by_aic[0] if by_aic else None


# 화면 규칙. fold 표준오차가 아니라, 70건 안팎에서 1%p 남짓은 순위를 가리지 않기 위한 폭.
PARITY_BAND_PP = 1.0
# 대표모형 확정용 화면 규칙. 순위를 바꾸지 않는다.
# 검증 거래 10건은 식을 제공하는 최소 건수와 같다. 확인이 탐색보다 10%p 이상 나쁘면 확정하지 않는다.
CONFIRM_WORSE_PP = 10.0
_COEF_P = 0.1


def _year_phrase(years: tuple[int, ...] | list[int]) -> str:
    if not years:
        return ""
    return "·".join(str(year) for year in years) + "년"


def representative_verdict(fit: BlockFitResult) -> tuple[bool, str | None]:
    """탐색 1위를 대표모형으로 확정할 수 있는지. 순위는 건드리지 않는다.

    탐색이 한 해이거나 검증 거래가 식 제공 하한보다 적으면, 또는 확인 CV가
    탐색 CV보다 10%p 이상 나쁘면 확정하지 않는다. 계수당 5건 미달(참고용)만으로는
    걸지 않는다.
    """
    search = fit.cv_search
    confirm = fit.cv_confirm
    reasons: list[str] = []
    thin_folds = search.folds < 2
    thin_trades = search.n_trades < built_min_fit_n()
    if search.mape is None or thin_folds or thin_trades:
        when = _year_phrase(search.years)
        where = f"{when} " if when else ""
        reasons.append(f"탐색 CV는 {where}{search.n_trades}건입니다.")
    if confirm.held_years and confirm.mape is None:
        held = _year_phrase(confirm.held_years)
        reasons.append(f"마지막 연도({held}) 확인을 계산하지 못했습니다.")
    elif (
        search.mape is not None
        and confirm.mape is not None
        and confirm.mape >= search.mape + CONFIRM_WORSE_PP
    ):
        gap = confirm.mape - search.mape
        reasons.append(
            f"확인 CV {confirm.mape:.2f}%가 탐색 CV {search.mape:.2f}%보다 {gap:.1f}%p 큽니다."
        )
    if not reasons:
        return True, None
    return False, "탐색 1위이며 대표모형은 확정하지 않았습니다. " + " ".join(reasons)
# 양수면 가격과 같이 커지는 방향, 음수면 가격과 반대로 가는 방향.
_INTERPRETIVE_SIGN: dict[str, tuple[str, int]] = {
    "land_area": ("대지면적", 1),
    "building_age": ("연식", -1),
}


def _coef_named(candidate: ModelCandidate, block: str):
    for coef in candidate.coefficients:
        if coef.name == block:
            return coef
    return None


def _earns_interpretive(candidate: ModelCandidate, block: str) -> bool:
    coef = _coef_named(candidate, block)
    if coef is None or coef.p_value is None or coef.p_value >= _COEF_P:
        return False
    direction = _INTERPRETIVE_SIGN[block][1]
    if direction > 0:
        return coef.estimate > 0
    return coef.estimate < 0


def annotate_predictive_band(
    candidates: list[ModelCandidate],
    ns: list[int] | None = None,
) -> tuple[list, list[str]]:
    """최저 CV-MAPE와의 차이. 1.0%p·같은 표본이면 성능 유사.

    해석 후보는 그 안에서 예측 최소의 같은 척도 식에 대지면적·연식만 더한 경우다.
    더한 열마다 전체 표본 계수가 유의하고, 대지면적은 양, 연식은 음일 때만 올린다.
    """
    from app.built.schemas import PredictiveJudgment

    if not candidates:
        return [], []
    counts = list(ns) if ns is not None and len(ns) == len(candidates) else [None] * len(candidates)
    scored = [
        (idx, c)
        for idx, c in enumerate(candidates)
        if c.metrics.cv_mape is not None
    ]
    if not scored:
        return [
            PredictiveJudgment(rank=c.rank, label="비교 후보") for c in candidates
        ], []

    anchor_idx = min(scored, key=lambda item: (float(item[1].metrics.cv_mape), item[1].rank))[0]
    anchor = candidates[anchor_idx]
    min_cv = float(anchor.metrics.cv_mape)  # type: ignore[arg-type]
    anchor_n = counts[anchor_idx]
    anchor_blocks = set(anchor.blocks)

    judgments: list[PredictiveJudgment] = []
    interpretive_lines: list[str] = []
    weak_lines: list[str] = []
    saw_other_n = False
    for idx, candidate in enumerate(candidates):
        cv = candidate.metrics.cv_mape
        gap = None if cv is None else round(float(cv) - min_cv, 2)
        same_n = anchor_n is None or counts[idx] == anchor_n
        in_band = gap is not None and gap <= PARITY_BAND_PP and same_n
        if gap is not None and gap <= PARITY_BAND_PP and not same_n:
            saw_other_n = True
        interpretive = False
        added: list[str] = []
        if in_band and idx != anchor_idx and candidate.response_scale == anchor.response_scale:
            extra = set(candidate.blocks) - anchor_blocks
            named = [b for b, _ in _INTERPRETIVE_SIGN.items() if b in extra]
            if extra and set(anchor_blocks) <= set(candidate.blocks) and extra <= set(_INTERPRETIVE_SIGN):
                added = named
                if all(_earns_interpretive(candidate, b) for b in added):
                    interpretive = True
                else:
                    weak_lines.append(_weak_line(candidate, added))
        if idx == anchor_idx:
            label = "예측 최소"
        elif interpretive:
            label = "성능 유사 · 해석 후보"
        elif in_band:
            label = "성능 유사"
        else:
            label = "비교 후보"
        judgments.append(
            PredictiveJudgment(rank=candidate.rank, cv_gap_pp=gap, label=label)
        )
        if interpretive and gap is not None and cv is not None:
            bits = []
            for block in added:
                label_ko, direction = _INTERPRETIVE_SIGN[block]
                sign = "양" if direction > 0 else "음"
                bits.append(f"{label_ko} 계수는 {sign}이고 p<0.1")
            names = " · ".join(_INTERPRETIVE_SIGN[b][0] for b in added)
            interpretive_lines.append(
                f"{candidate.rank}위는 예측 최소에 {names}만 더한 식입니다. "
                f"CV-MAPE {float(cv):.2f}%, 최저보다 +{gap:.2f}%p. "
                f"{', '.join(bits)}라 해석 후보로 둡니다. AIC로 고른 설명형과는 별개입니다."
            )

    notes = [
        "최저 CV-MAPE보다 1.0%p 이내이고 표본 수가 같으면 성능 유사입니다. "
        "이 폭은 화면 규칙이며, 그 식들이 통계적으로 같다는 뜻은 아닙니다."
    ]
    if saw_other_n:
        notes.append("표본 수가 다른 식은 차이가 1.0%p 이내여도 성능 유사에 넣지 않았습니다.")
    notes.extend(interpretive_lines)
    notes.extend(weak_lines)
    return judgments, notes


def _weak_line(candidate: ModelCandidate, added: list[str]) -> str:
    reasons: list[str] = []
    for block in added:
        label_ko, direction = _INTERPRETIVE_SIGN[block]
        coef = _coef_named(candidate, block)
        if coef is None or coef.p_value is None or coef.p_value >= _COEF_P:
            shown = "없음" if coef is None or coef.p_value is None else f"{coef.p_value:.2f}"
            reasons.append(f"{label_ko} 계수는 p={shown}로 유의하지 않습니다")
        else:
            sign = "양" if coef.estimate > 0 else "음"
            expected = "양" if direction > 0 else "음"
            reasons.append(f"{label_ko} 계수는 {sign}이라 해석에 쓰는 {expected}이 아닙니다")
    names = " · ".join(_INTERPRETIVE_SIGN[b][0] for b in added)
    return (
        f"{candidate.rank}위는 예측 최소에 {names}만 더한 식이나, "
        f"{', '.join(reasons)}. 해석 후보로 두지 않았습니다."
    )
