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
        "model",
        "formula",
        "scope_label",
        "asset_type",
        "window_years",
        "as_of_month",
    )
    stats = {k: d[k] for k in keys if d.get(k) is not None}
    coefs = d.get("coefficients") or d.get("coeffs") or []
    coef_brief: list[dict[str, Any]] = []
    if isinstance(coefs, list):
        for c in coefs[:12]:
            if not isinstance(c, dict):
                continue
            coef_brief.append(
                {
                    "name": c.get("name") or c.get("variable") or c.get("term"),
                    "coef": c.get("coef") if "coef" in c else c.get("coefficient"),
                    "p": c.get("p") or c.get("p_value"),
                    "significant": c.get("significant"),
                }
            )
    app = context.app if context is not None else bundle.app
    panel = context.panel if context is not None else bundle.panel
    purpose = context.purpose if context is not None else None
    ctx_block = screen_context_block(
        app=app, panel=panel, scope_label=scope_label, purpose=purpose
    )
    return {
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
