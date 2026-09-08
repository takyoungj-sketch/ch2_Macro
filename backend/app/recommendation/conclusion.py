"""탐색 결과 해석 문단 — D-068 4축 해석 강도 (적부 아님)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.recommendation.cv_fitness import (
    build_macro_diagnosis,
    cv_mape_gap_pp,
    lookup_cv_fitness,
)
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


def _verdict_from_composite(composite_tier: str) -> RecommendationVerdict:
    if composite_tier == "analysis_limit":
        return "no_predictive_model"
    if composite_tier in {"careful", "exploratory", "unknown"}:
        return "caution"
    return "adopt_predictive"


def _adopt_mode_from_composite(composite_tier: str) -> AdoptMode:
    if composite_tier in {"stable", "usable"}:
        return "predictive"
    return "review_only"


def _final_tone(axis_tone: str) -> str:
    if axis_tone == "fail":
        return "negative"
    if axis_tone in {"elevated", "high"}:
        return "warning"
    return "neutral"


def _recommended_actions(
    *,
    composite_tier: str,
    error_tier: str,
    twin_recommended: bool,
    twin_ran: bool,
    variable_limit: bool,
) -> list[RecommendedAction]:
    actions: list[RecommendedAction] = []
    if composite_tier == "analysis_limit":
        actions.append(
            RecommendedAction(
                action_id="sample_limit",
                kind="dont",
                label_ko="표본이 적어 계수 크기를 일반화하지 않음",
            )
        )
        actions.append(
            RecommendedAction(
                action_id="read_direction",
                kind="do",
                label_ko="변수 방향만 참고",
            )
        )
        return actions
    if error_tier == "high" or composite_tier == "exploratory":
        actions.append(
            RecommendedAction(
                action_id="no_avm_read",
                kind="dont",
                label_ko="개별 거래 예측값으로 해석하지 않음",
            )
        )
        actions.append(
            RecommendedAction(
                action_id="read_structure",
                kind="do",
                label_ko="계수 방향·변수 조합 중심으로 해석",
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
    elif error_tier == "elevated" or composite_tier == "careful":
        actions.append(
            RecommendedAction(
                action_id="structure_first",
                kind="do",
                label_ko="계수와 변수 관계는 참고, 개별 예측값은 거칠게",
            )
        )
        if twin_recommended and not twin_ran:
            actions.append(
                RecommendedAction(
                    action_id="run_twin",
                    kind="optional",
                    label_ko="구조 유지 여부를 Twin으로 비교",
                )
            )
    else:
        actions.append(
            RecommendedAction(
                action_id="structure_ok",
                kind="do",
                label_ko="계수 방향·상대 영향을 중심으로 활용",
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
    predictive_fit=None,
    excluded_blocks: list[str] | None = None,
    mape: float | None = None,
    adj_r_squared: float | None = None,
) -> RecommendationConclusion:
    from app.recommendation.models import PredictiveFitInfo
    from app.recommendation.satisfaction import lookup_predictive_fit

    pfit = predictive_fit or lookup_predictive_fit(cv_mape=cv_mape)
    fitness = lookup_cv_fitness(cv_mape)
    diagnosis = build_macro_diagnosis(
        cv_mape=cv_mape,
        mape=mape,
        adj_r_squared=adj_r_squared,
        fit_n=fit_n,
        scope_n_tx=scope_n_tx,
        selection_n=selection_n,
    )
    verdict = _verdict_from_composite(diagnosis.composite.tier)
    bullets: list[ConclusionBullet] = []
    twin_ran = bool(stage2 and stage2.ran)
    excluded_n = max(0, int(scope_n_tx) - int(selection_n)) if scope_n_tx and selection_n else 0
    excluded_notes = list(excluded_blocks or [])

    if diagnosis.sample.tier in {"caution", "insufficient"} and diagnosis.sample.detail_ko:
        bullets.append(
            ConclusionBullet(kind="neutral", text=diagnosis.sample.detail_ko + ".")
        )

    best_twin_cv: float | None = None
    variable_limit = False
    if twin_ran and stage2:
        tv = stage2.twin_validation
        if tv and tv.summary_ko:
            bullets.append(
                ConclusionBullet(
                    kind="positive" if tv.twin_adopt_recommended else "neutral",
                    text=tv.summary_ko,
                )
            )
        elif stage2.skipped_reason:
            bullets.append(ConclusionBullet(kind="neutral", text=stage2.skipped_reason))
        pools = stage2.pools
        if pools:
            cvs = [p.cv_mape for p in pools if p.cv_mape is not None]
            best_twin_cv = min(cvs) if cvs else None
        local_cv = stage2.local_cv_mape
        if (
            best_twin_cv is not None
            and local_cv is not None
            and best_twin_cv >= 60
            and (local_cv - best_twin_cv) < 5
        ):
            variable_limit = True
            bullets.append(
                ConclusionBullet(
                    kind="neutral",
                    text="Twin을 붙여도 오차가 크게 줄지 않아, 표본보다 변수 설명 한계를 의심할 수 있습니다.",
                )
            )
        elif (
            best_twin_cv is not None
            and local_cv is not None
            and local_cv - best_twin_cv >= 5
        ):
            bullets.append(
                ConclusionBullet(
                    kind="neutral",
                    text=(
                        f"Local CV-MAPE {local_cv:.1f}% → Twin {best_twin_cv:.1f}% "
                        f"({local_cv - best_twin_cv:.1f}%p). "
                        "유사 지역 거래를 추가했을 때 검증 오차가 감소했습니다. "
                        "추가 표본을 포함한 구조가 Local보다 안정적인지 확인해 보세요."
                    ),
                )
            )

    if twin_recommended and not twin_ran:
        bullets.append(
            ConclusionBullet(
                kind="neutral",
                text=(
                    "추가 검증 권고 — Local만으로 구조적 관계가 충분히 안정적으로 확인되지 않을 수 있습니다. "
                    "닮은 거래군을 보태면 같은 변수 관계가 유지되는지 비교할 수 있습니다."
                ),
            )
        )

    _ = grade
    _ = cv_mape_gap_pp(mape, cv_mape)
    actions = _recommended_actions(
        composite_tier=diagnosis.composite.tier,
        error_tier=diagnosis.error.tier,
        twin_recommended=twin_recommended and not twin_ran,
        twin_ran=twin_ran,
        variable_limit=variable_limit,
    )
    sublines = [a.label_ko for a in actions if a.kind == "do"][:3]
    if twin_recommended and not twin_ran:
        sublines = ["추가 검증으로 구조 유지 여부를 비교할 수 있음", *sublines][:3]

    return RecommendationConclusion(
        verdict=verdict,
        headline_ko=diagnosis.error_one_liner_ko,
        final_verdict_ko=diagnosis.error.label_ko,
        final_verdict_tone=_final_tone(diagnosis.error.tone),  # type: ignore[arg-type]
        final_verdict_emoji="",
        final_verdict_sublines=sublines,
        bullets=bullets,
        summary_ko=diagnosis.summary_ko,
        recommended_actions=actions,
        cv_fitness=fitness,
        predictive_fit=PredictiveFitInfo(
            tier=pfit.tier,
            label_ko=pfit.label_ko,
            grade=pfit.grade,
            tone=pfit.tone,
        ),
        macro_diagnosis=diagnosis,
        adj_r_squared=adj_r_squared,
        mape=mape,
        cv_mape=cv_mape,
        sample_excluded_n=excluded_n,
        excluded_block_notes=excluded_notes,
        twin_available=has_twins,
        twin_recommended=twin_recommended and not twin_ran,
        twin_ran=twin_ran,
        adopt_mode=_adopt_mode_from_composite(diagnosis.composite.tier),
        variable_limit=variable_limit,
    )
