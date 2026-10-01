"""랩에서 프로토콜 한 턴을 돌린다. LLM은 맥락만 고르고, 화면 어시스턴트 세션은 쓰지 않는다."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ai2.llm import read_sentence, write_report, choose_alternative
from app.ai2.loop import Session, Turn, known_fixtures, new_session, run_turn

router = APIRouter(prefix="/lab/ai2", tags=["ai2"])

_SESSIONS: dict[str, Session] = {}


class TurnIn(BaseModel):
    session_id: str = "lab"
    fixture: str = "one_eligible"
    reset: bool = False
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
    continue_session: bool = False
    use_llm: bool = False
    gross_area: float | None = None
    land_area: float | None = None
    building_age: float | None = None
    road_width_label: str | None = None
    screen_region: str | None = None
    screen_target: str | None = None


class TurnOut(BaseModel):
    actions: list[dict]
    context: dict
    fixtures: list[str] = Field(default_factory=list)
    llm: str = "off"


@router.get("/fixtures")
def fixtures() -> dict:
    return {"fixtures": sorted(known_fixtures())}


@router.post("/turn", response_model=TurnOut)
def turn(body: TurnIn) -> TurnOut:
    if body.fixture not in known_fixtures():
        raise HTTPException(status_code=404, detail="없는 픽스처")
    follow_up = bool(
        body.drop_property_type or body.accept_offer or body.measure or body.explain or body.continue_session
    )
    if body.reset or body.session_id not in _SESSIONS:
        _SESSIONS[body.session_id] = new_session(body.fixture)
    elif not follow_up and _SESSIONS[body.session_id].world_name != body.fixture:
        _SESSIONS[body.session_id] = new_session(body.fixture)
    state = _SESSIONS[body.session_id]
    actions = run_turn(
        state,
        Turn(
            region=body.region,
            property_type=body.property_type,
            analysis_type=body.analysis_type,
            target=body.target,
            period=body.period,
            measure=body.measure,
            accept_offer=body.accept_offer,
            offer_index=body.offer_index,
            also_fixture=body.also_fixture,
            also_region=body.also_region,
            also_property_type=body.also_property_type,
            also_analysis_type=body.also_analysis_type,
            also_target=body.also_target,
            drop_property_type=body.drop_property_type,
            explain=body.explain,
            claimed_n=body.claimed_n,
            claim=body.claim,
            sentence=body.sentence,
            gross_area=body.gross_area,
            land_area=body.land_area,
            building_age=body.building_age,
            road_width_label=body.road_width_label,
            screen_region=body.screen_region,
            screen_target=body.screen_target,
        ),
        reader=read_sentence if body.use_llm else None,
        writer=write_report if body.use_llm else None,
        chooser=choose_alternative if body.use_llm else None,
    )
    return TurnOut(
        actions=[a.to_dict() for a in actions],
        context=state.ctx.to_dict(),
        fixtures=sorted(known_fixtures()),
        llm=state.llm_mode,
    )
