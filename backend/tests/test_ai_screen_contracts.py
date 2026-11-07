import json
from pathlib import Path

import pytest
from fastapi import Response
from starlette.requests import Request

from app.ai.dialogue import _render, _screen, _sources, _for_question
from app.ai.orchestrator import handle_chat
from app.ai.schemas import AiChatRequest, AiContext
from app.ai.sessions import get_or_create, session_owner, SessionTurn


def ask(context, answer, monkeypatch, *, general=False):
    def model(*, user, **kwargs):
        payload = json.loads(user)
        if "passages" in payload:
            return json.dumps({"general_indices": list(range(len(payload["passages"]))) if general else []})
        return json.dumps(answer, ensure_ascii=False)
    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", model)
    return handle_chat(AiChatRequest(message="지금 보고 있는 결과와 의미를 설명해 주세요.", context=context))


@pytest.mark.parametrize("kind", ["knowledge", "screen", "clarify"])
def test_observed_numbers_cannot_bypass_checks_by_kind(monkeypatch, kind):
    ctx = AiContext(app="land", panel="LandRegressionTab", facts={"n": 120})
    result = ask(ctx, {"kind": kind, "answer": "현재 화면의 표본은 98765건입니다.",
                       "_general_check": [True, ["현재 화면의 표본은 98765건입니다."]]}, monkeypatch)
    assert "98765" not in result.answer
    assert not result.llm_used
    assert result.error_code == "evidence_validation_failed"


@pytest.mark.parametrize("answer", [
    "유의수준 0.05는 검정에서 정한 오류 확률의 기준입니다.",
    "가상 예시로 보증금 100만원과 월세 5만원을 비교할 수 있습니다.",
    "로그모형은 y = a + b*x 같은 식과 목적이 다릅니다.",
])
def test_general_numbers_and_equations_remain_allowed(monkeypatch, answer):
    result = ask(AiContext(), {"kind": "knowledge", "answer": answer}, monkeypatch, general=True)
    assert result.llm_used and result.answer == answer
    assert result.error_code is None


def test_mixed_freeform_answer_can_include_references_and_hypothetical_numbers(monkeypatch):
    ctx = AiContext(app="land", panel="LandRegressionTab", facts={"n": 120})
    result = ask(ctx, {"kind": "screen", "answer": "{{current.f0}}입니다.\n가상의 예시로 100건을 생각할 수 있습니다."}, monkeypatch, general=True)
    assert result.llm_used and "120건" in result.answer and "100건" in result.answer


@pytest.mark.parametrize("panel", ["BuildingList", "CommercialList"])
def test_list_prices_counts_and_context_reach_evidence(panel):
    result = _screen(AiContext(app="collective", panel=panel, facts={
        "list_n": 10, "window_years": 5,
        "visible_rows": [{"name": "대상 A", "count": 12, "median": 500, "mean": 510}],
        "items": [{"address": "RAW_PRIVATE_MARKER"}],
    }))
    assert "대상 A 평균 단가 510만원/㎡" in result.facts
    assert "목록 대상 수 10개" in result.facts
    assert "RAW_PRIVATE_MARKER" not in str(result)


def test_report_title_prose_and_correlations_reach_referenced_answer(monkeypatch):
    ctx = AiContext(app="insight", panel="Insight02", facts={
        "report": {"title": "부동산 유형별 상관관계", "sections": [
            {"heading": "결과", "text": "인구 보정 뒤 상관계수는 0.54입니다."}]},
        "pairs": [{"a": "상가", "b": "아파트", "amount": {"r": 0.92, "r_pop": 0.54}}],
        "points": [{"address": "RAW_PRIVATE_MARKER", "x": 888888}],
    })
    evidence = _screen(ctx)
    assert evidence.context["보고서 제목"] == "부동산 유형별 상관관계"
    assert any("r_pop 0.54" in fact for fact in evidence.facts)
    assert "RAW_PRIVATE_MARKER" not in str(evidence)
    result = ask(ctx, {"kind": "screen", "answer": "보정 뒤 상관계수는 0.54입니다{{current.f0}}. 따라서 보정 전후를 구분해 읽어야 합니다."}, monkeypatch)
    assert result.llm_used and "0.54" in result.answer


def test_report_ref_does_not_authorize_another_observation(monkeypatch):
    ctx = AiContext(app="insight", panel="Insight02", facts={"report": {"sections": [
        {"heading": "관측", "text": "상관계수는 0.54입니다."}]}})
    result = ask(ctx, {"kind": "screen", "answer": "{{current.f0}} 상관계수는 0.99입니다."}, monkeypatch)
    assert not result.llm_used and "0.99" not in result.answer


def test_sangkwon_all_five_kinds_and_final_metrics_have_units():
    result = _screen(AiContext(app="rent", panel="SangkwonCard", facts={
        "window_label": "2025.3Q~2026.2Q",
        "annual": {m: {k: 5 for k in ("office", "mid_retail", "small_retail", "strata", "retail_all")}
                   for m in ("rent", "investment_yield", "conversion")},
    }))
    assert len(result.facts) == 15
    assert "중대형상가 임대료 5만원/㎡·년" in result.facts
    assert "집합상가 투자수익률 5%" in result.facts
    assert "상가 전체 전환율 5%" in result.facts


def test_profile_amount_population_rank_and_distribution():
    result = _screen(AiContext(app="profile", panel="RegionalProfile", facts={
        "window_years": 3, "total_count_3y": 12, "population": 1000, "total_amount_3y": 45000,
        "national_rank": ["43113114", "복대동", 1000, 45000, 12, 2, 3, 4],
        "features": {"apartment_count": 10, "apartment_p25": 300, "apartment_median": 400, "apartment_p75": 600},
    }))
    assert "인구 1000명" in result.facts and "3년 거래금액 합계 45000만원" in result.facts
    assert "전국 거래금액 순위 2위" in result.facts
    assert "아파트 중앙단가 400만원/㎡" in result.facts
    assert "롤링" not in str(result)


def test_rent_detail_rates_are_distinct_and_base_restored_as_separate_source():
    ctx = AiContext(app="rent", panel="RentBuildingDetail", facts={
        "display_name": "건물 A", "detail_tab": "conversion", "building_rate": 4, "region_rate": 5, "pool_rate": 6,
        "base_screen": {"panel": "RentListCard", "scope": {"region_label": "지역 A"}, "facts": {"r_selected": 5}},
    })
    current = _screen(ctx)
    assert "건물 전환율 4%" in current.facts and "지역 적용 전환율 5%" in current.facts
    sources = _sources("기본표와 비교해줘", current, None)
    assert sources["base"].context["scope"]["region_label"] == "지역 A"
    assert set(_for_question("이것 좀 봐줘", sources)) == {"current", "base"}


def test_session_owner_cannot_read_or_select_another_owners_id():
    with session_owner("user:101"):
        first = get_or_create(None)
        first.add_turn(SessionTurn(role="user", message="private user A"))
        assert get_or_create(first.session_id) is first
    with session_owner("user:202"):
        second = get_or_create(first.session_id)
        assert second.session_id != first.session_id and not second.turns
    with session_owner("user:101"):
        assert get_or_create(first.session_id) is first


def test_browser_owner_cookie_and_signed_user_are_distinct(monkeypatch):
    from app.ai.router import _owner
    monkeypatch.setattr("app.ai.router.decode_access_token", lambda token: {"sub": "101"} if token == "signed-test-user" else None)
    request = Request({"type": "http", "scheme": "http", "headers": [], "path": "/api/ai/chat"})
    response = Response()
    owner = _owner(request, response)
    assert owner.startswith("browser:") and len(owner.split(":", 1)[1]) == 43
    assert "HttpOnly" in response.headers["set-cookie"]
    request = Request({"type": "http", "scheme": "http", "headers": [(b"cookie", b"ch2_session=signed-test-user")], "path": "/api/ai/chat"})
    assert _owner(request, Response()) == "user:101"


def test_session_turns_are_bounded():
    session = get_or_create(None)
    for i in range(100):
        session.add_turn(SessionTurn(role="user", message=str(i)))
    assert len(session.turns) == 40 and session.turns[-1].message == "99"


def test_insight_public_order_matches_shared_product_knowledge():
    from app.ai.knowledge.product import product_knowledge_pack
    root = Path(__file__).resolve().parents[2]
    catalog = json.loads((root / "shared/insight-catalog.json").read_text(encoding="utf-8"))
    knowledge = product_knowledge_pack(app="insight")
    assert len(catalog) == 13
    for item in catalog:
        assert f"{item['q']}번 · {item['title']}" in knowledge
    assert "3번 · 부동산 유형별 상관관계" in knowledge


def test_provider_failure_has_specific_error_code(monkeypatch):
    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", lambda **_: None)
    response = handle_chat(AiChatRequest(message="분석을 설명해줘", context=AiContext()))
    assert response.error_code == "provider_unavailable"
    assert "서비스의 응답" in response.answer


@pytest.mark.parametrize("question", ["저녁시간 유동인구와 상권의 관계는?", "게임이론은 어떻게 활용하나요?", "어느 메뉴를 눌러야 하나요?", "날씨와 상업지역의 매출 관계를 설명해줘"])
def test_negative_scope_does_not_reject_by_single_keyword(monkeypatch, question):
    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", lambda **_: json.dumps({"kind": "knowledge", "answer": "질문의 맥락에 맞춰 설명할 수 있습니다."}, ensure_ascii=False))
    response = handle_chat(AiChatRequest(message=question, context=AiContext()))
    assert response.llm_used and response.route == "ch2"
