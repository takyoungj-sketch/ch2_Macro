"""질문 한 턴. call은 사용자 입력 없이 이어서 실행하고, offer·ask·refuse·report에서 멈춘다."""

from __future__ import annotations

from dataclasses import dataclass, field

from collections.abc import Callable

from app.ai2.case_tools import CASES, install_case_specs, run_case_tool
from app.ai2.catalog import get_spec
from app.ai2.floor_tools import WORLDS, install_floor_spec, run_floor_tool
from app.ai2.live_cases import run_live_built, run_live_twin
from app.ai2.live_domains import run_live_profile, run_live_rent, run_live_shop
from app.ai2.live_floor import run_live_floor
from app.ai2.llm import LlmDraft, accept_report, restore_required_clauses
from app.ai2.parse import parse_sentence
from app.ai2.planner import MAX_CALLS, decide
from app.ai2.types import Action, Alternative, AnalysisContext, ToolEnvelope

ToolRunner = Callable[[str, AnalysisContext, dict], ToolEnvelope]
ContextReader = Callable[[str, AnalysisContext], LlmDraft | None]
ReportWriter = Callable[[str], str | None]
ToolChooser = Callable[[list[Alternative], dict], str | None]


@dataclass
class Session:
    ctx: AnalysisContext
    world_name: str = "one_eligible"
    envelopes: list[ToolEnvelope] = field(default_factory=list)
    pending: list[Alternative] = field(default_factory=list)
    phase: str = "ready"
    calls: int = 0
    queue: list[tuple[str, AnalysisContext]] = field(default_factory=list)
    segments: list[tuple[str, str]] = field(default_factory=list)
    claim: str | None = None
    llm_mode: str = "off"


@dataclass
class Turn:
    region: str | None = None
    property_type: str | None = None
    analysis_type: str | None = None
    target: str | None = None
    period: str | None = None
    measure: str | None = None
    accept_offer: bool = False
    offer_index: int = 0
    also_fixture: str | None = None
    also_region: str | None = None
    also_property_type: str | None = None
    also_analysis_type: str | None = None
    also_target: str | None = None
    drop_property_type: str | None = None
    explain: bool = False
    claimed_n: int | None = None
    claim: str | None = None
    sentence: str | None = None
    gross_area: float | None = None
    land_area: float | None = None
    building_age: float | None = None
    road_width_label: str | None = None
    screen_region: str | None = None


def install_protocol_specs() -> None:
    install_floor_spec()
    install_case_specs()


def known_fixtures() -> dict[str, object]:
    return {
        **WORLDS,
        **CASES,
        "live": "live",
        "live_twin": "live_twin",
        "live_built": "live_built",
        "live_shop": "live_shop",
        "live_rent": "live_rent",
        "live_profile": "live_profile",
    }


def run_registered_tool(tool_id: str, ctx: AnalysisContext, args: dict, world_name: str) -> ToolEnvelope:
    if world_name == "live":
        return run_live_floor(tool_id, ctx, args)
    if world_name == "live_twin":
        return run_live_twin(tool_id, ctx)
    if world_name == "live_built":
        return run_live_built(tool_id, ctx)
    if world_name == "live_shop":
        return run_live_shop(tool_id, ctx, args)
    if world_name == "live_rent":
        return run_live_rent(tool_id, ctx)
    if world_name == "live_profile":
        return run_live_profile(tool_id, ctx)
    if world_name in WORLDS:
        return run_floor_tool(tool_id, ctx, args, WORLDS[world_name])
    if world_name in CASES:
        return run_case_tool(tool_id, ctx, CASES[world_name])
    return ToolEnvelope(
        tool_id=tool_id,
        level="impossible",
        analysis_possible=False,
        reason_code="UNSUPPORTED",
    )


def new_session(world_name: str = "one_eligible") -> Session:
    install_protocol_specs()
    if world_name not in known_fixtures():
        raise KeyError(world_name)
    return Session(ctx=AnalysisContext(), world_name=world_name)


def _question_changed(state: Session, turn: Turn) -> bool:
    pairs = (
        (turn.region, state.ctx.region),
        (turn.property_type, state.ctx.property_type),
        (turn.analysis_type, state.ctx.analysis_type),
        (turn.target, state.ctx.target),
        (turn.period, state.ctx.period),
        (turn.measure, state.ctx.measure),
        (turn.gross_area, state.ctx.gross_area),
        (turn.land_area, state.ctx.land_area),
        (turn.building_age, state.ctx.building_age),
        (turn.road_width_label, state.ctx.road_width_label),
    )
    return any(new is not None and old is not None and new != old for new, old in pairs)


def _apply(state: Session, turn: Turn) -> Action | None:
    if not turn.accept_offer and _question_changed(state, turn):
        state.envelopes = []
        state.pending = []
        state.phase = "ready"
        state.calls = 0
    if turn.region is not None:
        state.ctx.region = turn.region
    if turn.property_type is not None:
        state.ctx.property_type = turn.property_type
    if turn.analysis_type is not None:
        state.ctx.analysis_type = turn.analysis_type
    if turn.period is not None:
        state.ctx.period = turn.period
    if turn.target is not None:
        state.ctx.target = turn.target
    if turn.measure is not None:
        state.ctx.measure = turn.measure
    if turn.gross_area is not None:
        state.ctx.gross_area = turn.gross_area
    if turn.land_area is not None:
        state.ctx.land_area = turn.land_area
    if turn.building_age is not None:
        state.ctx.building_age = turn.building_age
    if turn.road_width_label is not None:
        state.ctx.road_width_label = turn.road_width_label
    if turn.also_analysis_type and turn.also_fixture:
        state.queue.append(
            (
                turn.also_fixture,
                AnalysisContext(
                    region=turn.also_region,
                    property_type=turn.also_property_type,
                    analysis_type=turn.also_analysis_type,
                    target=turn.also_target,
                ),
            )
        )
    if not turn.accept_offer:
        return None
    if not state.pending:
        return Action(kind="refuse", message="제안 중인 대안이 없습니다.")
    if turn.offer_index < 0 or turn.offer_index >= len(state.pending):
        return Action(kind="refuse", message="고른 대안이 목록에 없습니다.")
    alt = state.pending[turn.offer_index]
    _bind_alternative(state, alt)
    return Action(kind="call", message="", tool_id=alt.id, args=dict(alt.args))


def _bind_alternative(state: Session, alt: Alternative) -> None:
    if alt.args.get("target"):
        state.ctx.target = str(alt.args["target"])
    if alt.args.get("region"):
        state.ctx.region = str(alt.args["region"])
    if alt.args.get("period"):
        state.ctx.period = str(alt.args["period"])
        state.envelopes = [
            env
            for env in state.envelopes
            if env.reason_code not in ("PERIOD_OUTSIDE", "PERIOD_UNAVAILABLE")
        ]
    state.pending = []
    state.phase = "ready"


def _explain(state: Session) -> list[Action]:
    if not state.segments:
        return [Action(kind="refuse", message="설명할 결과가 없습니다.")]
    message = "저장된 결과만 다시 읽습니다. 회귀를 다시 돌리지 않음.\n" + "\n".join(
        text for _, text in state.segments
    )
    if len(state.segments) > 1:
        message += "\n서로 다른 분석이라 한 숫자로 합치지 않습니다."
    return [Action(kind="report", message=message, verdict=None)]


def _drop(state: Session, property_type: str) -> list[Action]:
    kept = [item for item in state.segments if item[0] != property_type]
    state.segments = kept
    if not kept:
        return [Action(kind="report", message="남긴 결과가 없습니다.", verdict=None)]
    message = "\n".join(text for _, text in kept)
    if len(kept) > 1:
        message += "\n서로 다른 분석이라 한 숫자로 합치지 않습니다."
    return [Action(kind="report", message=message, verdict=None)]


def _finish_report(state: Session, action: Action) -> Action | None:
    state.segments.append((state.ctx.property_type or "", action.message))
    if state.queue:
        fixture, ctx = state.queue.pop(0)
        state.world_name = fixture
        state.ctx = ctx
        state.envelopes = []
        state.pending = []
        state.phase = "ready"
        return None
    if len(state.segments) > 1:
        action.message = (
            "\n".join(text for _, text in state.segments)
            + "\n서로 다른 분석이라 한 숫자로 합치지 않습니다."
        )
    return action


def _note_claim(state: Session, action: Action) -> Action:
    if state.claim != "appraisal" or action.kind not in ("report", "refuse"):
        return action
    note = "감정평가를 대신하지 않습니다."
    if note not in action.message:
        action.message = f"{action.message} {note}".strip()
    action.verdict = None
    return action


def _apply_fields(turn: Turn, source: LlmDraft | object) -> None:
    for name in ("region", "property_type", "analysis_type", "target", "period", "measure", "claim"):
        value = getattr(source, name, None)
        if getattr(turn, name) is None and value is not None:
            setattr(turn, name, value)


def _inherit_context(turn: Turn, state: Session) -> Action | None:
    if turn.analysis_type is None:
        turn.analysis_type = state.ctx.analysis_type
    if turn.property_type is None:
        turn.property_type = state.ctx.property_type
    if turn.region is None:
        turn.region = state.ctx.region
    if turn.period is None:
        turn.period = state.ctx.period
    if turn.measure is None:
        turn.measure = state.ctx.measure
    if turn.analysis_type is None:
        return Action(kind="refuse", message="이 문장에 해당하는 분석이 없습니다.")
    return None


def _analysis_fits(analysis: str | None, property_type: str | None) -> bool:
    if not analysis or not property_type:
        return False
    spec = get_spec(analysis)
    if spec is not None:
        return property_type in spec.property_types
    return analysis == "land_regression" and property_type == "land"


def _adopt_fitting_analysis(turn: Turn, named: str | None) -> None:
    if _analysis_fits(named, turn.property_type):
        turn.analysis_type = named


def _overlay_draft(turn: Turn, state: Session, draft: LlmDraft) -> Action | None:
    parsed = parse_sentence(turn.sentence or "")
    sentence_fits = not parsed.ambiguous_analysis and _analysis_fits(
        parsed.analysis_type, turn.property_type
    )
    if draft.unknown_analysis and not sentence_fits:
        return Action(kind="refuse", message="이 문장에 해당하는 분석이 없습니다.")
    if not draft.unknown_analysis:
        _apply_fields(turn, draft)
        _adopt_fitting_analysis(turn, draft.analysis_type)
    if turn.region is None and parsed.region is not None:
        turn.region = parsed.region
    if turn.target is None and not parsed.ambiguous_target and parsed.target is not None:
        turn.target = parsed.target
    if not parsed.ambiguous_analysis:
        _adopt_fitting_analysis(turn, parsed.analysis_type)
    return _inherit_context(turn, state)


def _overlay_sentence(turn: Turn, state: Session) -> Action | None:
    parsed = parse_sentence(turn.sentence or "")
    if turn.property_type is None and parsed.ambiguous_property:
        return Action(kind="refuse", message="유형이 둘입니다. 하나만 지정해 주세요.")
    if turn.analysis_type is None and parsed.ambiguous_analysis:
        return Action(kind="refuse", message="분석이 둘입니다. 하나만 지정해 주세요.")
    if turn.target is None and parsed.ambiguous_target:
        return Action(kind="refuse", message="대상이 둘입니다. 하나만 지정해 주세요.")
    for name in ("region", "property_type", "analysis_type", "target", "period", "measure", "claim"):
        if getattr(turn, name) is None and getattr(parsed, name) is not None:
            setattr(turn, name, getattr(parsed, name))
    if not parsed.ambiguous_analysis:
        _adopt_fitting_analysis(turn, parsed.analysis_type)
    return _inherit_context(turn, state)


def _choose_listed_tool(
    state: Session,
    alternatives: list[Alternative],
    chooser: ToolChooser,
) -> Alternative | None:
    allowed = {alt.id for alt in alternatives}
    try:
        facts = state.envelopes[-1].facts if state.envelopes else {}
        picked = chooser(alternatives, facts)
    except Exception:
        return None
    if picked not in allowed:
        return None
    return next(alt for alt in alternatives if alt.id == picked)


def _rewrite_report(state: Session, action: Action, writer: ReportWriter | None) -> Action:
    if writer is None or action.kind != "report":
        return action
    source = action.message
    try:
        prose = writer(source)
    except Exception:
        prose = None
    if prose and accept_report(source, prose):
        action.message = restore_required_clauses(source, prose)
        state.llm_mode = "used"
    note = "감정평가를 대신하지 않습니다."
    if state.claim == "appraisal" and note not in action.message:
        action.message = f"{action.message} {note}".strip()
    action.verdict = None
    return action


def run_turn(
    state: Session,
    turn: Turn,
    runner: ToolRunner | None = None,
    reader: ContextReader | None = None,
    writer: ReportWriter | None = None,
    chooser: ToolChooser | None = None,
) -> list[Action]:
    install_protocol_specs()
    state.llm_mode = "off"
    if turn.sentence:
        blocked: Action | None
        if reader is None:
            blocked = _overlay_sentence(turn, state)
        else:
            try:
                draft = reader(turn.sentence, state.ctx)
            except Exception:
                draft = None
            if draft is None:
                state.llm_mode = "fallback"
                blocked = _overlay_sentence(turn, state)
            else:
                state.llm_mode = "used"
                blocked = _overlay_draft(turn, state, draft)
        if blocked is not None:
            return [blocked]
    if (
        not turn.accept_offer
        and not turn.explain
        and not turn.drop_property_type
        and turn.region is None
        and (turn.screen_region or "").strip()
    ):
        turn.region = turn.screen_region.strip()
    if turn.claim:
        state.claim = turn.claim
    if turn.drop_property_type:
        return _drop(state, turn.drop_property_type)
    if turn.explain:
        return _explain(state)
    actions: list[Action] = []
    forced = _apply(state, turn)
    if forced is not None and forced.kind == "refuse":
        return [_note_claim(state, forced)]
    guard = 0
    while guard < MAX_CALLS + 1:
        guard += 1
        action = forced or decide(state)
        forced = None
        if action.kind == "offer" and chooser is not None and len(action.alternatives) > 1:
            picked = _choose_listed_tool(state, action.alternatives, chooser)
            if picked is not None:
                _bind_alternative(state, picked)
                state.llm_mode = "used"
                action = Action(kind="call", message="", tool_id=picked.id, args=dict(picked.args))
        if action.kind != "call":
            if action.kind == "offer":
                state.pending = list(action.alternatives)
                state.phase = "offered"
            if action.kind == "report":
                finished = _finish_report(state, action)
                if finished is None:
                    continue
                action = finished
            actions.append(_rewrite_report(state, _note_claim(state, action), writer))
            return actions
        if state.calls >= MAX_CALLS:
            actions.append(_note_claim(state, Action(kind="refuse", message="호출 상한에 닿았습니다.")))
            return actions
        if runner is None:
            env = run_registered_tool(action.tool_id or "", state.ctx, action.args, state.world_name)
        else:
            env = runner(action.tool_id or "", state.ctx, action.args)
        state.envelopes.append(env)
        state.calls += 1
        action.envelope = env
        actions.append(action)
    actions.append(_note_claim(state, Action(kind="refuse", message="호출 상한에 닿았습니다.")))
    return actions
