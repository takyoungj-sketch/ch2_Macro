"""Intent → 후보 경로 → 현재 Context 실행 가능성 → 순위.

숫자를 만들지 않는다. executable은 yes / no / unknown.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from app.ai.knowledge.playbook import INTENTS, path_meta
from app.ai.schemas import AiContext

Executable = Literal["yes", "no", "unknown"]

_GAP_TYPE_HINTS = ("오피스텔", "아파트", "유형")
_GAP_CMP_HINTS = ("가격 차이", "가격차이", "가격격차", "격차", "차이", "비교", "상대")


def is_path_intent_question(message: str) -> bool:
    """목적·경로 질문인가 (이번 결과 Explain과 구분)."""
    m = message.strip()
    if any(k in m for k in ("왜 이 결과", "왜 이렇게", "이 화면", "이번 표본", "이 계수")):
        return False
    # 「요약/설명」은 현재 화면 해석. 격차·경로 질문은 예외.
    if any(k in m for k in ("요약해", "설명해", "해석해", "풀어 주")):
        if detect_intent(m) == "apartment_officetel_price_gap":
            return True
        return any(
            k in m
            for k in ("어떻게 분석", "어떤 분석", "어떤 경로", "어떻게 접근", "보고 싶", "알고 싶")
        )
    if detect_intent(m):
        return True
    path_ask = (
        "알고 싶",
        "보고 싶",
        "분석해",
        "분석 경로",
        "어떻게 접근",
        "어떻게 분석",
        "어떤 분석",
        "어떤 경로",
        "어떤 기능",
        "통합회귀",
        "코호트",
    )
    return any(k in m for k in path_ask)


def is_memo_request(message: str) -> bool:
    m = message.strip()
    return any(
        k in m
        for k in ("정리해", "정리 해", "보고서로", "분석 메모", "지금까지 분석", "지금까지 실행", "히스토리")
    )


def detect_intent(message: str) -> Optional[str]:
    m = message.strip()
    lower = m.lower()

    # 아파트 vs 오피스텔 격차: 유형 힌트 + 비교 힌트
    if any(k in m for k in _GAP_TYPE_HINTS) and any(k in m for k in _GAP_CMP_HINTS):
        return "apartment_officetel_price_gap"
    if "오피스텔" in m and ("아파트" in m or "유형" in m):
        return "apartment_officetel_price_gap"

    for iid, spec in INTENTS.items():
        if iid == "apartment_officetel_price_gap":
            continue
        keys = spec.get("keywords") or ()
        if any(k.lower() in lower or k in m for k in keys):
            return iid
    return None


def _asset_types_present(context: AiContext, facts: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    at = (context.scope.asset_type or "").strip().lower()
    if at:
        found.add(at)
    nbt = facts.get("n_by_type") or facts.get("type_counts") or {}
    if isinstance(nbt, dict):
        for k, v in nbt.items():
            try:
                if int(v) > 0:
                    found.add(str(k).lower())
            except (TypeError, ValueError):
                continue
    filters = context.scope.filters or {}
    raw = filters.get("asset_types") or filters.get("asset_type")
    if isinstance(raw, (list, tuple)):
        found.update(str(x).lower() for x in raw if x)
    elif isinstance(raw, str) and raw:
        found.update(p.strip().lower() for p in raw.split(",") if p.strip())
    return {x for x in found if x}


def _has_regression_bundle(facts: dict[str, Any]) -> bool:
    if not facts:
        return False
    primary = facts.get("primary") if isinstance(facts.get("primary"), dict) else facts
    if not isinstance(primary, dict):
        return False
    return bool(primary.get("coefficients") or facts.get("coefficients"))


def assess_feasibility(path_id: str, context: AiContext) -> dict[str, Any]:
    """현재 화면/facts로 이 경로를 바로 실행할 수 있는가."""
    facts = context.facts or {}
    app = context.app
    types = _asset_types_present(context, facts)
    has_reg = _has_regression_bundle(facts)
    cohort = bool(facts.get("cohort"))
    reasons: list[str] = []
    executable: Executable = "unknown"

    if path_id == "collective_integrated_regression":
        if app not in ("collective",):
            executable = "no"
            reasons.append("집합(주거) 앱에서 코호트에 유형을 넣고 통합회귀를 실행하세요.")
        elif "officetel" in types and "apartment" in types:
            executable = "yes" if (has_reg and cohort) else "unknown"
            if has_reg and cohort:
                reasons.append("현재 화면에 통합회귀 결과가 있습니다.")
            else:
                reasons.append(
                    "두 유형이 선택되어 있습니다. 코호트에서 유형 더미를 켠 통합회귀를 실행하면 됩니다."
                )
        elif types and not ({"apartment", "officetel"} <= types) and len(types) < 2:
            executable = "no"
            reasons.append(
                "현재 화면은 한 유형입니다. 아파트와 오피스텔을 같은 코호트에 넣어야 유형 비교가 됩니다."
            )
        else:
            executable = "unknown"
            reasons.append(
                "현재 화면에 두 유형 표본이 확인되지 않습니다. "
                "주거 집합에서 동일·인접 단지를 코호트에 넣고 통합회귀를 실행하세요."
            )
    elif path_id == "collective_cohort":
        if app != "collective":
            executable = "no"
            reasons.append("집합 앱에서 코호트에 단지(또는 cluster)를 추가하세요.")
        elif cohort or has_reg:
            executable = "yes"
            reasons.append("집합 코호트/회귀 화면이 열려 있습니다.")
        else:
            executable = "unknown"
            reasons.append("집합 목록에서 코호트에 단지를 넣은 뒤 「통합분석」을 누르세요.")
    elif path_id == "regional_regression":
        if has_reg and "regional" in (context.panel or "").lower():
            executable = "yes"
        else:
            executable = "unknown"
            reasons.append("지역회귀는 해당 화면에서 실행합니다. 지금 Bundle에 지역회귀 결과가 없으면 숫자를 인용하지 않습니다.")
    elif path_id == "expand_adjacent":
        if has_reg:
            executable = "unknown"
            reasons.append("인접 확대는 별도 실행이 필요합니다. 현재 결과만으로 확대 n을 만들지 않습니다.")
        else:
            executable = "no"
            reasons.append("먼저 현재 지역에서 회귀가 성공해야 확대 비교가 가능합니다.")
    elif path_id == "profile_twin":
        executable = "unknown"
        reasons.append("지역프로필 앱에서 Twin을 연 뒤에만 유사 지역 이름을 인용할 수 있습니다.")
    elif path_id == "built_regression":
        executable = "yes" if app == "built" and has_reg else ("unknown" if app == "built" else "no")
        if executable == "no":
            reasons.append("복합 앱에서 회귀를 실행하세요.")
    elif path_id == "land_matrix":
        executable = "yes" if app == "land" and facts else ("unknown" if app == "land" else "no")
    else:
        executable = "unknown"
        reasons.append("확인된 실행 조건이 부족합니다.")

    return {
        "path_id": path_id,
        "executable": executable,
        "reasons": reasons,
    }


def plan_analysis(message: str, context: AiContext) -> dict[str, Any]:
    intent_id = detect_intent(message)
    spec = INTENTS.get(intent_id or "") if intent_id else None
    path_ids: list[str] = list(spec["paths"]) if spec else []
    if not path_ids and is_path_intent_question(message):
        # 가까운 기본: 집합 코호트 → 통합회귀
        path_ids = ["collective_cohort", "collective_integrated_regression"]

    ranked = []
    for i, pid in enumerate(path_ids):
        feas = assess_feasibility(pid, context)
        meta = path_meta(pid)
        ranked.append(
            {
                "rank": i + 1,
                "path_id": pid,
                "label": meta.get("label") or pid,
                "purpose": meta.get("purpose") or "",
                "executable": feas["executable"],
                "reasons": feas["reasons"],
            }
        )

    # 실행 가능한 것을 위로 — 순위는 Playbook 순서를 유지하되 no는 안내만
    return {
        "intent_id": intent_id,
        "intent_label": (spec or {}).get("label"),
        "paths": ranked,
        "unknown_playbook": spec is None,
    }


def format_plan_answer(plan: dict[str, Any], *, caveats_text: str = "") -> str:
    lines: list[str] = []
    if plan.get("intent_label"):
        lines.append(f"**분석 목적:** {plan['intent_label']}")
    elif plan.get("unknown_playbook"):
        lines.append(
            "확인된 플레이북이 없는 질문입니다. CH2에 있는 가까운 기능부터 안내합니다."
        )
    lines.append("")
    lines.append("CH2 Macro에서는 다음 순서로 접근하는 것이 좋습니다. (숫자는 엔진 실행 후에만 인용합니다.)")
    for p in plan.get("paths") or []:
        exe = p.get("executable")
        flag = {"yes": "지금 화면에서 결과 있음", "no": "지금 화면에서는 바로 실행 어려움", "unknown": "실행 전·조건 확인 필요"}.get(
            exe, "실행 전"
        )
        lines.append(f"{p['rank']}. **{p['label']}** — {p.get('purpose') or ''} ({flag})")
        for r in p.get("reasons") or []:
            lines.append(f"   - {r}")
    if caveats_text:
        lines.append("")
        lines.append(caveats_text)
    lines.append("")
    lines.append(
        "투자·매수·적정가 판단이 아닙니다. 경로만 제안하며, 계수는 해당 회귀가 성공한 뒤에만 말합니다."
    )
    return "\n".join(lines).strip()
