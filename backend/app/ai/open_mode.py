"""AI Open Mode — 라우팅/템플릿 우회, LLM 우선 (개발·검증용)."""

from __future__ import annotations

from typing import Any

from app.ai.schemas import AiDiagnosticPack
from app.config import settings


def open_mode_enabled() -> bool:
    return bool(settings.ai_open_mode)


def soft_facts_snapshot(bundle: AiDiagnosticPack, *, scope_label: str) -> dict[str, Any]:
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
    return {
        "scope_label": scope_label,
        "panel": bundle.panel,
        "app": bundle.app,
        "bundle_id": bundle.bundle_id,
        "stats": stats,
        "coefficients": coef_brief,
        "summary_lines": list(bundle.summary_lines[:8]),
        "limitations": list(bundle.limitations[:4]),
    }
