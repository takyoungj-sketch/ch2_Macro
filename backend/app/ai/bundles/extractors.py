"""Reasoning Bundle — facts JSON → AiDiagnosticPack."""

from __future__ import annotations

from typing import Any

from app.ai.bundles.registry import resolve_bundle_id
from app.ai.prediction_narrative import prediction_diagnostics_from_facts
from app.ai.schemas import AiContext, AiDiagnosticPack, AnalysisExplain
from app.ai.trend_narrative import trend_diagnostics_from_facts


def _primary_level(facts: dict[str, Any]) -> dict[str, Any]:
    primary = facts.get("primary")
    if isinstance(primary, dict):
        return primary
    return facts


def _coef_display(c: dict[str, Any]) -> tuple[str, Any, Any]:
    name = str(c.get("name") or c.get("label") or "?")
    est = c.get("estimate", c.get("coef"))
    p = c.get("p_value", c.get("p"))
    return name, est, p


def _fmt_p(p: Any) -> str:
    if p is None:
        return "—"
    try:
        fp = float(p)
        return "<0.001" if fp < 0.001 else f"{fp:.4f}"
    except (TypeError, ValueError):
        return str(p)


def _fmt_num(x: Any, digits: int = 3) -> str:
    if x is None:
        return "—"
    try:
        return f"{float(x):.{digits}f}"
    except (TypeError, ValueError):
        return str(x)


def _normalize_coeff(c: dict[str, Any]) -> dict[str, Any]:
    out = dict(c)
    if out.get("estimate") is None and out.get("coef") is not None:
        out["estimate"] = out["coef"]
    if out.get("p_value") is None and out.get("p") is not None:
        out["p_value"] = out["p"]
    name = str(out.get("name") or out.get("label") or "?")
    out["name"] = name
    return out


def _normalize_coefficients(coeffs: list[Any]) -> list[dict[str, Any]]:
    return [_normalize_coeff(c) for c in coeffs if isinstance(c, dict)]


def build_regression_diagnostic(context: AiContext) -> AiDiagnosticPack:
    facts = context.facts or {}
    primary = _primary_level(facts)
    n = primary.get("n")
    adj = primary.get("adj_r_squared") or primary.get("adj_r2")
    raw_coeffs = primary.get("coefficients") or []
    coeffs = _normalize_coefficients(raw_coeffs)
    vif = primary.get("vif") or facts.get("vif") or []
    vif_warn = primary.get("vif_warning") or facts.get("vif_warning")
    corrs = facts.get("correlations") or []
    warnings = list(facts.get("warnings") or primary.get("warnings") or [])
    if vif_warn and vif_warn not in warnings:
        warnings.append(vif_warn)

    coeff_lines = []
    for c in coeffs[:12]:
        if not isinstance(c, dict):
            continue
        name, est, p = _coef_display(c)
        coeff_lines.append(f"{name}: estimate={_fmt_num(est)}, p={_fmt_p(p)}")

    summary = []
    if n is not None:
        summary.append(f"표본 n={n}")
    if adj is not None:
        summary.append(f"Adj R²={_fmt_num(adj)}")
    if primary.get("scope_label"):
        summary.append(f"scope={primary['scope_label']}")
    summary.extend(coeff_lines[:8])

    if vif:
        vif_top = sorted(
            [v for v in vif if isinstance(v, dict)],
            key=lambda x: float(x.get("vif") or 0),
            reverse=True,
        )[:5]
        for v in vif_top:
            summary.append(f"VIF {v.get('name')}: {_fmt_num(v.get('vif'))}")

    for s in corrs[:4]:
        if isinstance(s, dict):
            label = s.get("label") or s.get("variable")
            summary.append(f"상관 {label}: r={_fmt_num(s.get('pearson_r'), 4)}")

    limitations = [
        "회귀는 선택 기간·지역 내 거래 패턴의 상관 관계이며 인과를 의미하지 않습니다.",
        "표본이 작으면 계수 부호·유의성이 불안정할 수 있습니다.",
    ]
    if context.explain and context.explain.limitations:
        limitations = context.explain.limitations + limitations

    scope_label = (
        primary.get("scope_label")
        or context.scope.region_label
        or facts.get("scope_label")
    )

    return AiDiagnosticPack(
        bundle_id="regression_diagnostic",
        panel=context.panel,
        app=context.app,
        summary_lines=summary,
        diagnostics={
            "n": n,
            "adj_r_squared": adj,
            "scope_label": scope_label,
            "coefficients": coeffs,
            "vif": vif,
            "vif_warning": vif_warn,
            "correlation_count": len(corrs),
            "correlations": corrs,
            "correlation_n": facts.get("correlation_n"),
            "warnings": warnings,
            "equation": primary.get("equation"),
            "r_squared": primary.get("r_squared"),
            "significant_count": primary.get("significant_count"),
        },
        limitations=limitations,
    )


def build_from_explain(context: AiContext) -> AiDiagnosticPack:
    ex: AnalysisExplain | None = context.explain
    summary = []
    limitations = []
    if ex:
        summary.append(ex.summary)
        summary.extend(ex.interpretation[:4])
        limitations.extend(ex.limitations)
    return AiDiagnosticPack(
        bundle_id="explain_only",
        panel=context.panel,
        app=context.app,
        summary_lines=summary,
        diagnostics={"spec_id": ex.spec_id if ex else None},
        limitations=limitations or ["Explain layer가 비어 있습니다."],
    )


def _facts_kind(facts: dict[str, Any]) -> str:
    if facts.get("y_hat") is not None:
        return "prediction"
    if facts.get("series") or facts.get("rows"):
        return "trend"
    primary = _primary_level(facts)
    if facts.get("coefficients") or primary.get("coefficients"):
        return "regression"
    return "empty"


def build_trend_diagnostic(context: AiContext) -> AiDiagnosticPack:
    facts = context.facts or {}
    scope_label = (
        context.scope.region_label
        or facts.get("scope_label")
        or "선택 scope"
    )
    diag = trend_diagnostics_from_facts(facts, scope_label=str(scope_label))
    summary = [
        f"scope={scope_label}",
        f"구간={diag.get('point_count')}개",
        f"거래={diag.get('total_count')}건",
    ]
    if diag.get("zone_type"):
        summary.append(f"{diag['zone_type']} × {diag.get('land_category')}")
    limitations = [
        "추이는 선택 필터·칸 scope 내 집계이며 인과·전망이 아닙니다.",
        "구간별 n이 작으면 단가·거래수가 불안정할 수 있습니다.",
    ]
    return AiDiagnosticPack(
        bundle_id="trend_diagnostic",
        panel=context.panel,
        app=context.app,
        summary_lines=summary,
        diagnostics=diag,
        limitations=limitations,
    )


def build_prediction_diagnostic(context: AiContext) -> AiDiagnosticPack:
    facts = context.facts or {}
    scope_label = (
        facts.get("scope_label")
        or context.scope.region_label
        or "선택 scope"
    )
    diag = prediction_diagnostics_from_facts(facts, scope_label=str(scope_label))
    summary = [
        f"scope={scope_label}",
        f"예측={_fmt_num(diag.get('y_hat'), 0)}만원",
    ]
    if diag.get("n") is not None:
        summary.append(f"회귀 n={diag['n']}")
    if diag.get("pi_lower") is not None and diag.get("pi_upper") is not None:
        summary.append(
            f"PI={_fmt_num(diag['pi_lower'], 0)}~{_fmt_num(diag['pi_upper'], 0)}"
        )
    limitations = [
        "예측은 동일 scope OLS 모형 출력이며 적정가·투자 판단이 아닙니다.",
        "PI는 개별 거래 변동을 포함합니다.",
    ]
    return AiDiagnosticPack(
        bundle_id="prediction_explain",
        panel=context.panel,
        app=context.app,
        summary_lines=summary,
        diagnostics=diag,
        limitations=limitations,
    )


def build_matrix_cell_snapshot(context: AiContext) -> AiDiagnosticPack:
    """매트릭스 칸 — 추이 외 스냅샷(히스토그램 등)."""
    facts = context.facts or {}
    scope_label = context.scope.region_label or "선택 scope"
    bins = facts.get("bins") or []
    summary = [f"scope={scope_label}", f"bins={len(bins)}"]
    return AiDiagnosticPack(
        bundle_id="matrix_cell_explain",
        panel=context.panel,
        app=context.app,
        summary_lines=summary,
        diagnostics={
            "scope_label": scope_label,
            "zone_type": facts.get("zone_type"),
            "land_category": facts.get("land_category"),
            "bins": bins,
            "n": facts.get("n"),
        },
        limitations=["칸·필터 scope 내 분포 설명입니다."],
    )


def build_bundle(context: AiContext) -> AiDiagnosticPack:
    facts = context.facts or {}
    panel = context.panel
    bid = resolve_bundle_id(panel)

    if not facts:
        if context.explain:
            return build_from_explain(context)
        return build_from_explain(context)

    kind = _facts_kind(facts)
    if bid == "prediction_explain" or kind == "prediction":
        return build_prediction_diagnostic(context)
    if bid == "trend_diagnostic" or kind == "trend":
        return build_trend_diagnostic(context)
    if kind == "regression":
        return build_regression_diagnostic(context)
    if bid == "matrix_cell_explain":
        return build_matrix_cell_snapshot(context)
    return build_regression_diagnostic(context)
