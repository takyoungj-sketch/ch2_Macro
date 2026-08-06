"""탐색 결과 판정·결론 문단 — R3.5."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.recommendation.cv_fitness import lookup_cv_fitness
from app.recommendation.models import (
    AdoptMode,
    ConclusionBullet,
    RecommendationConclusion,
    RecommendationVerdict,
    RecommendedAction,
)
from app.recommendation.satisfaction import GradeLookupResult

if TYPE_CHECKING:
    from app.built.schemas import RecommendationStage2


def _verdict_from_fitness(tier: str) -> RecommendationVerdict:
    if tier == "unsuitable":
        return "no_predictive_model"
    if tier in {"caution", "unknown"}:
        return "caution"
    if tier == "fair":
        return "caution"
    return "adopt_predictive"


def _adopt_mode_from_verdict(verdict: RecommendationVerdict) -> AdoptMode:
    if verdict == "no_predictive_model":
        return "review_only"
    if verdict == "explanatory_only":
        return "explanatory"
    if verdict == "caution":
        return "review_only"
    return "predictive"


def _headline(verdict: RecommendationVerdict) -> str:
    if verdict == "no_predictive_model":
        return "예측용 모형으로는 부적합"
    if verdict == "caution":
        return "예측 신중 — 검토용 후보만 제시"
    if verdict == "explanatory_only":
        return "설명형 분석 권장"
    return "예측 후보로 채택 가능"


def _final_verdict_display(fitness_tier: str) -> tuple[str, str, str]:
    if fitness_tier in {"excellent", "good"}:
        return "🟢", "예측 적합", "positive"
    if fitness_tier in {"fair", "caution", "unknown"}:
        return "🟡", "주의", "warning"
    return "🔴", "예측 부적합", "negative"


def _recommended_actions(
    *,
    verdict: RecommendationVerdict,
    twin_recommended: bool,
    twin_ran: bool,
    variable_limit: bool,
) -> list[RecommendedAction]:
    actions: list[RecommendedAction] = []
    if verdict == "no_predictive_model":
        actions.append(
            RecommendedAction(
                action_id="no_predictive_use",
                kind="dont",
                label_ko="회귀식 예측 사용하지 않음",
            )
        )
        actions.append(
            RecommendedAction(
                action_id="use_land_matrix",
                kind="do",
                label_ko="용도×지목 통계 활용",
            )
        )
        actions.append(
            RecommendedAction(
                action_id="use_comparables",
                kind="do",
                label_ko="비교사례 검토",
            )
        )
        actions.append(
            RecommendedAction(
                action_id="explanatory_only",
                kind="do",
                label_ko="설명형 회귀만 참고",
            )
        )
        if variable_limit:
            actions.append(
                RecommendedAction(
                    action_id="more_variables",
                    kind="do",
                    label_ko="추가 변수 확보 검토 (층수·접도·리모델링 등)",
                )
            )
    elif verdict == "caution":
        actions.append(
            RecommendedAction(
                action_id="predictive_caution",
                kind="optional",
                label_ko="예측용 사용 시 주의 — 검토용으로만",
            )
        )
        actions.append(
            RecommendedAction(
                action_id="explanatory_ref",
                kind="do",
                label_ko="설명형 회귀 병행 참고",
            )
        )
        actions.append(
            RecommendedAction(
                action_id="use_land_matrix",
                kind="do",
                label_ko="용도×지목 통계 병행",
            )
        )
        if twin_recommended and not twin_ran:
            actions.append(
                RecommendedAction(
                    action_id="run_twin",
                    kind="optional",
                    label_ko="Twin pool 추가 검토",
                )
            )
    else:
        actions.append(
            RecommendedAction(
                action_id="predictive_ok",
                kind="do",
                label_ko="예측용으로 사용 가능",
            )
        )
        actions.append(
            RecommendedAction(
                action_id="compare_explanatory",
                kind="optional",
                label_ko="설명형 후보와 비교 검토",
            )
        )
    return actions


def build_recommendation_conclusion(
    *,
    cv_mape: float | None,
    grade: GradeLookupResult,
    scope_n_tx: int,
    selection_n: int,
    fit_n: int,
    has_twins: bool,
    twin_recommended: bool,
    stage2: RecommendationStage2 | None,
) -> RecommendationConclusion:
    fitness = lookup_cv_fitness(cv_mape)
    verdict = _verdict_from_fitness(fitness.tier)
    bullets: list[ConclusionBullet] = []
    twin_ran = bool(stage2 and stage2.ran)

    if scope_n_tx > 0 and selection_n < scope_n_tx:
        drop = scope_n_tx - selection_n
        if drop >= 10 or selection_n / scope_n_tx < 0.75:
            bullets.append(
                ConclusionBullet(
                    kind="neutral",
                    text=(
                        f"거래 {scope_n_tx}건이지만 SSOT 탐색 complete-case는 {selection_n}건"
                        f"(적합 {fit_n}건)으로 감소했습니다."
                    ),
                )
            )

    if cv_mape is not None:
        bullets.append(
            ConclusionBullet(
                kind="negative" if fitness.tier in {"caution", "unsuitable"} else "neutral",
                text=f"현재 최적 후보 CV-MAPE {cv_mape:.1f}% — {fitness.label_ko}",
            )
        )
    elif grade.grade == "insufficient_cv":
        bullets.append(
            ConclusionBullet(
                kind="negative",
                text="CV-MAPE를 산출할 수 없어 예측 적합성을 판단하기 어렵습니다.",
            )
        )

    bullets.append(
        ConclusionBullet(
            kind="neutral" if grade.grade in {"excellent", "good"} else "negative",
            text=f"만족 등급 {grade.label_ko}({grade.grade})",
        )
    )

    best_twin_cv: float | None = None
    variable_limit = False
    if twin_ran and stage2:
        local_cv = stage2.local_cv_mape
        pools = stage2.pools
        if pools:
            cvs = [p.cv_mape for p in pools if p.cv_mape is not None]
            best_twin_cv = min(cvs) if cvs else None
        if local_cv is not None and best_twin_cv is not None:
            if best_twin_cv < local_cv - 0.5:
                delta = local_cv - best_twin_cv
                bullets.append(
                    ConclusionBullet(
                        kind="positive",
                        text=(
                            f"Twin pool이 Local보다 CV-MAPE {delta:.1f}%p 개선"
                            f" ({local_cv:.1f}% → {best_twin_cv:.1f}%)."
                        ),
                    )
                )
                if fitness.tier in {"caution", "unsuitable"} and best_twin_cv >= 60:
                    verdict = "no_predictive_model"
            elif best_twin_cv > local_cv + 0.5:
                bullets.append(
                    ConclusionBullet(
                        kind="positive",
                        text=(
                            f"Local({local_cv:.1f}%)이 Twin pool({best_twin_cv:.1f}%)보다 "
                            "상대적으로 우수합니다."
                        ),
                    )
                )
                if fitness.tier == "unsuitable" and best_twin_cv >= 60:
                    bullets.append(
                        ConclusionBullet(
                            kind="negative",
                            text=(
                                "지역을 확대(Twin)해도 예측력이 개선되지 않았습니다. "
                                "표본 부족보다 현재 독립변수의 설명 한계 가능성이 큽니다."
                            ),
                        )
                    )
                    verdict = "no_predictive_model"
                    variable_limit = True
            else:
                bullets.append(
                    ConclusionBullet(
                        kind="neutral",
                        text="Twin pool 추가 후에도 예측력 개선 폭이 제한적입니다.",
                    )
                )
                if fitness.tier == "unsuitable":
                    verdict = "no_predictive_model"
        elif stage2.skipped_reason:
            bullets.append(ConclusionBullet(kind="neutral", text=stage2.skipped_reason))

    if twin_recommended and not twin_ran and has_twins:
        bullets.append(
            ConclusionBullet(
                kind="neutral",
                text="만족 등급·표본 기준으로 Profile Twin 2단계 검토를 권장합니다.",
            )
        )

    if verdict == "no_predictive_model":
        summary = (
            "현재 변수·scope에서 예측용 회귀식으로는 신뢰하기 어렵습니다. "
            "회귀 예측보다 설명형 분석, 용도×지목 통계, 비교사례 접근을 권장합니다."
        )
    elif verdict == "caution":
        summary = (
            "후보 식은 탐색 결과상 최적이나 예측 오차가 클 수 있습니다. "
            "채택 전 변수·표본·Twin 검토를 권장합니다."
        )
    else:
        summary = (
            "1단계 Local 탐색에서 예측·설명 기준 최적 후보를 찾았습니다. "
            "아래 식을 채택하거나 탭에서 대안을 비교하세요."
        )

    if twin_ran and verdict == "no_predictive_model" and best_twin_cv and best_twin_cv >= 60:
        summary += (
            " Twin Pooling을 적용해도 CV-MAPE가 60% 이상으로, "
            "추가 변수(층수·접도·리모델링·용적률 등) 검토가 필요할 수 있습니다."
        )

    adopt_mode = _adopt_mode_from_verdict(verdict)
    emoji, final_ko, final_tone = _final_verdict_display(fitness.tier)
    actions = _recommended_actions(
        verdict=verdict,
        twin_recommended=twin_recommended and not twin_ran,
        twin_ran=twin_ran,
        variable_limit=variable_limit,
    )
    sublines = [a.label_ko for a in actions if a.kind == "do"][:3]

    return RecommendationConclusion(
        verdict=verdict,
        headline_ko=_headline(verdict),
        final_verdict_ko=final_ko,
        final_verdict_tone=final_tone,  # type: ignore[arg-type]
        final_verdict_emoji=emoji,
        final_verdict_sublines=sublines,
        bullets=bullets,
        summary_ko=summary,
        recommended_actions=actions,
        cv_fitness=fitness,
        cv_mape=cv_mape,
        twin_available=has_twins,
        twin_recommended=twin_recommended and not twin_ran,
        twin_ran=twin_ran,
        adopt_mode=adopt_mode,
        variable_limit=variable_limit,
    )
