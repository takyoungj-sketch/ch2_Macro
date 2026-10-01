"""다음 행동. 표본 가능 여부는 도구 봉투가 이미 판정한 값만 읽는다."""

from __future__ import annotations

from app.ai2.case_tools import UNAVAILABLE_ANALYSIS
from app.ai2.catalog import get_spec
from app.ai2.types import Action, Alternative, ToolEnvelope

MAX_CALLS = 6


_REASON_KO = {
    "INSUFFICIENT_SAMPLE": "표본이 최소 건수보다 적습니다.",
    "NO_REGION_LEVEL_INDEX": "이 지역 전체의 층별 지수는 없습니다.",
    "PERIOD_UNAVAILABLE": "요청한 기간의 자료는 제공하지 않습니다.",
    "PERIOD_OUTSIDE": "요청한 기간은 분석 구간 밖입니다.",
    "MISSING_INPUTS": "필요한 값이 빠졌습니다.",
    "MEASURE_UNSUPPORTED": "㎡당 가격은 이 분석에서 제공하지 않습니다.",
    "DATABASE_UNAVAILABLE": "자료를 불러오지 못했습니다.",
    "AMBIGUOUS_TARGET": "이름이 둘 이상입니다. 하나만 지정해 주세요.",
    "CONVERSION_GATE": "전환율 최소 조건을 넘지 않습니다.",
    "UNSUPPORTED": "이 도구는 제공하지 않습니다.",
    "REGRESSION_FAILED": "회귀를 계산하지 못했습니다.",
    "NO_DATA_FOR_REGION": "이 지역의 자료가 없습니다.",
    "REGION_EXPANDED": "범위를 넓힌 결과입니다.",
    "EXTRAPOLATION": "입력값이 표본 범위를 벗어납니다.",
}


def _reason_sentence(code: str | None) -> str | None:
    if not code:
        return None
    return _REASON_KO.get(code, "이 조건으로는 진행하지 않습니다.")


def _fmt_impossible(env: ToolEnvelope) -> str:
    parts = ["이 조건으로는 분석을 실행하지 않습니다."]
    reason = _reason_sentence(env.reason_code)
    if reason:
        parts.append(reason)
    if env.valid_n is not None and env.required_n is not None:
        parts.append(f"유효표본 {env.valid_n}건, 최소 {env.required_n}건.")
    missing = env.facts.get("missing")
    if missing:
        parts.append("필요한 값 " + ", ".join(_input_label(str(name)) for name in missing) + ".")
    if env.period:
        parts.append(f"기간 {env.period}.")
    return " ".join(parts)


def _ro(word: str) -> str:
    if not word:
        return "로"
    last = word[-1]
    if not ("가" <= last <= "힣"):
        return "로"
    jong = (ord(last) - ord("가")) % 28
    return "로" if jong in (0, 8) else "으로"


def _offer_message(env: ToolEnvelope, alts: list[Alternative]) -> str:
    bits = []
    reason = _reason_sentence(env.reason_code)
    if reason:
        bits.append(reason)
    if env.valid_n is not None and env.required_n is not None:
        bits.append(f"유효표본 {env.valid_n}건, 최소 {env.required_n}건.")
    selected = env.facts.get("selected")
    selected_n = env.facts.get("selected_n")
    if selected is not None:
        place = "도로" if env.facts.get("place") == "road" else "단지"
        bits.append(f"기준을 넘는 {place}는 {selected} ({selected_n}건)입니다.")
    changes = " 또는 ".join(f"{a.change}{_ro(a.change)}" for a in alts)
    bits.append(f"대신 {changes} 볼 수 있습니다. 어느 쪽으로 진행할까요?")
    return " ".join(bits)


def decide(state) -> Action:
    unavailable = UNAVAILABLE_ANALYSIS.get(state.ctx.analysis_type or "")
    if unavailable:
        return Action(kind="refuse", message=unavailable)
    spec = get_spec(state.ctx.analysis_type)
    if spec is None or state.ctx.property_type not in spec.property_types:
        return Action(kind="refuse", message="이 분석은 제공하지 않습니다.")
    if spec.needs_target and not state.ctx.target:
        return Action(kind="ask", message=spec.ask)
    if spec.needs_measure and not state.ctx.measure:
        return Action(kind="ask", message=spec.ask or "총액인가요, ㎡당인가요?")
    called = {e.tool_id for e in state.envelopes}
    if not spec.needs_target and spec.direct_tool not in called:
        return Action(kind="call", message="", tool_id=spec.direct_tool, args={})
    if (
        state.ctx.target == "region"
        and spec.discovery_tool
        and spec.discovery_tool not in called
    ):
        return Action(kind="call", message="", tool_id=spec.discovery_tool, args={})
    if state.envelopes:
        last = state.envelopes[-1]
        for alt in last.alternative_tools:
            if not alt.needs_confirm and alt.id not in called:
                return Action(kind="call", message="", tool_id=alt.id, args=dict(alt.args))
        pending = [
            a for a in last.alternative_tools if a.needs_confirm and a.id not in called
        ]
        if pending and state.phase != "offered":
            return Action(
                kind="offer",
                message=_offer_message(last, pending),
                alternatives=pending,
            )
        period_applied = last.reason_code == "PERIOD_APPLIED"
        if last.analysis_possible is False and not last.alternative_tools and not period_applied:
            return Action(kind="refuse", message=_fmt_impossible(last), envelope=last)
    if (
        state.ctx.target
        and state.ctx.target != "region"
        and spec.direct_tool not in called
    ):
        return Action(
            kind="call",
            message="",
            tool_id=spec.direct_tool,
            args={"target": state.ctx.target},
        )
    direct = next((e for e in state.envelopes if e.tool_id == spec.direct_tool), None)
    if (
        spec.follow_tool
        and spec.follow_tool not in called
        and direct is not None
        and direct.analysis_possible
    ):
        return Action(
            kind="call",
            message="",
            tool_id=spec.follow_tool,
            args={"local_index": direct.facts.get("local_index")},
        )
    discovery_done = (
        state.ctx.target == "region"
        and spec.discovery_tool is not None
        and spec.discovery_tool in called
        and state.envelopes[-1].analysis_possible
        and not state.envelopes[-1].alternative_tools
    )
    if direct is not None and (spec.follow_tool is None or spec.follow_tool in called):
        return _report_action(state)
    if discovery_done and (spec.follow_tool is None or spec.follow_tool in called):
        return _report_action(state)
    if (
        discovery_done
        and spec.follow_tool
        and spec.follow_tool not in called
    ):
        return Action(kind="call", message="", tool_id=spec.follow_tool, args={})
    if state.envelopes:
        return Action(kind="refuse", message=_fmt_impossible(state.envelopes[-1]))
    return Action(kind="refuse", message="이 분석은 제공하지 않습니다.")


def _report_action(state) -> Action:
    return Action(
        kind="report",
        message=_report(state.ctx, state.envelopes),
        verdict=None,
        comparable=_comparable(state.envelopes),
    )


def _comparable(envelopes: list[ToolEnvelope]) -> bool | None:
    for env in reversed(envelopes):
        if env.comparable is not None:
            return env.comparable
    return None


_INPUT_KO = {
    "building_age": "연식",
    "road_width": "도로폭",
    "road_width_label": "도로폭",
    "zone_type": "용도지역",
    "building_use": "건물용도",
    "structure_group": "구조",
    "gross_area": "연면적",
    "land_area": "대지면적",
}


def _input_label(name: str) -> str:
    return _INPUT_KO.get(name, name)


def _report(ctx, envelopes: list[ToolEnvelope]) -> str:
    lines = []
    if ctx.analysis_type == "built_predict" or ctx.measure:
        lines.append("과거 거래에 맞춘 중심값과 예측구간입니다.")
    if ctx.measure == "unit_price":
        lines.append("기준은 ㎡당입니다.")
    elif ctx.measure == "total" or any(env.facts.get("price_basis") == "total" for env in envelopes):
        lines.append("기준은 총액입니다.")
    where = []
    if ctx.region:
        where.append(f"지역은 {ctx.region}입니다.")
    if ctx.target and ctx.target != "region":
        where.append(f"대상은 {ctx.target}입니다.")
    if where:
        lines.append(" ".join(where))
    result_keys = ("local_index", "y_hat", "conversion_rate", "twin_region", "index_rule", "top_floor_index")
    has_result = any(any(env.facts.get(key) is not None for key in result_keys) for env in envelopes)
    for env in envelopes:
        if has_result and not any(env.facts.get(key) is not None for key in result_keys):
            continue
        bits: list[str] = []
        if env.valid_n is not None and env.required_n is not None:
            bits.append(f"유효표본 {env.valid_n}건, 최소 {env.required_n}건.")
        if env.period and env.facts.get("top_floor_index") is None:
            bits.append(f"기간 {env.period}.")
        if env.facts.get("y_hat_suppressed"):
            bits.append("중심값 숨김.")
            bits.append(f"예측구간 {env.facts.get('pi_lower')}–{env.facts.get('pi_upper')}.")
        elif env.facts.get("y_hat") is not None:
            bits.append(
                f"중심값 {env.facts['y_hat']}, 예측구간 {env.facts.get('pi_lower')}–{env.facts.get('pi_upper')}."
            )
        if env.facts.get("reference_inputs"):
            names = ", ".join(_input_label(str(name)) for name in env.facts["reference_inputs"])
            bits.append(f"비어 있던 조건은 기준값 {names}.")
        if env.facts.get("price_base_year") is not None:
            bits.append(f"기준 연도 {env.facts['price_base_year']}.")
        if env.facts.get("conversion_rate") is not None:
            bits.append(
                f"기준 지역 {env.facts.get('rate_region') or '-'}. "
                f"적용 전환율 {env.facts['conversion_rate']}%. "
                f"창 {env.facts.get('window_years')}년. 전세 시세가 아닙니다."
            )
        if env.facts.get("twin_adopted") is False:
            local_mape = env.facts.get("local_cv_mape")
            twin_mape = env.facts.get("twin_cv_mape")
            if local_mape is not None and twin_mape is not None:
                bits.append(f"로컬 {local_mape}, 쌍둥이 {twin_mape}. 쌍둥이는 결론으로 쓰지 않음.")
            else:
                bits.append(f"쌍둥이 {env.facts.get('twin_region') or '-'}. 쌍둥이는 결론으로 쓰지 않음.")
        elif env.facts.get("twin_adopted") is True:
            bits.append(
                f"쌍둥이는 {env.facts.get('twin_region')}. "
                f"검증 {env.facts.get('twin_cv_mape')}, 로컬 {env.facts.get('local_cv_mape')}."
            )
        if env.facts.get("local_index") is not None and env.facts.get("top_floor_index") is None:
            bits.append(f"지수 {env.facts['local_index']}.")
        if env.facts.get("blank_group"):
            bits.append(
                f"{env.facts['blank_group']} {env.facts.get('blank_group_n')}건이라 칸을 비움."
            )
        if env.facts.get("index_rule"):
            bits.append(str(env.facts["index_rule"]))
        if env.facts.get("reran") is False:
            bits.append("회귀를 다시 돌리지 않음.")
        if env.facts.get("top_floor_index") is not None:
            bits.append(f"Insight {env.facts.get('insight_id')}은 {env.facts['top_floor_index']}.")
        if (
            env.comparable is False
            and env.facts.get("local_index") is not None
            and env.facts.get("top_floor_index") is not None
        ):
            bits.append("어느 결과를 채택하지 않습니다.")
        if bits:
            lines.append(" ".join(bits))
    return " ".join(lines)
