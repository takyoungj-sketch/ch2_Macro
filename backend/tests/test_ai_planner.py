"""Planner 실행 가능성 · Caveat · History 자동 기록 (D-056)."""

from app.ai.constitution import classify_route, is_refusal_message
from app.ai.knowledge.caveats import fire_caveats
from app.ai.knowledge.history import maybe_record, slot_from_success_bundle
from app.ai.knowledge.planner import assess_feasibility, detect_intent, plan_analysis
from app.ai.orchestrator import handle_chat, handle_history_record
from app.ai.schemas import AiChatRequest, AiContext, AiHistoryRecordRequest, AiScope
from app.ai.sessions import get_or_create


def test_analysis_path_recommend_not_refusal(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_open_mode", False)
    monkeypatch.setattr("app.ai.orchestrator.llm_configured", lambda: False)
    assert not is_refusal_message("아파트와 오피스텔은 통합회귀가 적합한가요?")
    assert not is_refusal_message("분석 경로를 추천해 주세요")
    assert classify_route("분석 경로를 추천해 주세요") != "refusal"
    resp = handle_chat(
        AiChatRequest(
            message="분석 경로를 추천해 주세요",
            context=AiContext(app="collective", panel="BuildingRegressionPanel"),
        )
    )
    assert "코호트" in resp.answer or "통합회귀" in resp.answer


def test_investment_recommend_is_refusal():
    assert is_refusal_message("이 아파트를 추천해 주세요")
    assert is_refusal_message("이 아파트는 저평가되어 있습니다")
    assert is_refusal_message("적정가격은 5억인가요?")
    assert classify_route("이 아파트를 매수하는 것이 좋나요?") == "refusal"


def test_gap_intent_and_infeasible_without_two_types():
    assert detect_intent("아파트와 오피스텔 가격격차를 분석해줘") == "apartment_officetel_price_gap"
    ctx = AiContext(
        app="collective",
        panel="BuildingRegressionPanel",
        scope=AiScope(region_label="청주 흥덕구", asset_type="apartment"),
        facts={},
    )
    feas = assess_feasibility("collective_integrated_regression", ctx)
    assert feas["executable"] == "no"
    plan = plan_analysis("아파트와 오피스텔 가격 차이를 보고 싶어", ctx)
    assert plan["intent_id"] == "apartment_officetel_price_gap"
    integrated = next(p for p in plan["paths"] if p["path_id"] == "collective_integrated_regression")
    assert integrated["executable"] == "no"


def test_gap_unknown_when_no_screen():
    ctx = AiContext(app="built", panel="RegressionCard", facts={})
    feas = assess_feasibility("collective_integrated_regression", ctx)
    assert feas["executable"] == "no"


def test_floor_split_warning_fires_caveat():
    fired = fire_caveats(
        n=80,
        warnings=["유형이 층으로 갈립니다 (OT 2–18 / apt 19–26). 같은 층에 두 유형이 없어"],
    )
    ids = [c["id"] for c in fired]
    assert "floor_type_split" in ids
    assert "23%" not in fired[0]["judgment"]


def test_small_sample_cites_bundle_n_not_invented_percent():
    fired = fire_caveats(n=18, warnings=["n=18 — 참고용 (권장 n≥30)"])
    ids = [c["id"] for c in fired]
    assert "small_sample" in ids
    blob = " ".join(c["judgment"] + c["next_action"] for c in fired)
    assert "23%" not in blob
    assert "n=18" in blob


def test_history_only_on_successful_regression():
    session = get_or_create(None)
    empty_ctx = AiContext(app="collective", panel="BuildingRegressionPanel", facts={})
    slot = maybe_record(
        session,
        empty_ctx,
        bundle_id="regression_diagnostic",
        diagnostics={},
    )
    assert slot is None
    assert session.analysis_history == []

    ok_ctx = AiContext(
        app="collective",
        panel="BuildingRegressionPanel",
        scope=AiScope(region_label="청주", asset_type="apartment"),
        facts={
            "n": 42,
            "adj_r_squared": 0.51,
            "coefficients": [{"name": "연식", "estimate": -0.02, "p_value": 0.01}],
            "warnings": [],
            "cohort": True,
        },
    )
    slot = maybe_record(
        session,
        ok_ctx,
        bundle_id="regression_diagnostic",
        diagnostics={"n": 42, "adj_r_squared": 0.51, "warnings": []},
    )
    assert slot is not None
    assert slot.n == 42
    assert len(session.analysis_history) == 1

    # 목록 조회 성격 — coefficients 없음
    none = slot_from_success_bundle(
        AiContext(app="collective", facts={"items": [1, 2, 3]}),
        bundle_id="regression_diagnostic",
        diagnostics={"n": 3},
    )
    assert none is None


def test_history_endpoint_and_chat_planner(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_open_mode", False)
    monkeypatch.setattr("app.ai.orchestrator.llm_configured", lambda: False)
    monkeypatch.setattr("app.ai.synthesis.llm_configured", lambda: False)

    rec = handle_history_record(
        AiHistoryRecordRequest(
            context=AiContext(
                app="collective",
                panel="BuildingRegressionPanel",
                scope=AiScope(region_label="청주 가경동"),
                facts={
                    "n": 18,
                    "coefficients": [{"name": "atype_officetel", "estimate": -0.12, "p_value": 0.02}],
                    "warnings": ["n=18 — 참고용 (권장 n≥30)"],
                    "n_by_type": {"apartment": 40, "officetel": 18},
                    "cohort": True,
                },
            )
        )
    )
    assert rec.recorded is True
    assert rec.history_len == 1

    failed = handle_history_record(
        AiHistoryRecordRequest(
            context=AiContext(app="collective", facts={"count": 5}),
        )
    )
    assert failed.recorded is False

    resp = handle_chat(
        AiChatRequest(
            session_id=rec.session_id,
            message="아파트와 오피스텔 가격 차이를 보고 싶어",
            context=AiContext(
                app="collective",
                panel="BuildingRegressionPanel",
                scope=AiScope(region_label="청주 가경동", asset_type="apartment"),
                facts={},
            ),
        )
    )
    assert resp.route == "ch2"
    assert "통합회귀" in resp.answer
    assert "바로 실행" in resp.answer or "한 유형" in resp.answer or "실행" in resp.answer

    memo = handle_chat(
        AiChatRequest(
            session_id=rec.session_id,
            message="지금까지 실행한 분석을 정리해 주세요",
            context=AiContext(app="collective", panel="BuildingRegressionPanel", facts={}),
        )
    )
    assert "n=18" in memo.answer
    assert "small_sample" in memo.answer
