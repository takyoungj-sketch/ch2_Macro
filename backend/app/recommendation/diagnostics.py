"""진단 체크리스트 — 표본·변수·이상치·지역 (R4, D-068)."""

from __future__ import annotations

from app.recommendation.cv_fitness import lookup_sample
from app.recommendation.models import DiagnosticCheckItem, DiagnosticStatus, RecommendationVerdict


def build_diagnostics_checklist(
    *,
    scope_n_tx: int,
    selection_n: int,
    fit_n: int,
    cv_mape: float | None,
    mape: float | None,
    verdict: RecommendationVerdict,
    exclude_outliers_iqr: bool,
    primary_blocks: list[str],
    variable_limit: bool,
    twin_ran: bool = False,
) -> list[DiagnosticCheckItem]:
    items: list[DiagnosticCheckItem] = []
    _ = verdict

    sample = lookup_sample(fit_n=fit_n, scope_n_tx=scope_n_tx, selection_n=selection_n)
    if sample.tier == "insufficient":
        sample_status: DiagnosticStatus = "fail"
    elif sample.tier == "caution":
        sample_status = "warn"
    else:
        sample_status = "ok"
    sample_summary = sample.detail_ko or f"탐색 {selection_n}건·적합 {fit_n}건"
    if sample.label_ko:
        sample_summary = f"{sample.label_ko} — {sample_summary}"

    items.append(
        DiagnosticCheckItem(
            check_id="sample",
            label_ko="표본",
            status=sample_status,
            summary_ko=sample_summary,
        )
    )

    if cv_mape is not None and cv_mape >= 75:
        var_status: DiagnosticStatus = "warn"
        var_summary = (
            "현재 변수로 개별 가격 차이를 많이 남깁니다. "
            "계수 방향·상대 영향 등 구조 탐색으로 해석하세요."
        )
        if twin_ran:
            var_summary += " Twin을 붙여도 오차가 크게 줄지 않았습니다."
        elif variable_limit:
            var_summary += " 추가 변수 확보를 검토할 수 있습니다."
    elif cv_mape is not None and cv_mape >= 60:
        var_status = "warn"
        var_summary = (
            f"CV-MAPE {cv_mape:.1f}% — 개별 예측값은 거칠고, 구조적 관계는 볼 수 있습니다."
        )
        if twin_ran:
            var_summary += " Twin 실험 결과는 아래 접두 표를 보세요."
    elif cv_mape is not None and cv_mape >= 45:
        var_status = "warn"
        var_summary = (
            f"CV-MAPE {cv_mape:.1f}% — 개별 거래 차이는 크지만 구조 분석에 활용할 수 있습니다."
        )
    else:
        var_status = "ok"
        var_summary = "현재 변수 구성에서 일정 수준의 구조적 관계가 확인됩니다."

    items.append(
        DiagnosticCheckItem(
            check_id="variable",
            label_ko="변수·예측력",
            status=var_status,
            summary_ko=var_summary,
        )
    )

    if exclude_outliers_iqr:
        outlier_status: DiagnosticStatus = "ok"
        outlier_summary = "IQR 이상치 제외가 적용되어 극단 거래 영향을 줄였습니다."
    elif cv_mape is not None and mape is not None and cv_mape - mape >= 25:
        outlier_status = "warn"
        outlier_summary = (
            f"표본내 MAPE {mape:.1f}% 대비 CV-MAPE {cv_mape:.1f}% — "
            "일부 거래·검증 fold에서 오차가 커 **이상치·극단값** 영향을 의심할 수 있습니다."
        )
    elif cv_mape is not None and cv_mape >= 50 and not exclude_outliers_iqr:
        outlier_status = "warn"
        outlier_summary = "이상치 제외 미적용 — 극단 거래가 모형 성능을 크게 떨어뜨릴 수 있습니다."
    else:
        outlier_status = "ok"
        outlier_summary = "이상치 특이 신호는 크지 않거나, 제외 필터가 적용되었습니다."

    items.append(
        DiagnosticCheckItem(
            check_id="outlier",
            label_ko="이상치",
            status=outlier_status,
            summary_ko=outlier_summary,
        )
    )

    has_region = "region_leaf" in primary_blocks
    if has_region and cv_mape is not None and cv_mape >= 50:
        reg_status: DiagnosticStatus = "warn"
        reg_summary = (
            "지역(읍·면·동/리) 더미가 포함되어 **동일 scope 내 가격 편차**가 커 "
            "단일 회귀식 해석에 한계가 있을 수 있습니다."
        )
    elif has_region:
        reg_status = "warn"
        reg_summary = "지역 더미 포함 — 세부 지역 간 편차를 반영하지만, 해석·예측 복잡도가 올라갑니다."
    else:
        reg_status = "ok"
        reg_summary = "지역 더미 없음 — scope 내 단일 회귀 가정에 가깝습니다."

    items.append(
        DiagnosticCheckItem(
            check_id="regional",
            label_ko="지역 특성",
            status=reg_status,
            summary_ko=reg_summary,
        )
    )

    return items
