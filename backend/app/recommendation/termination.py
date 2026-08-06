"""추천 종료 이유 — v0→R2."""

from __future__ import annotations

from typing import Literal

from app.built.schemas import ModelCandidate, RecommendationStage2
from app.recommendation.models import TerminationAction, TerminationInfo
from app.recommendation.satisfaction import GradeLookupResult, built_min_local_n


def build_termination_v0(
    *,
    selection_n: int,
    primary: ModelCandidate,
    alternate: ModelCandidate | None,
    truncated: bool,
    min_local_n: int | None = None,
) -> TerminationInfo:
    min_n = min_local_n if min_local_n is not None else built_min_local_n()
    reasons: list[str] = []
    action: TerminationAction = "stop"
    next_hint: str | None = None

    reasons.append(f"1단계 Local 탐색 완료 (selection_n={selection_n})")

    cv = primary.metrics.cv_mape
    if cv is not None:
        reasons.append(f"현재 최적 후보(예측형) CV-MAPE {cv:.1f}%")
    elif primary.metrics.mape is not None:
        reasons.append(f"CV 불가 — in-sample MAPE {primary.metrics.mape:.1f}% 기준")

    if alternate and set(alternate.blocks) != set(primary.blocks):
        reasons.append("설명형(AIC) 최적 후보와 예측형 최적 후보 변수 구성이 다릅니다 — 탭별 검토를 권장합니다.")

    if truncated:
        reasons.append("후보 조합 128개 상한으로 일부만 평가했습니다.")

    if selection_n < min_n:
        action = "proceed_twin"
        next_hint = "표본이 적어 Profile Twin 2단계 검토를 권장합니다."
        reasons.append(f"selection_n={selection_n} (< {min_n}) — Twin pool 보강 후보")

    return TerminationInfo(
        stage_reached=1,
        action=action,
        grade="pending",
        reasons=reasons,
        next_stage_hint=next_hint,
    )


def build_termination_r2(
    *,
    grade: GradeLookupResult,
    selection_n: int,
    scope_n_tx: int,
    primary: ModelCandidate,
    alternate: ModelCandidate | None,
    truncated: bool,
    stage2: RecommendationStage2 | None,
) -> TerminationInfo:
    reasons: list[str] = []
    action: TerminationAction = "stop"
    next_hint: str | None = None
    stage_reached = 1

    reasons.append(
        f"1단계 Local — 등급 {grade.label_ko}({grade.grade}), selection_n={selection_n}"
    )
    cv = primary.metrics.cv_mape
    if cv is not None:
        reasons.append(f"현재 최적 후보(예측형) CV-MAPE {cv:.1f}%")

    if alternate and set(alternate.blocks) != set(primary.blocks):
        reasons.append("설명형·예측형 최적 후보 변수 구성 상이 — 탭별 검토 권장")

    if truncated:
        reasons.append("후보 조합 128개 상한으로 일부만 평가했습니다.")

    if scope_n_tx < built_min_local_n():
        reasons.append(
            f"scope_n_tx={scope_n_tx} (< {built_min_local_n()}) — 표본 극소, Twin 검토 우선"
        )

    if stage2 is None:
        if grade.proceed_twin:
            action = "proceed_twin"
            next_hint = grade.note or "Profile Twin 2단계 검토를 권장합니다."
            reasons.append("Twin 후보 미전달 또는 2단계 미실행")
        return TerminationInfo(
            stage_reached=1,
            action=action,
            grade=grade.grade,
            reasons=reasons,
            next_stage_hint=next_hint,
        )

    stage_reached = 2

    if not stage2.ran:
        reasons.append(stage2.skipped_reason or "2단계 Twin 미실행")
        if grade.proceed_twin:
            action = "proceed_twin"
            next_hint = "Twin 후보를 확인하세요."
        return TerminationInfo(
            stage_reached=1,
            action=action,
            grade=grade.grade,
            reasons=reasons,
            next_stage_hint=next_hint,
        )

    reasons.append("2단계 Twin pool 검토 완료 (1단계 식·스케일 고정)")
    if stage2.decision_reason:
        reasons.append(stage2.decision_reason)

    if stage2.primary and stage2.primary.cv_mape_delta is not None:
        if stage2.primary.cv_mape_delta > 0:
            reasons.append(
                f"Twin pool CV-MAPE {stage2.primary.cv_mape_delta:.1f}%p 개선 "
                f"({stage2.local_cv_mape:.1f}% → {stage2.primary.cv_mape:.1f}%)"
            )
        else:
            reasons.append("Twin pool 추가 개선 폭 제한적 — 1단계 Local 유지 가능")

    if stage2.twin_gates:
        rejected = sum(1 for g in stage2.twin_gates if not g.accepted)
        if rejected:
            reasons.append(f"Twin gate: {rejected}곳 제외")

    if stage2.primary and stage2.decision != "local":
        action = "stop"
    elif grade.proceed_twin and not stage2.pools:
        action = "proceed_twin"
        next_hint = "gate 통과 Twin pool 없음 — scope 확대 검토"

    return TerminationInfo(
        stage_reached=stage_reached,
        action=action,
        grade=grade.grade,
        reasons=reasons,
        next_stage_hint=next_hint,
        recommended_pool=stage2.primary.candidate_id if stage2.primary else None,
    )


def narrative_hints_from_termination(termination: TerminationInfo) -> list[str]:
    return list(termination.reasons)
