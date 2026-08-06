"""진단 체크리스트 — 표본·변수·이상치·지역 (R4)."""

from __future__ import annotations

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
) -> list[DiagnosticCheckItem]:
    items: list[DiagnosticCheckItem] = []

    # 표본
    if selection_n >= 30 and fit_n >= 20:
        sample_status: DiagnosticStatus = "ok"
        sample_summary = f"탐색 {selection_n}건·적합 {fit_n}건 — 회귀 탐색에 무난한 수준입니다."
    elif selection_n >= 15:
        sample_status = "warn"
        sample_summary = (
            f"탐색 {selection_n}건·적합 {fit_n}건 — 가능하나 세부 계수·CV는 불안정할 수 있습니다."
        )
    else:
        sample_status = "fail"
        sample_summary = f"탐색 {selection_n}건 — 표본이 적어 탐색 결과 신뢰도가 낮습니다."

    if scope_n_tx > 0 and selection_n < scope_n_tx * 0.7:
        sample_status = "warn" if sample_status == "ok" else sample_status
        sample_summary += f" (거래 {scope_n_tx}건 대비 complete-case 감소)"

    items.append(
        DiagnosticCheckItem(
            check_id="sample",
            label_ko="표본",
            status=sample_status,
            summary_ko=sample_summary,
        )
    )

    # 변수 / 예측력
    if variable_limit or verdict == "no_predictive_model":
        var_status: DiagnosticStatus = "fail"
        var_summary = (
            "Local·Twin 모두 예측력이 낮아 **현재 독립변수만으로는 가격 설명이 어렵**습니다."
        )
    elif cv_mape is not None and cv_mape >= 60:
        var_status = "fail"
        var_summary = f"CV-MAPE {cv_mape:.1f}% — 예측 목적에는 부적합한 수준입니다."
    elif cv_mape is not None and cv_mape >= 40:
        var_status = "warn"
        var_summary = f"CV-MAPE {cv_mape:.1f}% — 변수 설명력·예측 안정성에 주의가 필요합니다."
    else:
        var_status = "ok"
        var_summary = "현재 변수 조합으로 scope 내 설명·예측이 **참고 가능**한 수준입니다."

    items.append(
        DiagnosticCheckItem(
            check_id="variable",
            label_ko="변수·예측력",
            status=var_status,
            summary_ko=var_summary,
        )
    )

    # 이상치
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

    # 지역 특성
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
        reg_summary = "지역 더미 없음 — scope 내 **단일 회귀식** 가정에 가깝습니다."

    items.append(
        DiagnosticCheckItem(
            check_id="regional",
            label_ko="지역 특성",
            status=reg_status,
            summary_ko=reg_summary,
        )
    )

    return items
