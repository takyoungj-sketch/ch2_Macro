"""AI2 프로토콜. 층별효용은 첫 픽스처이고, 행동 순서는 분석 종류에 묶이지 않는다."""

from app.ai2.catalog import AnalysisSpec, register
from app.ai2.floor_tools import install_floor_spec
from app.ai2.llm import LlmDraft
from app.ai2.loop import Session, Turn, new_session, run_turn
from app.ai2.types import AnalysisContext, ToolEnvelope
from app.collective.analysis_gates import MIN_COUNT_FLOOR_INDEX


def _kinds(actions) -> list[str]:
    return [a.kind for a in actions]


def _ids(actions) -> list[str]:
    return [a.tool_id for a in actions if a.kind == "call"]


def test_missing_target_asks_once():
    state = new_session("one_eligible")
    actions = run_turn(
        state,
        Turn(region="가경동", property_type="apartment", analysis_type="floor_utility"),
    )
    assert _kinds(actions) == ["ask"]
    assert "단지" in actions[0].message
    assert actions[0].tool_id is None


def test_named_complex_runs_index_then_insight():
    state = new_session("named_ok")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
        ),
    )
    assert _kinds(actions) == ["call", "call", "report"]
    assert _ids(actions) == ["floor_index", "insight_compare"]
    assert actions[-1].verdict is None
    assert actions[-1].comparable is False
    assert "채택하지 않습니다" in actions[-1].message
    assert actions[-1].message.count("112") == 1
    assert "108" in actions[-1].message


def test_region_chains_status_then_representative_then_offer():
    state = new_session("one_eligible")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="region",
        ),
    )
    assert _kinds(actions) == ["call", "call", "offer"]
    assert _ids(actions) == ["sample_status", "representative_candidates"]
    offer = actions[-1]
    assert offer.alternatives[0].id == "floor_index"
    assert offer.alternatives[0].args["target"] == "A아파트"
    assert str(MIN_COUNT_FLOOR_INDEX) in offer.message
    assert "62" in offer.message
    env = actions[0].envelope
    assert env is not None
    assert env.reason_code == "NO_REGION_LEVEL_INDEX"
    assert env.required_n == MIN_COUNT_FLOOR_INDEX


def test_accept_offer_runs_index_and_insight():
    state = new_session("one_eligible")
    run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="region",
        ),
    )
    actions = run_turn(state, Turn(accept_offer=True))
    assert _kinds(actions) == ["call", "call", "report"]
    assert _ids(actions) == ["floor_index", "insight_compare"]
    assert state.ctx.target == "A아파트"
    assert actions[-1].verdict is None
    assert actions[-1].comparable is False


def test_below_gate_does_not_invent_a_representative():
    state = new_session("below_gate")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="region",
        ),
    )
    assert _ids(actions) == ["sample_status"]
    assert actions[-1].kind == "offer"
    assert [a.id for a in actions[-1].alternatives] == ["expand_region"]
    assert "A아파트" not in actions[-1].message
    env = actions[0].envelope
    assert env is not None
    assert env.valid_n == 61
    assert env.required_n == MIN_COUNT_FLOOR_INDEX


def test_short_complex_refuses_with_counts():
    state = new_session("named_short")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="짧은단지",
        ),
    )
    assert _kinds(actions) == ["call", "refuse"]
    env = actions[0].envelope
    assert env is not None
    assert env.reason_code == "INSUFFICIENT_SAMPLE"
    assert env.valid_n == 8
    assert env.required_n == MIN_COUNT_FLOOR_INDEX
    assert "8" in actions[-1].message
    assert str(MIN_COUNT_FLOOR_INDEX) in actions[-1].message


def test_thin_floor_group_stays_blank():
    state = new_session("thin_group")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
        ),
    )
    assert actions[-1].kind == "report"
    assert "칸을 비움" in actions[-1].message
    floor = next(a.envelope for a in actions if a.tool_id == "floor_index")
    assert floor is not None
    assert floor.reason_code == "INSUFFICIENT_FLOOR_GROUP"
    assert floor.facts["blank_group"] == "최상층"
    assert floor.analysis_possible is True


def test_named_ineligible_is_not_replaced_by_selector():
    state = new_session("one_eligible")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="C아파트",
        ),
    )
    assert _ids(actions) == ["floor_index"]
    assert actions[-1].kind == "refuse"
    assert state.ctx.target == "C아파트"
    assert "A아파트" not in actions[-1].message


def test_unknown_analysis_refuses_without_a_call():
    state = new_session("named_ok")
    actions = run_turn(
        state,
        Turn(region="가경동", property_type="apartment", analysis_type="vacancy_rate"),
    )
    assert _kinds(actions) == ["refuse"]
    assert _ids(actions) == []


def test_other_analysis_type_uses_the_same_loop():
    install_floor_spec()
    register(
        AnalysisSpec(
            analysis_type="marker",
            property_types=frozenset({"land"}),
            needs_target=True,
            ask="범위를 고르세요",
            discovery_tool="marker_status",
            direct_tool="marker_run",
        )
    )
    state = Session(
        ctx=AnalysisContext(region="흥덕구", property_type="land", analysis_type="marker"),
        world_name="one_eligible",
    )

    def runner(tool_id: str, ctx: AnalysisContext, args: dict) -> ToolEnvelope:
        return ToolEnvelope(
            tool_id=tool_id,
            level="ok",
            analysis_possible=True,
            valid_n=3,
            required_n=1,
            period="2021-09~2026-08",
        )

    asked = run_turn(state, Turn(), runner=runner)
    assert _kinds(asked) == ["ask"]
    assert asked[0].message == "범위를 고르세요"
    followed = run_turn(state, Turn(target="region"), runner=runner)
    assert _kinds(followed) == ["call", "report"]
    assert _ids(followed) == ["marker_status"]
    assert followed[0].tool_id == "marker_status"
    assert "흥덕구" in followed[-1].message
    assert "유효표본 3건" in followed[-1].message
    assert "marker" not in followed[-1].message


def test_method_question_does_not_run_the_index():
    state = new_session("named_ok")
    actions = run_turn(
        state,
        Turn(region="가경동", property_type="apartment", analysis_type="floor_utility_method"),
    )
    assert _kinds(actions) == ["call", "report"]
    assert _ids(actions) == ["floor_formula"]
    assert "1층 = 100%" in actions[-1].message
    assert "회귀를 다시 돌리지 않음" in actions[-1].message
    assert "어느 결과를 채택하지 않습니다" not in actions[-1].message


def test_period_outside_ledger_is_not_offered():
    state = new_session("named_ok")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
            period="2010-01~2010-12",
        ),
    )
    assert _kinds(actions) == ["call", "refuse"]
    env = actions[0].envelope
    assert env is not None
    assert env.reason_code == "PERIOD_UNAVAILABLE"
    assert env.alternative_tools == []
    assert "2010" not in (env.period or "")


def test_accept_period_snap_reruns_the_index_once():
    state = new_session("period_snap")
    offered = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
            period="2010-01~2010-12",
        ),
    )
    assert _kinds(offered) == ["call", "offer"]
    blocked = offered[0].envelope
    assert blocked is not None
    assert blocked.reason_code == "PERIOD_OUTSIDE"
    assert [a.id for a in blocked.alternative_tools] == ["expand_period"]
    accepted = run_turn(state, Turn(accept_offer=True))
    assert _ids(accepted) == ["expand_period", "floor_index", "insight_compare"]
    assert accepted[-1].kind == "report"
    assert state.ctx.period == "2021-09~2026-08"
    assert "112" in accepted[-1].message
    assert "2010" not in accepted[-1].message
    assert state.calls == 4


def test_raw_rows_are_refused():
    state = new_session("named_ok")
    actions = run_turn(
        state,
        Turn(region="가경동", property_type="apartment", analysis_type="raw_rows"),
    )
    assert _kinds(actions) == ["refuse"]
    assert _ids(actions) == []


def test_accept_region_expand_does_not_rerun_the_same_sample():
    state = new_session("below_gate")
    run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="region",
        ),
    )
    actions = run_turn(state, Turn(accept_offer=True))
    assert _ids(actions) == ["expand_region"]
    assert actions[-1].kind == "refuse"
    assert actions[0].envelope is not None
    assert actions[0].envelope.reason_code == "NO_DATA_FOR_REGION"


def test_new_target_does_not_reuse_the_previous_refusal():
    state = new_session("one_eligible")
    refused = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="C아파트",
        ),
    )
    assert refused[-1].kind == "refuse"
    assert refused[0].envelope is not None
    assert refused[0].envelope.valid_n == 13
    switched = run_turn(state, Turn(target="A아파트"))
    assert _ids(switched) == ["floor_index", "insight_compare"]
    assert switched[-1].kind == "report"
    assert "120" in switched[-1].message
    assert "유효표본 13" not in switched[-1].message


def test_second_offer_runs_only_the_chosen_tool():
    state = new_session("two_alts")
    offered = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
            period="2010-01~2010-12",
        ),
    )
    assert offered[-1].kind == "offer"
    assert [a.id for a in offered[-1].alternatives] == ["expand_period", "expand_region"]
    chosen = run_turn(state, Turn(accept_offer=True, offer_index=1))
    assert _ids(chosen) == ["expand_region"]
    assert chosen[-1].kind == "refuse"
    assert chosen[0].envelope is not None
    assert chosen[0].envelope.reason_code == "NO_DATA_FOR_REGION"
    assert state.ctx.region == "흥덕구"
    assert state.ctx.period == "2010-01~2010-12"


def test_expanded_region_offers_the_eligible_complex():
    state = new_session("expand_hits")
    offered = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="region",
        ),
    )
    assert _ids(offered) == ["sample_status"]
    widened = run_turn(state, Turn(accept_offer=True))
    assert _ids(widened) == ["expand_region"]
    assert widened[-1].kind == "offer"
    assert "넓은단지" in widened[-1].message
    assert "sample_status" not in _ids(widened)
    done = run_turn(state, Turn(accept_offer=True))
    assert _ids(done) == ["floor_index", "insight_compare"]
    assert "105" in done[-1].message
    assert state.calls == 4


def test_land_regression_is_refused_without_a_call():
    state = new_session("twin_worse")
    actions = run_turn(
        state,
        Turn(region="흥덕구", property_type="land", analysis_type="land_regression"),
    )
    assert _kinds(actions) == ["refuse"]
    assert _ids(actions) == []
    assert actions[0].message == "토지 회귀는 현재 제공하지 않습니다."


def test_twin_not_adopted_is_not_the_conclusion():
    state = new_session("twin_worse")
    actions = run_turn(
        state,
        Turn(region="흥덕구", property_type="land", analysis_type="twin_region"),
    )
    assert _kinds(actions) == ["call", "report"]
    assert _ids(actions) == ["twin_status"]
    assert actions[0].envelope is not None
    assert actions[0].envelope.facts["twin_adopted"] is False
    assert "결론으로 쓰지 않음" in actions[-1].message


def test_twin_adopted_when_validation_is_better():
    state = new_session("twin_better")
    actions = run_turn(
        state,
        Turn(region="흥덕구", property_type="land", analysis_type="twin_region"),
    )
    assert actions[-1].kind == "report"
    assert "오창읍" in actions[-1].message
    assert "결론으로 쓰지 않음" not in actions[-1].message


def test_report_names_the_place_without_tool_ids():
    state = new_session("twin_worse")
    actions = run_turn(
        state,
        Turn(region="흥덕구", property_type="land", analysis_type="twin_region"),
    )
    text = actions[-1].message
    assert "지역은 흥덕구입니다." in text
    assert "대상 None" not in text
    assert "twin_status" not in text
    assert "twin_region" not in text
    assert "유형 land" not in text
    assert "결론으로 쓰지 않음" in text
    floor = new_session("named_ok")
    named = run_turn(
        floor,
        Turn(region="가경동", property_type="apartment", analysis_type="floor_utility", target="세원가경골"),
    )
    named_text = named[-1].message
    assert "대상은 세원가경골입니다." in named_text
    assert "floor_index" not in named_text
    assert "apartment" not in named_text


def test_built_predict_reports_center_and_interval():
    state = new_session("built_ok")
    actions = run_turn(
        state,
        Turn(region="가경동", property_type="built", analysis_type="built_predict"),
    )
    assert _kinds(actions) == ["call", "report"]
    text = actions[-1].message
    assert text.startswith("과거 거래에 맞춘 중심값과 예측구간입니다.")
    assert "1520" in text and "980" in text and "2100" in text
    assert "적정" not in text


def test_built_partial_names_reference_inputs():
    state = new_session("built_partial")
    actions = run_turn(
        state,
        Turn(region="가경동", property_type="built", analysis_type="built_predict"),
    )
    assert "연식" in actions[-1].message
    assert "도로폭" in actions[-1].message
    assert "기준값" in actions[-1].message


def test_built_short_sample_refuses():
    state = new_session("built_short")
    actions = run_turn(
        state,
        Turn(region="가경동", property_type="built", analysis_type="built_predict"),
    )
    assert _kinds(actions) == ["call", "refuse"]
    env = actions[0].envelope
    assert env is not None
    assert env.valid_n == 8
    assert env.required_n == 10
    assert "1520" not in actions[-1].message


def test_built_extrapolation_hides_the_center():
    state = new_session("built_extrap")
    actions = run_turn(
        state,
        Turn(region="가경동", property_type="built", analysis_type="built_predict"),
    )
    text = actions[-1].message
    assert "중심값 숨김" in text
    assert "1520" not in text
    assert "400" in text and "9000" in text
    assert "적정" not in text


def test_built_value_asks_total_or_unit_price():
    state = new_session("built_ok")
    asked = run_turn(
        state,
        Turn(region="가경동", property_type="built", analysis_type="built_value"),
    )
    assert _kinds(asked) == ["ask"]
    assert "㎡당" in asked[0].message
    answered = run_turn(state, Turn(measure="unit_price"))
    assert _kinds(answered) == ["call", "report"]
    assert "기준은 ㎡당입니다." in answered[-1].message
    assert "기준은 총액입니다." not in answered[-1].message
    assert "적정" not in answered[-1].message


def test_mixed_types_stay_separate_and_land_can_be_dropped():
    state = new_session("twin_worse")
    actions = run_turn(
        state,
        Turn(
            region="흥덕구",
            property_type="land",
            analysis_type="twin_region",
            also_fixture="named_ok",
            also_region="가경동",
            also_property_type="apartment",
            also_analysis_type="floor_utility_method",
        ),
    )
    assert _ids(actions) == ["twin_status", "floor_formula"]
    assert actions[-1].kind == "report"
    assert "한 숫자로 합치지 않습니다" in actions[-1].message
    assert "결론으로 쓰지 않음" in actions[-1].message
    assert "1층 = 100%" in actions[-1].message
    calls = state.calls
    dropped = run_turn(state, Turn(drop_property_type="land"))
    assert _kinds(dropped) == ["report"]
    assert state.calls == calls
    assert "1층 = 100%" in dropped[0].message
    assert "결론으로 쓰지 않음" not in dropped[0].message


def test_explain_restates_the_stored_report_without_a_call():
    state = new_session("named_ok")
    run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
        ),
    )
    calls = state.calls
    actions = run_turn(state, Turn(explain=True))
    assert _kinds(actions) == ["report"]
    assert _ids(actions) == []
    assert state.calls == calls
    assert "저장된 결과만 다시 읽습니다" in actions[0].message
    assert "회귀를 다시 돌리지 않음" in actions[0].message
    assert "112" in actions[0].message
    empty = new_session("named_ok")
    missing = run_turn(empty, Turn(explain=True))
    assert _kinds(missing) == ["refuse"]
    assert empty.calls == 0
    assert missing[0].message == "설명할 결과가 없습니다."


def test_claimed_sample_size_does_not_override_the_envelope():
    state = new_session("named_short")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="짧은단지",
            claimed_n=200,
        ),
    )
    assert _kinds(actions) == ["call", "refuse"]
    env = actions[0].envelope
    assert env is not None
    assert env.valid_n == 8
    assert "200" not in actions[-1].message
    assert "8" in actions[-1].message
    assert "200" not in str(env.facts)


def test_appraisal_claim_keeps_the_interval_and_refuses_a_valuation():
    state = new_session("built_ok")
    actions = run_turn(
        state,
        Turn(region="가경동", property_type="built", analysis_type="built_predict", claim="appraisal"),
    )
    assert actions[-1].kind == "report"
    assert actions[-1].verdict is None
    assert "1520" in actions[-1].message
    assert "980" in actions[-1].message
    assert "2100" in actions[-1].message
    assert "감정평가를 대신하지 않습니다." in actions[-1].message
    assert "적정" not in actions[-1].message


def test_screen_region_fills_only_when_the_sentence_has_none():
    state = new_session("one_eligible")
    asked = run_turn(state, Turn(sentence="아파트 층별효용", screen_region="가경동"))
    assert _kinds(asked) == ["ask"]
    assert state.ctx.region == "가경동"
    named = new_session("one_eligible")
    run_turn(named, Turn(sentence="오창읍 아파트 층별효용", screen_region="가경동"))
    assert named.ctx.region == "오창읍"
    explicit = new_session("one_eligible")
    run_turn(
        explicit,
        Turn(region="가경동", sentence="오창읍 아파트 층별효용", screen_region="흥덕구"),
    )
    assert explicit.ctx.region == "가경동"


def test_sentence_without_a_target_asks():
    state = new_session("one_eligible")
    actions = run_turn(state, Turn(sentence="가경동 아파트 층별효용"))
    assert _kinds(actions) == ["ask"]
    assert _ids(actions) == []
    assert state.ctx.region == "가경동"
    assert state.ctx.property_type == "apartment"
    assert state.ctx.analysis_type == "floor_utility"
    assert state.ctx.target is None


def test_sentence_names_the_complex_and_keeps_explicit_analysis():
    state = new_session("named_ok")
    actions = run_turn(state, Turn(sentence="가경동 세원가경골 아파트 층별효용"))
    assert _ids(actions) == ["floor_index", "insight_compare"]
    assert "112" in actions[-1].message
    held = new_session("named_ok")
    formula = run_turn(
        held,
        Turn(
            property_type="apartment",
            analysis_type="floor_utility",
            sentence="가경동 아파트 산식",
        ),
    )
    assert held.ctx.analysis_type == "floor_utility_method"
    assert _ids(formula) == ["floor_formula"]


def test_sentence_analysis_stays_inside_the_open_property():
    shop = new_session("named_ok")
    asked = run_turn(
        shop,
        Turn(
            property_type="collective_shop",
            analysis_type="shop_floor",
            sentence="가경동 층별효용",
        ),
    )
    assert shop.ctx.analysis_type == "shop_floor"
    assert asked[-1].kind == "ask"
    assert "도로" in asked[-1].message
    land = new_session("twin_worse")
    refused = run_turn(
        land,
        Turn(
            region="흥덕구",
            property_type="land",
            analysis_type="twin_region",
            sentence="회귀",
        ),
    )
    assert land.ctx.analysis_type == "land_regression"
    assert refused[-1].message == "토지 회귀는 현재 제공하지 않습니다."
    kept = new_session("twin_worse")
    run_turn(
        kept,
        Turn(region="흥덕구", property_type="land", analysis_type="twin_region", sentence="알려줘"),
    )
    assert kept.ctx.analysis_type == "twin_region"


def test_model_analysis_replaces_the_default_only_when_it_fits():
    state = new_session("named_ok")
    actions = run_turn(
        state,
        Turn(property_type="apartment", analysis_type="floor_utility", sentence="산식"),
        reader=lambda _sentence, _ctx: LlmDraft(
            analysis_type="floor_utility_method",
            property_type="apartment",
        ),
    )
    assert state.ctx.analysis_type == "floor_utility_method"
    assert _ids(actions) == ["floor_formula"]
    shop = new_session("named_ok")
    run_turn(
        shop,
        Turn(property_type="collective_shop", analysis_type="shop_floor", sentence="층별효용"),
        reader=lambda _sentence, _ctx: LlmDraft(
            analysis_type="floor_utility",
            property_type="apartment",
        ),
    )
    assert shop.ctx.analysis_type == "shop_floor"


def test_unknown_sentence_refuses_without_a_call():
    state = new_session("named_ok")
    actions = run_turn(state, Turn(sentence="가경동 공실률 알려줘"))
    assert _kinds(actions) == ["refuse"]
    assert _ids(actions) == []
    assert actions[0].message == "이 문장에 해당하는 분석이 없습니다."
    assert state.calls == 0


def test_two_targets_in_a_sentence_are_not_guessed():
    state = new_session("named_ok")
    actions = run_turn(state, Turn(sentence="가경동 세원가경골 아이파크 아파트 층별효용"))
    assert _kinds(actions) == ["refuse"]
    assert _ids(actions) == []
    assert actions[0].message == "대상이 둘입니다. 하나만 지정해 주세요."


def test_sentence_land_regression_uses_the_catalog_refusal():
    state = new_session("twin_worse")
    actions = run_turn(state, Turn(sentence="흥덕구 토지 회귀"))
    assert _kinds(actions) == ["refuse"]
    assert _ids(actions) == []
    assert actions[0].message == "토지 회귀는 현재 제공하지 않습니다."


def test_sentence_appraisal_keeps_the_interval():
    state = new_session("built_ok")
    actions = run_turn(state, Turn(sentence="가경동 복합 예측 적정가"))
    assert actions[-1].kind == "report"
    assert "1520" in actions[-1].message
    assert "감정평가를 대신하지 않습니다." in actions[-1].message
    assert "적정" not in actions[-1].message


def test_short_reply_fills_the_missing_target():
    state = new_session("named_ok")
    asked = run_turn(state, Turn(sentence="가경동 아파트 층별효용"))
    assert _kinds(asked) == ["ask"]
    answered = run_turn(state, Turn(sentence="세원가경골"))
    assert _ids(answered) == ["floor_index", "insight_compare"]
    assert "112" in answered[-1].message
    fresh = new_session("named_ok")
    missing = run_turn(fresh, Turn(sentence="세원가경골"))
    assert _kinds(missing) == ["refuse"]
    assert fresh.calls == 0


def test_short_reply_can_choose_the_whole_region():
    state = new_session("one_eligible")
    run_turn(state, Turn(sentence="가경동 아파트 층별효용"))
    answered = run_turn(state, Turn(sentence="지역 전체"))
    assert _ids(answered) == ["sample_status", "representative_candidates"]
    assert answered[-1].kind == "offer"
    assert "A아파트" in answered[-1].message


def test_short_reply_sets_unit_price_after_the_measure_question():
    state = new_session("built_ok")
    asked = run_turn(state, Turn(sentence="가경동 복합 가치"))
    assert _kinds(asked) == ["ask"]
    assert "㎡당" in asked[0].message
    answered = run_turn(state, Turn(sentence="㎡당"))
    assert answered[-1].kind == "report"
    assert "기준은 ㎡당입니다." in answered[-1].message
    assert "1520" in answered[-1].message
    bare = new_session("built_ok")
    refused = run_turn(bare, Turn(sentence="㎡당"))
    assert _kinds(refused) == ["refuse"]
    assert bare.calls == 0


def test_sentence_property_mismatch_refuses_without_a_call():
    state = new_session("named_ok")
    actions = run_turn(state, Turn(sentence="가경동 토지 층별효용"))
    assert _kinds(actions) == ["refuse"]
    assert _ids(actions) == []
    assert actions[0].message == "이 분석은 제공하지 않습니다."


def test_continue_sentence_keeps_the_session_if_the_form_fixture_differs():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    sid = "ai2-sentence-keep"
    first = client.post(
        "/api/lab/ai2/turn",
        json={
            "session_id": sid,
            "fixture": "named_ok",
            "reset": True,
            "sentence": "가경동 아파트 층별효용",
        },
    )
    assert first.status_code == 200
    assert first.json()["actions"][0]["kind"] == "ask"
    second = client.post(
        "/api/lab/ai2/turn",
        json={
            "session_id": sid,
            "fixture": "one_eligible",
            "reset": False,
            "continue_session": True,
            "sentence": "세원가경골",
        },
    )
    assert second.status_code == 200
    assert [a["tool_id"] for a in second.json()["actions"] if a["kind"] == "call"] == [
        "floor_index",
        "insight_compare",
    ]
    assert "112" in second.json()["actions"][-1]["message"]


def test_model_context_runs_the_index_without_a_keyword():
    state = new_session("named_ok")

    def reader(sentence: str, ctx):
        assert "층수" in sentence
        return LlmDraft(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
        )

    actions = run_turn(state, Turn(sentence="층수가 가격에 어떤 영향인가"), reader=reader)
    assert state.llm_mode == "used"
    assert _ids(actions) == ["floor_index", "insight_compare"]
    assert "112" in actions[-1].message
    plain = new_session("named_ok")
    refused = run_turn(plain, Turn(sentence="층수가 가격에 어떤 영향인가"))
    assert _kinds(refused) == ["refuse"]
    assert plain.llm_mode == "off"


def test_model_cannot_supply_a_sample_size_or_an_unknown_analysis():
    from app.ai2.llm import draft_from_model_json

    dropped = draft_from_model_json(
        {
            "analysis_type": "floor_utility",
            "property_type": "apartment",
            "region": "가경동",
            "target": "짧은단지",
            "valid_n": 200,
            "y_hat": 999,
        }
    )
    assert dropped is not None
    assert dropped.target == "짧은단지"
    assert not hasattr(dropped, "valid_n")
    state = new_session("named_short")
    actions = run_turn(state, Turn(sentence="충분하다"), reader=lambda _sentence, _ctx: dropped)
    assert actions[0].envelope is not None
    assert actions[0].envelope.valid_n == 8
    assert "200" not in actions[-1].message
    unknown = draft_from_model_json({"analysis_type": "vacancy_rate"})
    assert unknown is not None and unknown.unknown_analysis
    refused = run_turn(new_session("named_ok"), Turn(sentence="공실"), reader=lambda _s, _c: unknown)
    assert _kinds(refused) == ["refuse"]
    assert _ids(refused) == []


def test_model_failure_falls_back_to_the_keyword_parser():
    state = new_session("one_eligible")
    actions = run_turn(
        state,
        Turn(sentence="가경동 아파트 층별효용"),
        reader=lambda _sentence, _ctx: None,
    )
    assert state.llm_mode == "fallback"
    assert _kinds(actions) == ["ask"]


def test_use_llm_flag_uses_the_reader(monkeypatch):
    from fastapi.testclient import TestClient

    from app.ai2.llm import LlmDraft as Draft
    from app.main import app

    def fake(sentence: str, ctx):
        return Draft(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
        )

    monkeypatch.setattr("app.ai2.router.read_sentence", fake)
    monkeypatch.setattr("app.ai2.router.write_report", lambda _source: None)
    monkeypatch.setattr("app.ai2.router.choose_alternative", lambda _alts, _facts: None)
    client = TestClient(app)
    res = client.post(
        "/api/lab/ai2/turn",
        json={
            "session_id": "ai2-llm-flag",
            "fixture": "named_ok",
            "reset": True,
            "use_llm": True,
            "sentence": "층수와 가격",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["llm"] == "used"
    assert "112" in body["actions"][-1]["message"]


def test_report_prose_keeps_only_envelope_numbers():
    from app.ai2.llm import accept_report

    state = new_session("named_ok")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
        ),
        writer=lambda _source: "세원가경골의 층 지수는 112입니다. Insight 08은 108이라 어느 결과를 채택하지 않습니다.",
    )
    assert state.llm_mode == "used"
    assert actions[-1].message.startswith("세원가경골의 층 지수")
    assert "112" in actions[-1].message
    kept = new_session("named_ok")
    original = run_turn(
        kept,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
        ),
        writer=lambda _source: "지수는 9999입니다. 적정합니다.",
    )
    assert "9999" not in original[-1].message
    assert "적정" not in original[-1].message
    assert "112" in original[-1].message
    assert kept.llm_mode == "off"
    assert accept_report("지수 112.0", "지수는 112입니다.")
    assert not accept_report("지수 112.0", "지수는 113입니다.")
    priced = new_session("built_ok")
    priced.claim = "appraisal"
    answered = run_turn(
        priced,
        Turn(region="가경동", property_type="built", analysis_type="built_predict", claim="appraisal"),
        writer=lambda _source: "과거 거래의 중심값은 1520이고 예측구간은 980에서 2100입니다.",
    )
    assert "1520" in answered[-1].message
    assert "감정평가를 대신하지 않습니다." in answered[-1].message
    assert "적정" not in answered[-1].message
    twin = new_session("twin_worse")
    rewritten = run_turn(
        twin,
        Turn(region="흥덕구", property_type="land", analysis_type="twin_region"),
        writer=lambda _source: "흥덕구의 구조 이웃을 적었습니다.",
    )
    assert "쌍둥이는 결론으로 쓰지 않음" in rewritten[-1].message
    assert twin.llm_mode == "used"
    compared = new_session("named_ok")
    compared_actions = run_turn(
        compared,
        Turn(region="가경동", property_type="apartment", analysis_type="floor_utility", target="세원가경골"),
        writer=lambda _source: "세원가경골의 층 지수는 112입니다. Insight 08은 108입니다.",
    )
    assert "어느 결과를 채택하지 않습니다" in compared_actions[-1].message
    assert "112" in compared_actions[-1].message
    assert compared.llm_mode == "used"


def test_model_picks_one_listed_tool_and_rejects_any_other():
    state = new_session("two_alts")

    def pick_region(_alts, _facts):
        return "expand_region"

    chosen = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
            period="2010-01~2010-12",
        ),
        chooser=pick_region,
    )
    assert "expand_period" not in _ids(chosen)
    assert "expand_region" in _ids(chosen)
    assert chosen[-1].kind == "refuse"
    assert chosen[-1].envelope is None or chosen[0].envelope is not None
    refused = next(a for a in chosen if a.envelope and a.envelope.reason_code == "NO_DATA_FOR_REGION")
    assert refused.tool_id == "expand_region"
    held = new_session("two_alts")
    offered = run_turn(
        held,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
            period="2010-01~2010-12",
        ),
        chooser=lambda _alts, _facts: "raw_rows",
    )
    assert offered[-1].kind == "offer"
    assert [a.id for a in offered[-1].alternatives] == ["expand_period", "expand_region"]
    assert "raw_rows" not in _ids(offered)
    quiet = new_session("one_eligible")

    def must_not_run(_alts, _facts):
        raise AssertionError("단일 대안은 모델이 고르지 않습니다")

    single = run_turn(
        quiet,
        Turn(region="가경동", property_type="apartment", analysis_type="floor_utility", target="region"),
        chooser=must_not_run,
    )
    assert single[-1].kind == "offer"
    assert len(single[-1].alternatives) == 1


def test_follow_up_explain_keeps_the_session_if_the_form_fixture_differs():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    sid = "ai2-explain-keep"
    first = client.post(
        "/api/lab/ai2/turn",
        json={
            "session_id": sid,
            "fixture": "named_ok",
            "reset": True,
            "region": "가경동",
            "property_type": "apartment",
            "analysis_type": "floor_utility",
            "target": "세원가경골",
        },
    )
    assert first.status_code == 200
    second = client.post(
        "/api/lab/ai2/turn",
        json={
            "session_id": sid,
            "fixture": "one_eligible",
            "reset": False,
            "explain": True,
        },
    )
    assert second.status_code == 200
    text = second.json()["actions"][0]["message"]
    assert second.json()["actions"][0]["kind"] == "report"
    assert "112" in text
    assert "저장된 결과만 다시 읽습니다" in text


def test_follow_up_drop_keeps_the_session_if_the_form_fixture_differs():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    sid = "ai2-drop-keep"
    first = client.post(
        "/api/lab/ai2/turn",
        json={
            "session_id": sid,
            "fixture": "twin_worse",
            "reset": True,
            "region": "흥덕구",
            "property_type": "land",
            "analysis_type": "twin_region",
            "also_fixture": "named_ok",
            "also_region": "가경동",
            "also_property_type": "apartment",
            "also_analysis_type": "floor_utility_method",
        },
    )
    assert first.status_code == 200
    second = client.post(
        "/api/lab/ai2/turn",
        json={
            "session_id": sid,
            "fixture": "one_eligible",
            "reset": False,
            "drop_property_type": "land",
        },
    )
    assert second.status_code == 200
    text = second.json()["actions"][0]["message"]
    assert "1층 = 100%" in text
    assert "결론으로 쓰지 않음" not in text


def test_live_twin_names_a_neighbor_and_does_not_adopt_it(monkeypatch):
    monkeypatch.setattr(
        "app.ai2.live_cases.fetch_land_twin",
        lambda region: {"twin_region": "오창읍", "anchor_n": 40, "period": "2021-09-01~2026-08-31"}
        if region == "흥덕구"
        else {"error": "NO_MATCH"},
    )
    state = new_session("live_twin")
    actions = run_turn(
        state,
        Turn(region="흥덕구", property_type="land", analysis_type="twin_region"),
    )
    report = actions[-1]
    assert report.kind == "report"
    assert actions[0].envelope is not None
    assert actions[0].envelope.facts["twin_adopted"] is False
    assert "오창읍" in report.message
    assert "결론으로 쓰지 않음" in report.message
    assert "cv_mape" not in repr(actions[0].envelope.facts)


def test_live_twin_without_a_database_does_not_invent_a_region(monkeypatch):
    monkeypatch.setattr("app.ai2.live_cases.fetch_land_twin", lambda _region: None)
    state = new_session("live_twin")
    actions = run_turn(
        state,
        Turn(region="흥덕구", property_type="land", analysis_type="twin_region"),
    )
    assert actions[-1].kind == "refuse"
    assert "자료를 불러오지 못했습니다." in actions[-1].message
    assert "DATABASE_UNAVAILABLE" not in actions[-1].message
    assert "오창읍" not in actions[-1].message


def test_live_built_uses_the_engine_interval_and_states_total_price(monkeypatch):
    seen = {}

    def _predict(ctx):
        seen["area"] = ctx.gross_area
        return {
            "n": 40,
            "y_hat": 1520.0,
            "pi_lower": 980.0,
            "pi_upper": 2100.0,
            "y_hat_suppressed": False,
            "price_base_year": None,
            "reference_inputs": ["road_width"],
        }

    monkeypatch.setattr("app.ai2.live_cases.fetch_built_predict", _predict)
    state = new_session("live_built")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="built",
            analysis_type="built_predict",
            gross_area=200,
            land_area=150,
            building_age=20,
        ),
    )
    report = actions[-1]
    assert seen["area"] == 200
    assert report.kind == "report"
    assert "1520" in report.message
    assert "980" in report.message
    assert "2100" in report.message
    assert "기준은 총액입니다." in report.message
    assert "적정" not in report.message
    assert report.verdict is None


def test_live_built_hides_the_center_when_the_engine_suppresses_it(monkeypatch):
    monkeypatch.setattr(
        "app.ai2.live_cases.fetch_built_predict",
        lambda _ctx: {
            "n": 40,
            "y_hat": 1520.0,
            "pi_lower": 400.0,
            "pi_upper": 9000.0,
            "y_hat_suppressed": True,
            "price_base_year": None,
            "reference_inputs": [],
        },
    )
    state = new_session("live_built")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="built",
            analysis_type="built_predict",
            gross_area=200,
            land_area=150,
            building_age=20,
        ),
    )
    text = actions[-1].message
    assert "중심값 숨김" in text
    assert "400" in text
    assert "9000" in text
    assert "1520" not in text


def test_live_built_short_sample_and_missing_inputs_do_not_call_the_engine(monkeypatch):
    called = {"n": 0}

    def _predict(_ctx):
        called["n"] += 1
        return {"error": "INSUFFICIENT_SAMPLE", "n": 8}

    monkeypatch.setattr("app.ai2.live_cases.fetch_built_predict", _predict)
    missing = new_session("live_built")
    refused = run_turn(
        missing,
        Turn(region="가경동", property_type="built", analysis_type="built_predict"),
    )
    assert called["n"] == 0
    assert "필요한 값이 빠졌습니다." in refused[-1].message
    assert "연면적" in refused[-1].message
    assert "MISSING_INPUTS" not in refused[-1].message
    short = new_session("live_built")
    actions = run_turn(
        short,
        Turn(
            region="가경동",
            property_type="built",
            analysis_type="built_predict",
            gross_area=200,
            land_area=150,
            building_age=20,
        ),
    )
    assert called["n"] == 1
    assert "표본이 최소 건수보다 적습니다." in actions[-1].message
    assert "INSUFFICIENT_SAMPLE" not in actions[-1].message
    assert "1520" not in actions[-1].message


def test_live_built_unit_price_is_not_derived(monkeypatch):
    called = {"n": 0}

    def _predict(_ctx):
        called["n"] += 1
        return {"n": 40, "y_hat": 1, "pi_lower": 1, "pi_upper": 2, "y_hat_suppressed": False}

    monkeypatch.setattr("app.ai2.live_cases.fetch_built_predict", _predict)
    state = new_session("live_built")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="built",
            analysis_type="built_value",
            measure="unit_price",
            gross_area=200,
            land_area=150,
            building_age=20,
        ),
    )
    assert called["n"] == 0
    assert actions[-1].kind == "refuse"
    assert "㎡당 가격은 이 분석에서 제공하지 않습니다." in actions[-1].message
    assert "MEASURE_UNSUPPORTED" not in actions[-1].message


def _patch_live(monkeypatch, rows, index=None):
    monkeypatch.setattr("app.ai2.live_floor.fetch_counts", lambda region: rows if region == "가경동" else [])
    seen = {}

    def _index(key):
        seen["key"] = key
        return index

    monkeypatch.setattr("app.ai2.live_floor.fetch_floor_index", _index)
    return seen


def test_live_region_offers_only_a_complex_over_the_gate(monkeypatch):
    seen = _patch_live(
        monkeypatch,
        [("세원가경골", "k-secret", 80), ("짧은단지", "k-short", 27)],
        {
            "n": 80,
            "cells": [
                {"label": "1층", "count": 20, "index": 100.0, "mean_unit_price": 999},
                {"label": "최상층", "count": 10, "index": 112.0, "mean_unit_price": 1200},
            ],
        },
    )
    state = new_session("live")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="region",
        ),
    )
    assert _ids(actions) == ["sample_status", "representative_candidates"]
    assert actions[-1].kind == "offer"
    assert "세원가경골" in actions[-1].message
    assert "짧은단지" not in actions[-1].message
    blob = repr([env.facts for env in state.envelopes])
    assert "unit_price" not in blob
    assert "k-secret" not in blob
    assert "k-secret" not in actions[-1].message
    accepted = run_turn(state, Turn(accept_offer=True))
    assert seen["key"] == "k-secret"
    report = accepted[-1]
    assert report.kind == "report"
    assert "112" in report.message
    assert "108" in report.message
    assert "999" not in report.message
    assert "1200" not in report.message
    assert report.verdict is None
    assert report.comparable is False


def test_live_short_complex_does_not_run_the_regression(monkeypatch):
    seen = _patch_live(monkeypatch, [("짧은단지", "k-short", 27)])
    state = new_session("live")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="짧은단지",
        ),
    )
    assert actions[-1].kind == "refuse"
    assert "표본이 최소 건수보다 적습니다." in actions[-1].message
    assert "INSUFFICIENT_SAMPLE" not in actions[-1].message
    assert "key" not in seen
    assert MIN_COUNT_FLOOR_INDEX == 50


def test_live_without_a_database_does_not_invent_an_index(monkeypatch):
    monkeypatch.setattr("app.ai2.live_floor.fetch_counts", lambda _region: None)
    state = new_session("live")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="region",
        ),
    )
    assert actions[-1].kind == "refuse"
    assert "자료를 불러오지 못했습니다." in actions[-1].message
    assert "DATABASE_UNAVAILABLE" not in actions[-1].message
    assert "지수" not in actions[-1].message


def test_live_period_outside_the_window_does_not_query(monkeypatch):
    called = {"n": 0}

    def _counts(_region):
        called["n"] += 1
        return []

    monkeypatch.setattr("app.ai2.live_floor.fetch_counts", _counts)
    state = new_session("live")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="세원가경골",
            period="2010-01~2010-12",
        ),
    )
    assert called["n"] == 0
    assert actions[-1].kind == "refuse"
    assert "요청한 기간의 자료는 제공하지 않습니다." in actions[-1].message
    assert "PERIOD_UNAVAILABLE" not in actions[-1].message


def test_live_ambiguous_name_is_not_picked(monkeypatch):
    _patch_live(
        monkeypatch,
        [("세원가경골", "k1", 80), ("가경골", "k2", 60)],
    )
    state = new_session("live")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="apartment",
            analysis_type="floor_utility",
            target="가경골",
        ),
    )
    assert actions[-1].kind == "refuse"
    assert "이름이 둘 이상입니다." in actions[-1].message
    assert "AMBIGUOUS_TARGET" not in actions[-1].message


def test_live_shop_offers_a_road_and_does_not_compare_with_insight(monkeypatch):
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_shop_counts",
        lambda _region: [("좁은길", "secret-key", 12), ("넓은길", "road-ok", 80)],
    )
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_shop_index",
        lambda _key: {
            "n": 80,
            "cells": [
                {"label": "1층", "count": 40, "index": 100.0},
                {"label": "초고층", "count": 8, "index": 90.0},
            ],
        },
    )
    state = new_session("live_shop")
    offered = run_turn(
        state,
        Turn(region="가경동", property_type="collective_shop", analysis_type="shop_floor", target="region"),
    )
    assert offered[-1].kind == "offer"
    assert "넓은길" in offered[-1].message
    assert "도로" in offered[-1].message
    assert "secret-key" not in offered[-1].message
    indexed = new_session("live_shop")
    report = run_turn(
        indexed,
        Turn(region="가경동", property_type="collective_shop", analysis_type="shop_floor", target="넓은길"),
    )
    assert report[-1].kind == "report"
    assert "90" in report[-1].message
    assert "화면 100은 1층입니다." in report[-1].message
    assert "어느 결과를 채택하지 않습니다" not in report[-1].message
    assert "Insight" not in report[-1].message


def test_live_shop_short_road_does_not_run_the_index(monkeypatch):
    monkeypatch.setattr("app.ai2.live_domains.fetch_shop_counts", lambda _region: [("짧은길", "k", 12)])

    def boom(_key):
        raise AssertionError("index")

    monkeypatch.setattr("app.ai2.live_domains.fetch_shop_index", boom)
    state = new_session("live_shop")
    actions = run_turn(
        state,
        Turn(region="가경동", property_type="collective_shop", analysis_type="shop_floor", target="region"),
    )
    assert actions[-1].kind == "refuse"
    assert "이 지역 전체의 층별 지수는 없습니다." in actions[-1].message
    assert "NO_REGION_LEVEL_INDEX" not in actions[-1].message


def test_factory_sentence_uses_the_factory_road_index(monkeypatch):
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_shop_counts",
        lambda _region: (_ for _ in ()).throw(AssertionError("shop")),
    )
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_factory_counts",
        lambda _region: [("좁은공장", "secret", 12), ("공장길", "road-ok", 80)],
    )
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_factory_index",
        lambda _key: {
            "n": 80,
            "cells": [
                {"label": "1층", "count": 40, "index": 100.0},
                {"label": "2층", "count": 8, "index": 70.0},
                {"label": "3층 이상", "count": 9, "index": 88.0},
            ],
        },
    )
    state = new_session("live_shop")
    offered = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="collective_shop",
            analysis_type="shop_floor",
            target="region",
            sentence="공장",
        ),
    )
    assert state.ctx.analysis_type == "factory_floor"
    assert offered[-1].kind == "offer"
    assert "공장길" in offered[-1].message
    assert "도로" in offered[-1].message
    assert "좁은공장" not in offered[-1].message
    assert "secret" not in offered[-1].message
    indexed = new_session("live_shop")
    report = run_turn(
        indexed,
        Turn(
            region="가경동",
            property_type="collective_shop",
            analysis_type="shop_floor",
            target="공장길",
            sentence="공장",
        ),
    )
    assert indexed.ctx.analysis_type == "factory_floor"
    assert report[-1].kind == "report"
    assert "88" in report[-1].message
    assert "70" not in report[-1].message
    assert "공장·창고 층은 지하·1·2·3층 이상입니다." in report[-1].message
    assert "화면 100은 1층입니다." in report[-1].message
    assert "어느 결과를 채택하지 않습니다" not in report[-1].message
    assert "Insight" not in report[-1].message
    accepted = run_turn(state, Turn(accept_offer=True))
    assert accepted[-1].kind == "report"
    assert accepted[-1].message.count("80") == 1
    assert "92" not in accepted[-1].message
    assert "88" in accepted[-1].message
    short = new_session("live_shop")
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_factory_counts",
        lambda _region: [("짧은공장", "k", 12)],
    )

    def boom(_key):
        raise AssertionError("index")

    monkeypatch.setattr("app.ai2.live_domains.fetch_factory_index", boom)
    refused = run_turn(
        short,
        Turn(
            region="가경동",
            property_type="collective_shop",
            analysis_type="shop_floor",
            target="region",
            sentence="공장 전체",
        ),
    )
    assert refused[-1].kind == "refuse"
    assert "이 지역 전체의 층별 지수는 없습니다." in refused[-1].message


def test_shop_sentence_does_not_switch_to_the_factory(monkeypatch):
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_factory_counts",
        lambda _region: (_ for _ in ()).throw(AssertionError("factory")),
    )
    monkeypatch.setattr("app.ai2.live_domains.fetch_shop_counts", lambda _region: [])
    state = new_session("live_shop")
    actions = run_turn(
        state,
        Turn(
            region="가경동",
            property_type="collective_shop",
            analysis_type="shop_floor",
            target="region",
            sentence="상가 층별효용",
        ),
    )
    assert state.ctx.analysis_type == "shop_floor"
    assert actions[-1].kind == "refuse"


def test_model_factory_sentence_overrides_a_shop_guess(monkeypatch):
    monkeypatch.setattr("app.ai2.live_domains.fetch_shop_counts", lambda _region: [])
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_factory_counts",
        lambda _region: [("공장길", "road-ok", 80)],
    )
    state = new_session("live_shop")
    actions = run_turn(
        state,
        Turn(
            property_type="collective_shop",
            analysis_type="shop_floor",
            sentence="가경동 공장 전체",
        ),
        reader=lambda _sentence, _ctx: LlmDraft(analysis_type="floor_utility", property_type="apartment"),
    )
    assert state.ctx.analysis_type == "factory_floor"
    assert actions[-1].kind == "offer"
    assert "공장길" in actions[-1].message


def test_rent_label_uses_the_published_sigungu_inside_a_gu_name():
    from app.ai2.live_domains import _pick_label

    assert _pick_label(["청주시", "공주시"], "청주시 흥덕구") == ["청주시"]
    assert _pick_label(["청주시", "공주시"], "공주시") == ["공주시"]


def test_live_rent_reports_only_the_closed_rate(monkeypatch):
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_rent_rate",
        lambda region: {
            "conversion_rate": 5.1,
            "n_buildings": 40,
            "gate_passed": True,
            "window_years": 5,
            "as_of": "2026-05-01",
            "r_ols": 9.9,
        }
        if region == "흥덕구"
        else {"error": "NO_MATCH"},
    )
    state = new_session("live_rent")
    actions = run_turn(state, Turn(region="흥덕구", property_type="rent", analysis_type="rent_conversion"))
    text = actions[-1].message
    assert actions[-1].kind == "report"
    assert "5.1" in text
    assert "전세 시세가 아닙니다." in text
    assert "9.9" not in text
    assert "적정" not in text
    blocked = new_session("live_rent")
    refused = run_turn(
        blocked,
        Turn(region="흥덕구", property_type="rent", analysis_type="rent_conversion"),
    )
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_rent_rate",
        lambda _region: {"conversion_rate": 5.1, "n_buildings": 2, "gate_passed": False, "window_years": 5},
    )
    gated = new_session("live_rent")
    gated_actions = run_turn(
        gated, Turn(region="흥덕구", property_type="rent", analysis_type="rent_conversion")
    )
    assert gated_actions[-1].kind == "refuse"
    assert "5.1" not in gated_actions[-1].message
    assert refused[-1].kind == "report"


def test_live_profile_names_a_neighbor_and_does_not_adopt_it(monkeypatch):
    monkeypatch.setattr(
        "app.ai2.live_domains.fetch_profile_twin",
        lambda region: {"twin_region": "경기도 파주시", "similarity": 0.88}
        if region == "흥덕구"
        else {"error": "NO_MATCH"},
    )
    state = new_session("live_profile")
    actions = run_turn(state, Turn(region="흥덕구", property_type="profile", analysis_type="profile_twin"))
    assert actions[-1].kind == "report"
    assert "경기도 파주시" in actions[-1].message
    assert "결론으로 쓰지 않음" in actions[-1].message
    assert "0.88" not in actions[-1].message
    assert "similarity" not in actions[0].envelope.facts
    missing = new_session("live_profile")
    monkeypatch.setattr("app.ai2.live_domains.fetch_profile_twin", lambda _region: None)
    down = run_turn(missing, Turn(region="흥덕구", property_type="profile", analysis_type="profile_twin"))
    assert down[-1].kind == "refuse"
    assert "자료를 불러오지 못했습니다." in down[-1].message
    assert "DATABASE_UNAVAILABLE" not in down[-1].message
