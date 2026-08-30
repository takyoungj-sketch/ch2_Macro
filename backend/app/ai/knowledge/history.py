"""Analysis History — 성공한 분석 Bundle만. 채팅 전문이 아님. D-056."""

from __future__ import annotations

import time
from typing import Any, Optional
from uuid import uuid4

from app.ai.knowledge.caveats import caveat_ids, fire_caveats
from app.ai.knowledge.planner import detect_intent
from app.ai.schemas import AiContext, AnalysisHistorySlot
from app.ai.sessions import AiSession

HISTORY_BUNDLE_IDS = frozenset(
    {
        "regression_diagnostic",
    }
)
MAX_SLOTS = 12


def _coerce_n(raw: Any) -> Any:
    if raw is None:
        return None
    try:
        f = float(raw)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return raw

# 목록·지도·기간 변경은 Bundle이 이 id가 아니므로 제외.


def _primary(facts: dict[str, Any]) -> dict[str, Any]:
    p = facts.get("primary")
    return p if isinstance(p, dict) else facts


def _n_by_type(facts: dict[str, Any], scope_asset: Optional[str]) -> dict[str, Any]:
    nbt = facts.get("n_by_type") or facts.get("type_counts")
    if isinstance(nbt, dict) and nbt:
        return {str(k): v for k, v in nbt.items()}
    if scope_asset:
        n = _primary(facts).get("n")
        if n is not None:
            return {scope_asset: n}
    return {}


def _key_coeffs(facts: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    primary = _primary(facts)
    raw = primary.get("coefficients") or facts.get("coefficients") or []
    out: list[dict[str, Any]] = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or c.get("label") or "")
        out.append(
            {
                "name": name,
                "estimate": c.get("estimate", c.get("coef")),
                "p_value": c.get("p_value", c.get("p")),
            }
        )
        if len(out) >= limit:
            break
    return out


def _fingerprint(slot: dict[str, Any]) -> tuple[Any, ...]:
    return (
        slot.get("path_id"),
        slot.get("n"),
        (slot.get("scope") or {}).get("region_label"),
        tuple((slot.get("caveat_ids") or [])[:6]),
        str((slot.get("metrics") or {}).get("adj_r_squared")),
    )


def infer_path_id(context: AiContext) -> str:
    facts = context.facts or {}
    if facts.get("cohort"):
        types = _n_by_type(facts, context.scope.asset_type)
        if len(types) >= 2:
            return "collective_integrated_regression"
        return "collective_cohort"
    panel = context.panel or ""
    if "Regional" in panel or "regional" in panel.lower():
        return "regional_regression"
    if context.app == "built":
        return "built_regression"
    if context.app == "land":
        return "land_matrix"
    return "collective_building_regression"


def slot_from_success_bundle(
    context: AiContext,
    *,
    bundle_id: str,
    diagnostics: dict[str, Any],
    message: str = "",
) -> Optional[AnalysisHistorySlot]:
    if bundle_id not in HISTORY_BUNDLE_IDS:
        return None
    facts = context.facts or {}
    primary = _primary(facts)
    n = diagnostics.get("n") if diagnostics.get("n") is not None else primary.get("n")
    coeffs = primary.get("coefficients") or facts.get("coefficients")
    if n is None or not coeffs:
        return None
    warnings = list(diagnostics.get("warnings") or facts.get("warnings") or [])
    n_by_type = _n_by_type(facts, context.scope.asset_type)
    fired = fire_caveats(
        n=n,
        warnings=warnings,
        n_by_type=n_by_type,
        adj_r_squared=diagnostics.get("adj_r_squared") or primary.get("adj_r_squared"),
        vif_warning=diagnostics.get("vif_warning"),
    )
    intent_id = detect_intent(message) if message else None
    path_id = infer_path_id(context)
    return AnalysisHistorySlot(
        id=str(uuid4())[:12],
        at=time.time(),
        intent_id=intent_id,
        path_id=path_id,
        scope={
            "region_label": context.scope.region_label or diagnostics.get("scope_label"),
            "asset_type": context.scope.asset_type,
        },
        n=n if isinstance(n, int) else _coerce_n(n),
        n_by_type=n_by_type,
        metrics={
            "adj_r_squared": diagnostics.get("adj_r_squared") or primary.get("adj_r_squared"),
            "mape": diagnostics.get("mape") or primary.get("mape"),
        },
        key_coeffs=_key_coeffs(facts),
        warnings=warnings[:12],
        caveat_ids=caveat_ids(fired),
        source="engine_bundle",
        recommended_path=None,
        executed_path=path_id,
        user_override=None,
    )


def maybe_record(
    session: AiSession,
    context: AiContext,
    *,
    bundle_id: str,
    diagnostics: dict[str, Any],
    message: str = "",
) -> Optional[AnalysisHistorySlot]:
    slot = slot_from_success_bundle(
        context, bundle_id=bundle_id, diagnostics=diagnostics, message=message
    )
    if slot is None:
        return None
    fp = _fingerprint(slot.model_dump())
    for existing in session.analysis_history:
        if _fingerprint(existing) == fp:
            return None
    session.push_analysis(slot.model_dump())
    return slot


def format_history_for_prompt(slots: list[dict[str, Any]]) -> str:
    if not slots:
        return ""
    lines = ["[Analysis History — 실행된 분석만. 없는 숫자를 만들지 말 것]"]
    for i, s in enumerate(slots, start=1):
        scope = (s.get("scope") or {}).get("region_label") or "—"
        n = s.get("n")
        cids = ",".join(s.get("caveat_ids") or []) or "—"
        lines.append(
            f"#{i} path={s.get('path_id')} scope={scope} n={n} caveats={cids}"
        )
        for c in (s.get("key_coeffs") or [])[:4]:
            if isinstance(c, dict):
                lines.append(
                    f"    {c.get('name')}: est={c.get('estimate')} p={c.get('p_value')}"
                )
    return "\n".join(lines)


def format_memo(slots: list[dict[str, Any]]) -> str:
    if not slots:
        return (
            "아직 이 세션에서 **성공한 분석**이 기록되지 않았습니다. "
            "목록 조회만으로는 History가 생기지 않습니다. "
            "집합·복합·지역 회귀가 성공하면 자동으로 기록됩니다."
        )
    lines = [
        "**분석 메모** (CH2에서 실행된 결과만. 적정가·투자 의견 아님)",
        "",
    ]
    for i, s in enumerate(slots, start=1):
        scope = (s.get("scope") or {}).get("region_label") or "선택 지역"
        n = s.get("n")
        metrics = s.get("metrics") or {}
        adj = metrics.get("adj_r_squared")
        lines.append(f"### {i}차 — {s.get('path_id')}")
        lines.append(f"- 범위: {scope} · n={n}")
        if s.get("n_by_type"):
            lines.append(f"- 유형별 n: {s['n_by_type']}")
        if adj is not None:
            lines.append(f"- Adj R²: {adj}")
        for c in (s.get("key_coeffs") or [])[:6]:
            if isinstance(c, dict):
                lines.append(
                    f"- {c.get('name')}: {c.get('estimate')} (p={c.get('p_value')})"
                )
        cids = s.get("caveat_ids") or []
        if cids:
            lines.append(f"- 유의: {', '.join(cids)}")
        ov = s.get("user_override")
        rec = s.get("recommended_path")
        exe = s.get("executed_path")
        if rec and exe and rec != exe:
            lines.append(
                f"- 당초 {rec}를 검토할 수 있었으나 {exe}를 대상으로 분석하였다."
            )
        elif ov:
            lines.append(f"- 사용자 선택: {ov}")
        lines.append("")
    lines.append("한계: 이번 선택 기간·지역 내 패턴입니다. 인과·적정가·투자 판단이 아닙니다.")
    return "\n".join(lines).strip()
