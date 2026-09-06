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


def test_built_type_gap_does_not_use_collective_playbook(monkeypatch):
    from app.config import settings
    from app.ai.knowledge.planner import is_knowledge_source_question

    monkeypatch.setattr(settings, "ai_open_mode", False)
    monkeypatch.setattr("app.ai.orchestrator.llm_configured", lambda: False)
    monkeypatch.setattr("app.ai.synthesis.llm_configured", lambda: False)

    q = "복합부동산에서 집합이 아니라 상가와 단독다가구 유형의 가격 차이를 보려면 어떤 방법이 좋나요?"
    ctx = AiContext(app="built", panel="RegressionCard", facts={})
    assert detect_intent(q, ctx) == "built_type_price_gap"
    assert is_path_intent_question(q, ctx)
    assert not is_howto_ui_question(q)

    plan = plan_analysis(q, ctx)
    assert plan["intent_id"] == "built_type_price_gap"
    path_ids = [p["path_id"] for p in plan["paths"]]
    assert "built_type_compare" in path_ids
    assert "collective_integrated_regression" not in path_ids

    resp = handle_chat(AiChatRequest(message=q, context=ctx))
    assert resp.route == "ch2"
    assert "유형 더미" in resp.answer
    assert "계수" in resp.answer
    assert "한 식에 넣지 말고" not in resp.answer
    assert "대상이 아닙니다" not in resp.answer
    assert "확인된 플레이북이 없는" not in resp.answer
    assert any(
        (a.href == "/built/" or a.ui == "built_regression") for a in (resp.actions or [])
    )
    assert not any(a.href == "/collective/residential/" for a in (resp.actions or []))

    apt_on_built = plan_analysis("아파트와 오피스텔 가격 차이를 보고 싶어", ctx)
    assert apt_on_built["intent_id"] == "apartment_officetel_price_gap"
    assert any(p["path_id"] == "collective_integrated_regression" for p in apt_on_built["paths"])

    src = "위의 답변내용(집합 통합회귀, 지역회귀 등)은 ch2 macro 에서 사전에 제공한 지식에 기반해서 답변한 건가?"
    assert is_knowledge_source_question(src)
    assert not is_path_intent_question(src, ctx)
    src_resp = handle_chat(AiChatRequest(message=src, context=ctx))
    assert "확인된 플레이북이 없는" not in src_resp.answer
    assert "Product Knowledge" in src_resp.answer
    assert "Playbook" in src_resp.answer
    assert "유형 더미" in src_resp.answer
    assert not any(a.href == "/collective/residential/" for a in (src_resp.actions or []))

    rec = handle_chat(
        AiChatRequest(message="분석 경로를 추천해 주세요", context=ctx)
    )
    rec_paths = " ".join(a.label or "" for a in (rec.actions or []))
    assert "주거 집합" not in rec_paths
    assert not any(a.href == "/collective/residential/" for a in (rec.actions or []))
    assert "주거 집합에서 통합회귀" not in rec.answer
    assert "확인된 플레이북이 없는" not in rec.answer


def test_nested_admin_scope_not_history_compare(monkeypatch):
    from app.ai.bundles.extractors import build_regression_diagnostic
    from app.ai.knowledge.planner import is_history_compare_question, is_nested_admin_scope_question
    from app.ai.knowledge.product import format_nested_scope_answer
    from app.config import settings

    monkeypatch.setattr(settings, "ai_open_mode", False)
    monkeypatch.setattr("app.ai.orchestrator.llm_configured", lambda: False)
    monkeypatch.setattr("app.ai.synthesis.llm_configured", lambda: False)

    meaning = "1차와 2차가 의미하는 바는 각각 무엇인가?"
    compare_q = "1차와 2차의 결과를 비교설명 바람"
    assert is_nested_admin_scope_question(meaning)
    assert is_nested_admin_scope_question(compare_q)
    assert not is_history_compare_question(meaning)
    assert not is_history_compare_question(compare_q)
    assert is_history_compare_question("아까와 비교해 주세요")
    assert not is_nested_admin_scope_question("아까와 비교해 주세요")

    ctx = AiContext(
        app="built",
        panel="RegressionCard",
        scope=AiScope(region_label="간석동"),
        facts={
            "primary": {
                "scope_label": "간석동",
                "admin_level": "eupmyeondong",
                "n": 67,
                "adj_r_squared": 0.8737,
            },
            "comparisons": [
                {
                    "scope_label": "남동구",
                    "admin_level": "sigungu",
                    "n": 259,
                    "adj_r_squared": 0.9221,
                }
            ],
        },
    )
    pack = build_regression_diagnostic(ctx)
    assert any("남동구" in s for s in pack.summary_lines)

    meaning_resp = handle_chat(AiChatRequest(message=meaning, context=ctx))
    assert "실행 비교" not in meaning_resp.answer
    assert "시군구" in meaning_resp.answer
    assert "읍" in meaning_resp.answer
    assert "History" in meaning_resp.answer or "실행 순서" in meaning_resp.answer
    assert "259" not in meaning_resp.answer or "남동구" in meaning_resp.answer

    cmp_resp = handle_chat(AiChatRequest(message=compare_q, context=ctx))
    assert "실행 비교" not in cmp_resp.answer
    assert "남동구" in cmp_resp.answer
    assert "n=259" in cmp_resp.answer
    assert "n=67" in cmp_resp.answer

    hist_text = format_nested_scope_answer(
        facts=ctx.facts,
        history=[
            {"scope": {"region_label": "간석동 읍면동"}, "n": 259, "path_id": "built_regression"},
            {"scope": {"region_label": "간석동 읍면동"}, "n": 67, "path_id": "built_regression"},
        ],
        message=compare_q,
    )
    assert "실행 순서" in hist_text
    assert "시군구 vs 읍면동 비교가 아닙니다" in hist_text


def test_knowledge_pack_is_app_scoped():
    from app.ai.knowledge.product import (
        is_cross_app_question,
        product_knowledge_excerpt,
        product_knowledge_pack,
        skip_llm_for_quota,
    )

    built = product_knowledge_pack(app="built")
    assert "혼동 금지" in built
    assert "집합 아파트·오피스텔 코호트" in built
    assert "mean_simple" not in built
    assert "window_years=3만" not in built

    land = product_knowledge_pack(app="land")
    assert "거래액 합" in land
    assert "M2" in land
    assert "여러 용도×지목 칸을 한 식에 UNION하지 않음" in land
    assert "asset_type_dummy" not in land

    profile = product_knowledge_pack(app="profile")
    assert "proxy 금지" in profile
    assert "Twin 점수 ≠ 매수" in profile

    rent = product_knowledge_pack(app="rent")
    assert "mean_simple" in rent
    assert "주거 원장과 상권 공표" in rent

    gap = product_knowledge_excerpt(
        app="built", panel="RegressionCard", message="상가와 단독 가격 차이를 어떻게 분석하나요?"
    )
    assert "혼동 금지" in gap
    assert "mean_simple" not in gap

    cross = product_knowledge_excerpt(app="built", panel="", message="토지와 복합은 뭐가 다르나요?")
    assert is_cross_app_question("토지와 복합은 뭐가 다르나요?")
    assert "용도지역×지목" in cross
    assert "asset_type_dummy" in cross

    assert skip_llm_for_quota("1차와 2차가 의미하는 바는 각각 무엇인가?")
    assert skip_llm_for_quota("분석 경로를 추천해 주세요")
    assert skip_llm_for_quota("추세는 어떻게 보나요?")
    assert not skip_llm_for_quota("이번 표본에서 Adj R²가 높은 이유는?")


def test_product_questions_skip_llm_even_if_configured(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_open_mode", False)
    monkeypatch.setattr("app.ai.orchestrator.llm_configured", lambda: True)
    monkeypatch.setattr("app.ai.synthesis.llm_configured", lambda: True)

    def _boom(*_a, **_k):
        raise AssertionError("product questions must not call grounded LLM")

    monkeypatch.setattr("app.ai.orchestrator.try_grounded_synthesis", _boom)

    meaning = handle_chat(
        AiChatRequest(
            message="1차와 2차가 의미하는 바는 각각 무엇인가?",
            context=AiContext(app="built", panel="RegressionCard", facts={}),
        )
    )
    assert meaning.llm_used is False
    assert "시군구" in meaning.answer

    path = handle_chat(
        AiChatRequest(
            message="분석 경로를 추천해 주세요",
            context=AiContext(app="collective", panel="BuildingRegressionPanel"),
        )
    )
    assert path.llm_used is False
    assert path.actions
