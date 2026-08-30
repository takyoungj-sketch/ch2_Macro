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
    """분석 *방법*을 고르는 질문인가. 화면 사용법·추세 안내는 여기로 보내지 않는다."""
    m = message.strip()
    if any(k in m for k in ("왜 이 결과", "왜 이렇게", "이 화면", "이번 표본", "이 계수")):
        return False
    if detect_intent(m) == "apartment_officetel_price_gap":
        return True
    method_ask = (
        "분석 경로",
        "어떤 경로",
        "어떤 분석",
        "어떻게 분석",
        "어떻게 접근",
        "어떤 기능",
        "경로를 추천",
        "통합회귀",
        "코호트",
        "지역회귀",
    )
    return any(k in m for k in method_ask)


def is_memo_request(message: str) -> bool:
    m = message.strip()
    return any(
        k in m
        for k in ("정리해", "정리 해", "보고서로", "분석 메모", "지금까지 분석", "지금까지 실행", "히스토리")
    ) and "비교" not in m


def is_history_compare_question(message: str) -> bool:
    """P3-4: 이전 History 슬롯 비교. 유형 격차 질문과 구분."""
    m = message.strip()
    if any(k in m for k in ("오피스텔", "아파트와", "유형 효과", "용도지역")):
        if "아까" not in m and "이전 분석" not in m and "슬롯" not in m:
            return False
    if any(
        k in m
        for k in (
            "아까와 비교",
            "이전 분석과",
            "이전과 비교",
            "히스토리 비교",
            "슬롯 비교",
            "1차와 2차",
        )
    ):
        return True
    return ("아까" in m or "이전 실행" in m or "방금 전" in m) and any(
        k in m for k in ("비교", "차이", "달라")
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
        "아래 버튼은 **기존 CH2 화면**으로 보내거나, 승인 후에만 엔진을 돌립니다. "
        "AI가 코호트 구성을 바꾸거나 계수를 계산하지 않습니다."
    )
    lines.append(
        "투자·매수·적정가 판단이 아닙니다. 경로만 제안하며, 계수는 해당 회귀가 성공한 뒤에만 말합니다."
    )
    return "\n".join(lines).strip()


def _action(
    *,
    aid: str,
    kind: str,
    label: str,
    href: str | None = None,
    ui: str | None = None,
    path_id: str | None = None,
    confirm_message: str | None = None,
) -> dict[str, Any]:
    return {
        "id": aid,
        "kind": kind,
        "label": label,
        "href": href,
        "ui": ui,
        "path_id": path_id,
        "confirm_message": confirm_message,
    }


_RUN_CONFIRM = (
    "현재 화면에 설정된 단지(또는 cluster)·변수로 CH2 회귀를 실행합니다. "
    "AI가 조건을 바꾸거나 숫자를 계산하지 않습니다."
)

_RUN_CONFIRM_BUILT = (
    "현재 화면에 설정된 지역·변수로 CH2 회귀를 실행합니다. "
    "AI가 조건을 바꾸거나 숫자를 계산하지 않습니다."
)


def actions_for_plan(plan: dict[str, Any], context: AiContext) -> list[dict[str, Any]]:
    """P3: 화면 이동(P3-1) · 승인 실행(P3-2). 코호트 프리필 없음."""
    app = context.app
    panel = context.panel or ""
    on_collective = app == "collective" and panel not in ("CollectiveLanding",)
    on_commercial = "Commercial" in panel
    on_building = panel in ("BuildingRegressionPanel", "CommercialRegressionPanel") or "RegressionPanel" in panel
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(item: dict[str, Any]) -> None:
        key = item["id"]
        if key in seen:
            return
        seen.add(key)
        out.append(item)

    for p in plan.get("paths") or []:
        pid = p.get("path_id")
        exe = p.get("executable")
        if pid == "collective_cohort":
            if not on_collective:
                add(
                    _action(
                        aid="nav-coll-cohort",
                        kind="navigate",
                        label="주거 집합에서 코호트 구성",
                        href="/collective/residential/",
                        path_id=pid,
                    )
                )
            else:
                add(
                    _action(
                        aid="ui-coll-cohort",
                        kind="open_ui",
                        label="코호트 화면으로 (기존 단지 모달)",
                        ui="collective_cohort",
                        path_id=pid,
                    )
                )
        elif pid == "collective_integrated_regression":
            if not on_collective:
                add(
                    _action(
                        aid="nav-coll-integrated",
                        kind="navigate",
                        label="주거 집합에서 통합회귀",
                        href="/collective/residential/",
                        path_id=pid,
                    )
                )
            elif exe == "no":
                add(
                    _action(
                        aid="ui-coll-cohort-types",
                        kind="open_ui",
                        label="코호트에 비교 유형 추가",
                        ui="collective_cohort",
                        path_id=pid,
                    )
                )
            elif on_building and exe != "yes":
                add(
                    _action(
                        aid="run-coll-integrated",
                        kind="run_engine",
                        label="현재 설정으로 통합회귀 실행",
                        ui="collective_integrated",
                        path_id=pid,
                        confirm_message=_RUN_CONFIRM,
                    )
                )
            else:
                add(
                    _action(
                        aid="ui-coll-integrated",
                        kind="open_ui",
                        label="단지 모달에서 통합회귀",
                        ui="collective_cohort",
                        path_id=pid,
                    )
                )
        elif pid == "collective_building_regression":
            if on_collective:
                add(
                    _action(
                        aid="ui-coll-building",
                        kind="open_ui",
                        label="단지 회귀 탭",
                        ui="collective_cohort",
                        path_id=pid,
                    )
                )
            else:
                add(
                    _action(
                        aid="nav-coll-building",
                        kind="navigate",
                        label="집합에서 단지 회귀",
                        href="/collective/residential/",
                        path_id=pid,
                    )
                )
        elif pid == "regional_regression":
            if on_commercial:
                continue
            if on_collective:
                add(
                    _action(
                        aid="ui-coll-regional",
                        kind="open_ui",
                        label="지역회귀 모달 열기",
                        ui="collective_regional",
                        path_id=pid,
                    )
                )
            else:
                add(
                    _action(
                        aid="nav-coll-regional",
                        kind="navigate",
                        label="집합에서 지역회귀",
                        href="/collective/residential/",
                        path_id=pid,
                    )
                )
        elif pid == "expand_adjacent":
            if on_collective and not on_commercial:
                add(
                    _action(
                        aid="ui-coll-expand",
                        kind="open_ui",
                        label="지역을 넓혀 지역회귀",
                        ui="collective_regional",
                        path_id=pid,
                    )
                )
        elif pid == "profile_twin":
            if app != "profile":
                add(
                    _action(
                        aid="nav-profile",
                        kind="navigate",
                        label="지역 프로필 Twin",
                        href="/profile/",
                        path_id=pid,
                    )
                )
            else:
                add(
                    _action(
                        aid="ui-profile-twin",
                        kind="open_ui",
                        label="Twin 카드로 이동",
                        ui="profile_twin",
                        path_id=pid,
                    )
                )
        elif pid == "built_regression":
            if app != "built":
                add(
                    _action(
                        aid="nav-built",
                        kind="navigate",
                        label="복합 회귀 화면으로",
                        href="/built/",
                        path_id=pid,
                    )
                )
            elif exe == "yes":
                add(
                    _action(
                        aid="ui-built-reg",
                        kind="open_ui",
                        label="회귀 카드로 이동",
                        ui="built_regression",
                        path_id=pid,
                    )
                )
            else:
                add(
                    _action(
                        aid="run-built-reg",
                        kind="run_engine",
                        label="현재 설정으로 복합 회귀 실행",
                        ui="built_regression",
                        path_id=pid,
                        confirm_message=_RUN_CONFIRM_BUILT,
                    )
                )
        elif pid == "land_matrix":
            if app != "land":
                add(
                    _action(
                        aid="nav-land",
                        kind="navigate",
                        label="토지 매트릭스로",
                        href="/land/",
                        path_id=pid,
                    )
                )
            else:
                add(
                    _action(
                        aid="ui-land-matrix",
                        kind="open_ui",
                        label="토지 통계 화면으로",
                        ui="land_matrix",
                        path_id=pid,
                    )
                )
    return out
