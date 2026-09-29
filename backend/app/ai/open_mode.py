"""AI Open Mode — 라우팅/템플릿 우회, LLM 우선 (개발·검증용)."""

from __future__ import annotations

from typing import Any

from app.ai.panel_capabilities import get_panel_capability
from app.ai.schemas import AiContext, AiDiagnosticPack
from app.config import settings

_APP_LABEL = {
    "land": "토지",
    "built": "복합부동산",
    "collective": "집합",
    "rent": "임대",
}


def open_mode_enabled() -> bool:
    return bool(settings.ai_open_mode)


def screen_context_block(
    *,
    app: str,
    panel: str,
    scope_label: str,
    purpose: str | None = None,
) -> dict[str, Any]:
    cap = get_panel_capability(panel)
    block: dict[str, Any] = {
        "service": "CH2 Macro",
        "page": cap.label,
        "scope": scope_label,
        "analysis_type": panel,
        "app": app,
        "app_label": _APP_LABEL.get(app, app),
    }
    if purpose:
        block["purpose"] = purpose
    return block


_ROW_KEYS = (
    "name",
    "display_name",
    "asset_label",
    "asset_type",
    "count",
    "median",
    "mean",
    "y",
    "y_hat",
    "ape",
    "households",
    "building_year",
    "building_age",
    "max_floor",
    "parking_per_household",
    "structure_group",
    "builder_group",
    "is_reliable",
)

_CANDIDATE_KEYS = (
    "rank",
    "purpose",
    "blocks",
    "model_type",
    "n",
    "adj_r_squared",
    "mape",
    "cv_mape",
    "hold_mape",
)


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: row.get(k) for k in keys if row.get(k) is not None}


def _compact_rows(raw: Any, limit: int = 40) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw[:limit]:
        if not isinstance(row, dict):
            continue
        item = _pick(row, _ROW_KEYS)
        if item:
            out.append(item)
    return out


def _compact_candidates(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw[:6]:
        if not isinstance(row, dict):
            continue
        item = _pick(row, _CANDIDATE_KEYS)
        if item:
            out.append(item)
    return out


def _compact_coefs(raw: Any, limit: int = 40) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for c in raw[:limit]:
        if not isinstance(c, dict):
            continue
        item = {
            "name": c.get("name") or c.get("variable") or c.get("term"),
            "label": c.get("label"),
            "coef": c.get("coef") if "coef" in c else c.get("coefficient") or c.get("estimate"),
            "p": c.get("p") or c.get("p_value"),
            "significant": c.get("significant"),
            "effect_plain": c.get("effect_plain"),
        }
        out.append({k: v for k, v in item.items() if v is not None})
    return out


def _base_screen_brief(facts: dict[str, Any]) -> dict[str, Any] | None:
    base = facts.get("base_screen")
    if not isinstance(base, dict):
        return None
    inner = base.get("facts") if isinstance(base.get("facts"), dict) else {}
    brief: dict[str, Any] = {
        "panel": base.get("panel"),
        "scope": base.get("scope"),
        "screen": inner.get("screen"),
        "list_n": inner.get("list_n"),
        "window_years": inner.get("window_years"),
        "region_label": inner.get("region_label"),
        "list_sort": inner.get("list_sort"),
        "first_row": inner.get("first_row"),
        "visible_rows": _compact_rows(inner.get("visible_rows")),
    }
    return {k: v for k, v in brief.items() if v is not None and v != []}


def soft_facts_snapshot(
    bundle: AiDiagnosticPack,
    *,
    scope_label: str,
    context: AiContext | None = None,
) -> dict[str, Any]:
    """LLM에 넘길 화면 facts — 강제 해석이 아닌 참고 스냅샷."""
    d = bundle.diagnostics or {}
    keys = (
        "n",
        "fit_n",
        "r_squared",
        "adj_r_squared",
        "mape",
        "cv_mape",
        "hold_mape",
        "model",
        "model_type",
        "formula",
        "scope_label",
        "asset_type",
        "window_years",
        "as_of_month",
        "weight_mode",
        "price_adj_r_squared",
        "display_name",
    )
    facts = context.facts if context is not None and isinstance(context.facts, dict) else {}
    stats = {k: d[k] for k in keys if d.get(k) is not None}
    for key in keys:
        if stats.get(key) is None and facts.get(key) is not None:
            stats[key] = facts.get(key)
    raw_coefs = facts.get("coefficients") or d.get("coefficients") or d.get("coeffs") or []
    coef_brief = _compact_coefs(raw_coefs)
    app = context.app if context is not None else bundle.app
    panel = context.panel if context is not None else bundle.panel
    purpose = context.purpose if context is not None else None
    ctx_block = screen_context_block(
        app=app, panel=panel, scope_label=scope_label, purpose=purpose
    )
    snapshot: dict[str, Any] = {
        **ctx_block,
        "scope_label": scope_label,
        "panel": panel,
        "app": app,
        "bundle_id": bundle.bundle_id,
        "stats": stats,
        "coefficients": coef_brief,
        "summary_lines": list(bundle.summary_lines[:8]),
        "limitations": list(bundle.limitations[:4]),
    }
    equation = facts.get("equation") or d.get("equation")
    if equation:
        snapshot["equation"] = equation
    time_reference = facts.get("time_reference")
    if time_reference:
        snapshot["time_reference"] = time_reference
    candidates = _compact_candidates(facts.get("model_candidates"))
    if candidates:
        snapshot["model_candidates"] = candidates
    comparison = facts.get("model_comparison")
    if isinstance(comparison, dict):
        snapshot["model_comparison"] = {
            "recommended": comparison.get("recommended"),
            "metric_basis": comparison.get("metric_basis"),
            "log": comparison.get("log"),
            "linear": comparison.get("linear"),
        }
    blocks = facts.get("blocks")
    if isinstance(blocks, list) and blocks:
        snapshot["blocks"] = [
            _pick(b, ("block", "label", "weak", "hold_mape", "in_sample_mape", "delta_mape_vs_core", "note"))
            for b in blocks[:12]
            if isinstance(b, dict)
        ]
    sample = facts.get("sample")
    if isinstance(sample, dict):
        snapshot["sample"] = {
            k: sample.get(k)
            for k in (
                "n_pool",
                "n_with_attributes",
                "n_usable_tier",
                "n_analysis",
                "n_fit",
                "n_hold",
                "n_missing_attr",
                "n_weak_tier",
                "n_no_price",
            )
            if sample.get(k) is not None
        }
    fitted = _compact_rows(facts.get("fitted"))
    if fitted:
        snapshot["fitted"] = fitted
    visible = _compact_rows(facts.get("visible_rows"))
    if visible:
        snapshot["visible_rows"] = visible
    if facts.get("list_n") is not None:
        snapshot["list_n"] = facts.get("list_n")
    prediction = facts.get("prediction")
    if isinstance(prediction, dict):
        snapshot["prediction"] = prediction
    base_screen = _base_screen_brief(facts)
    if base_screen:
        snapshot["base_screen"] = base_screen
    warnings = facts.get("warnings")
    if isinstance(warnings, list) and warnings:
        snapshot["warnings"] = [str(w) for w in warnings[:8]]
    return snapshot
