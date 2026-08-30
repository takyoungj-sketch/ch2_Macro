"""Planner 실행 가능성 · Caveat · History 자동 기록 (D-056)."""

from app.ai.constitution import classify_route, is_refusal_message
from app.ai.knowledge.caveats import fire_caveats
from app.ai.knowledge.history import maybe_record, slot_from_success_bundle
from app.ai.knowledge.planner import assess_feasibility, detect_intent, is_path_intent_question, plan_analysis
from app.ai.knowledge.product import is_howto_ui_question
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
    assert any("비교" in (q or "") for q in (memo.suggested_followups or []))

    cmp_empty = handle_chat(
        AiChatRequest(
            session_id=rec.session_id,
            message="아까와 비교해 주세요",
            context=AiContext(app="collective", panel="BuildingRegressionPanel", facts={}),
        )
    )
    assert "이전 실행" in cmp_empty.answer
    assert "23%" not in cmp_empty.answer


def test_p3_actions_navigate_open_ui_run_engine():
    from app.ai.knowledge.planner import actions_for_plan, is_history_compare_question

    built_ctx = AiContext(app="built", panel="RegressionCard", facts={})
    plan = plan_analysis("아파트와 오피스텔 가격 차이를 보고 싶어", built_ctx)
    acts = actions_for_plan(plan, built_ctx)
    assert any(a["kind"] == "navigate" and a.get("href") == "/collective/residential/" for a in acts)
    assert not any(a["kind"] == "run_engine" for a in acts)

    list_ctx = AiContext(app="collective", panel="BuildingList", facts={})
    plan_list = plan_analysis("코호트로 보고 싶어", list_ctx)
    acts_list = actions_for_plan(plan_list, list_ctx)
    assert any(a["kind"] == "open_ui" and a.get("ui") == "collective_cohort" for a in acts_list)
    assert not any(a["kind"] == "run_engine" for a in acts_list)

    landing = AiContext(app="collective", panel="CollectiveLanding", facts={})
    acts_land_home = actions_for_plan(plan_analysis("코호트로 보고 싶어", landing), landing)
    assert any(
        a["kind"] == "navigate" and a.get("href") == "/collective/residential/"
        for a in acts_land_home
    )
    assert not any(a["kind"] == "run_engine" for a in acts_land_home)

    two_types = AiContext(
        app="collective",
        panel="BuildingRegressionPanel",
        scope=AiScope(region_label="청주", asset_type="apartment"),
        facts={"n_by_type": {"apartment": 40, "officetel": 18}},
    )
    plan_run = plan_analysis("아파트와 오피스텔 가격 차이를 보고 싶어", two_types)
    integrated = next(p for p in plan_run["paths"] if p["path_id"] == "collective_integrated_regression")
    assert integrated["executable"] == "unknown"
    acts_run = actions_for_plan(plan_run, two_types)
    assert any(
        a["kind"] == "run_engine" and a.get("path_id") == "collective_integrated_regression"
        for a in acts_run
    )

    one_type = AiContext(
        app="collective",
        panel="BuildingRegressionPanel",
        scope=AiScope(asset_type="apartment"),
        facts={},
    )
    plan_no = plan_analysis("아파트와 오피스텔 가격 차이를 보고 싶어", one_type)
    acts_no = actions_for_plan(plan_no, one_type)
    assert not any(a["kind"] == "run_engine" for a in acts_no)
    assert any(a.get("ui") == "collective_cohort" for a in acts_no)

    shop = AiContext(app="collective", panel="CommercialRegressionPanel", facts={})
    plan_shop = plan_analysis("아파트와 오피스텔 가격 차이를 보고 싶어", shop)
    acts_shop = actions_for_plan(plan_shop, shop)
    assert not any(a.get("ui") == "collective_regional" for a in acts_shop)

    land_ctx = AiContext(app="land", panel="PaidMatrixCell", facts={})
    plan_land = plan_analysis("용도지역 지목 단가를 보고 싶어", land_ctx)
    acts_land = actions_for_plan(plan_land, land_ctx)
    assert any(a["kind"] == "open_ui" and a.get("ui") == "land_matrix" for a in acts_land)

    assert is_history_compare_question("아까와 비교해 주세요")
    assert detect_intent("아까와 비교해 주세요") is None


def test_history_compare_slots_only():
    from app.ai.knowledge.history import format_history_compare

    assert "이전 실행" in format_history_compare([])
    assert "이전 실행" in format_history_compare([{"n": 1, "path_id": "x"}])
    text = format_history_compare(
        [
            {
                "path_id": "collective_building_regression",
                "n": 42,
                "scope": {"region_label": "청주"},
                "key_coeffs": [{"name": "atype_officetel", "estimate": -0.123, "p_value": 0.021}],
                "metrics": {"adj_r_squared": 0.4},
                "caveat_ids": ["small_sample"],
            },
            {
                "path_id": "expand_adjacent",
                "n": 187,
                "scope": {"region_label": "청주 인접"},
                "key_coeffs": [{"name": "atype_officetel", "estimate": -0.108, "p_value": 0.004}],
                "metrics": {"adj_r_squared": 0.51},
                "caveat_ids": [],
            },
        ]
    )
    assert "방향은 동일" in text
    assert "n: 42 → 187" in text
    assert "23%" not in text


def test_chat_compare_two_slots_and_actions(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_open_mode", False)
    monkeypatch.setattr("app.ai.orchestrator.llm_configured", lambda: False)
    monkeypatch.setattr("app.ai.synthesis.llm_configured", lambda: False)

    rec1 = handle_history_record(
        AiHistoryRecordRequest(
            context=AiContext(
                app="collective",
                panel="BuildingRegressionPanel",
                scope=AiScope(region_label="청주"),
                facts={
                    "n": 42,
                    "coefficients": [{"name": "atype_officetel", "estimate": -0.12, "p_value": 0.02}],
                    "warnings": [],
                    "n_by_type": {"apartment": 40, "officetel": 18},
                    "cohort": True,
                },
            )
        )
    )
    rec2 = handle_history_record(
        AiHistoryRecordRequest(
            session_id=rec1.session_id,
            context=AiContext(
                app="collective",
                panel="BuildingRegressionPanel",
                scope=AiScope(region_label="청주 인접"),
                facts={
                    "n": 187,
                    "adj_r_squared": 0.5,
                    "coefficients": [{"name": "atype_officetel", "estimate": -0.10, "p_value": 0.004}],
                    "warnings": [],
                    "n_by_type": {"apartment": 120, "officetel": 67},
                    "cohort": True,
                },
            )
        )
    )
    assert rec2.history_len == 2

    cmp_ok = handle_chat(
        AiChatRequest(
            session_id=rec1.session_id,
            message="아까와 비교해 주세요",
            context=AiContext(app="collective", panel="BuildingRegressionPanel", facts={}),
        )
    )
    assert "방향은 동일" in cmp_ok.answer
    assert "23%" not in cmp_ok.answer
    assert "통합회귀가 적합" not in cmp_ok.answer

    path = handle_chat(
        AiChatRequest(
            message="분석 경로를 추천해 주세요",
            context=AiContext(app="collective", panel="BuildingRegressionPanel"),
        )
    )
    assert path.actions
    assert any(a.kind in ("navigate", "open_ui", "run_engine") for a in path.actions)


def test_howto_trend_is_not_playbook_dump(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_open_mode", False)
    monkeypatch.setattr("app.ai.orchestrator.llm_configured", lambda: False)
    monkeypatch.setattr("app.ai.synthesis.llm_configured", lambda: False)

    q = "아파트의 평균 판매가의 과거 추세를 알고 싶은데 어떻게 하면 되지?"
    assert is_howto_ui_question(q)
    assert not is_path_intent_question(q)

    resp = handle_chat(
        AiChatRequest(
            message=q,
            context=AiContext(app="collective", panel="BuildingList"),
        )
    )
    assert "통계분석" in resp.answer
    assert "단지" in resp.answer
    assert "확인된 플레이북" not in resp.answer
    assert "유형 더미" not in resp.answer
    assert is_path_intent_question("아파트와 오피스텔 가격 차이를 보고 싶어")
    assert is_path_intent_question("분석 경로를 추천해 주세요")

