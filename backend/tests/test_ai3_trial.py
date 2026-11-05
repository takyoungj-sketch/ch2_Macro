"""AI3 시험 계약·소유권·실행 정합성. 외부 LLM/운영 DB 호출 없음."""
from __future__ import annotations

import time
from contextlib import contextmanager
from unittest.mock import Mock
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.config import settings
from app.ai3 import execution, llm, tools as adapters
from app.ai3.catalog import public_catalog, validate_arguments
from app.ai3.orchestrator import chat
from app.ai3.router import router, _BUCKETS
from app.ai3.schemas import ChatIn, Context, Fact
from app.ai3.store import STATES, session, save_plan
from app.ai3.validation import extract_facts, render_grounded, external_view, redact_for_llm

REAL_DRAFT = llm.draft


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    STATES.clear(); _BUCKETS.clear()
    monkeypatch.setattr(settings, "ai3_enabled", True)
    monkeypatch.setattr(settings, "ai3_access_token", "")
    monkeypatch.setattr(llm, "draft", lambda payload: None)
    monkeypatch.setattr("app.ai3.orchestrator.llm_configured", lambda: False)
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    yield
    STATES.clear(); _BUCKETS.clear()


@pytest.fixture
def client():
    app = FastAPI(); app.include_router(router, prefix="/api")
    with TestClient(app) as c:
        yield c


LAND = dict(beopjungri_code="4311311400", window_years=5, as_of_month="2026-08-01")


def test_disabled_has_no_api(client, monkeypatch):
    monkeypatch.setattr(settings, "ai3_enabled", False)
    assert client.get("/api/ai3/health").status_code == 404
    assert client.post("/api/ai3/chat", json={"message": "안녕"}).status_code == 404


def test_health_and_cookie(client):
    response = client.get("/api/ai3/health")
    assert response.status_code == 200
    assert len(response.json()["tools"]) == 8
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]


def test_explicit_token_and_forwarded_guard(client, monkeypatch):
    assert client.get("/api/ai3/health", headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 401
    monkeypatch.setattr(settings, "ai3_access_token", "private-test")
    assert client.get("/api/ai3/health").status_code == 401
    assert client.get("/api/ai3/health", headers={"X-Ai3-Token": "private-test"}).status_code == 200


def test_cross_origin_and_workers(client, monkeypatch):
    assert client.get("/api/ai3/health", headers={"Origin": "https://attacker.example"}).status_code == 403
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    assert client.get("/api/ai3/health").status_code == 503


def test_rate_limit_not_reset_by_cookie(client):
    for _ in range(120):
        assert client.get("/api/ai3/health").status_code == 200
    client.cookies.clear()
    assert client.get("/api/ai3/health").status_code == 429


def test_session_owner_and_expiry(monkeypatch):
    state = session("alice", None)
    with pytest.raises(HTTPException) as exc:
        session("bob", state.id)
    assert exc.value.status_code == 404
    state.touched = time.time() - 90000
    session("bob", None)
    assert state.id not in STATES


def test_http_chat_session_isolation(client):
    first = client.post("/api/ai3/chat", json={"message": "설명력이 뭔가요?"})
    assert first.status_code == 200
    assert "예측" in first.json()["answer"]
    assert first.json()["evidence"]
    sid = first.json()["session_id"]
    assert client.post("/api/ai3/chat", json={"session_id": sid, "message": "MAPE는?"}).status_code == 200
    client.cookies.clear()
    assert client.post("/api/ai3/chat", json={"session_id": sid, "message": "MAPE는?"}).status_code == 404


@pytest.mark.parametrize("question", ["토지 기능", "복합 기능", "아파트 회귀", "임대 전환율", "지역프로필 쌍둥이", "Macro Insight"])
def test_all_product_domains_from_land(question):
    result = chat(session("owner", None), ChatIn(message=question, context=Context(app="land")))
    assert result.answer and result.evidence and not result.llm_used


@pytest.mark.parametrize("question", ["설명력은?", "R²란?", "MAPE란?", "VIF란?", "p-value란?", "신뢰구간은?", "예측구간은?", "로그 회귀", "표본 한계", "상관과 인과", "회귀란?", "평균과 중앙값"])
def test_general_statistics_without_screen(question):
    result = chat(session("owner", None), ChatIn(message=question))
    assert result.answer and "UI ?" not in result.answer


@pytest.mark.parametrize("prose", ["표본 73건입니다.", "{{f0}}입니다. 수익률 999%입니다.", "-{{f0}}", "{{f0}}%", "{{f9}}", "{{bad}}", "매수 추천합니다."])
def test_unsupported_number_sign_unit_and_refs_rejected(prose):
    assert render_grounded(prose, [Fact(id="f0", label="coef", value="-0.35", source="run")]) is None


def test_reference_preserves_sign_and_no_raw_rows():
    facts = extract_facts({"coef": -0.35, "transactions": [{"price": 999}], "jibun_address": "private"}, "run")
    assert len(facts) == 1
    assert render_grounded("계수는 {{f0}}입니다.", facts) == "계수는 -0.35입니다."


def test_model_answer_and_number_guard(monkeypatch):
    state = session("owner", None)
    monkeypatch.setattr(llm, "draft", lambda _: dict(kind="answer", answer="표본은 {{f0}}입니다.", evidence_ids=["product"]))
    result = chat(state, ChatIn(message="이번 결과를 설명해줘", context=Context(metrics={"n": 73})))
    assert result.answer == "표본은 73.0입니다." and result.llm_used
    monkeypatch.setattr(llm, "draft", lambda _: dict(kind="answer", answer="표본은 999건입니다.", evidence_ids=["product"]))
    assert not chat(state, ChatIn(message="이번 결과를 설명해줘", context=Context(metrics={"n": 73}))).llm_used


def test_model_unknown_source_rejected(monkeypatch):
    monkeypatch.setattr(llm, "draft", lambda _: dict(kind="answer", answer="설명입니다.", evidence_ids=["invented"]))
    assert not chat(session("owner", None), ChatIn(message="회귀란?")).llm_used


def test_model_cannot_run_on_explanation_or_invent_code(monkeypatch):
    drafted = dict(kind="plan", answer="계획을 제안합니다.", evidence_ids=["product"], tool_id="land.basic_stats", arguments=LAND)
    monkeypatch.setattr(llm, "draft", lambda _: drafted)
    state = session("owner", None)
    assert chat(state, ChatIn(message="왜 그런가요?")).plan is None
    assert chat(state, ChatIn(message="가경동 통계를 조회해줘")).kind == "clarify"
    assert not state.executions


@pytest.mark.parametrize("args", [{**LAND, "fixture": "named_ok"}, {**LAND, "beopjungri_code": "중앙동"}, {**LAND, "window_years": 4}, {**LAND, "as_of_month": "2026-08-02"}])
def test_land_inputs_reject_ambiguity_or_unsupported(args):
    with pytest.raises(ValueError):
        validate_arguments("land.basic_stats", args)


def test_floor_periods_and_parity():
    base = dict(target_key="key", year_from=2021, year_to=2025)
    for kind in ("residential", "commercial"):
        parsed = validate_arguments(f"collective.{kind}.index", base)
        assert parsed["year_from"] == 2021 and parsed["year_to"] == 2025
        with pytest.raises(ValueError):
            validate_arguments(f"collective.{kind}.index", {**base, "year_from": 2026})


def test_built_rejects_missing_period_and_ambiguous_region():
    with pytest.raises(ValueError):
        validate_arguments("built.predict", dict(admin_level="sigungu", gross_area=200, land_area=150, building_age=20))


def test_http_plan_no_execution_and_immutable_body(client):
    response = client.post("/api/ai3/chat", json=dict(message="통계를 조회해줘", tool_id="land.basic_stats", arguments=LAND))
    data = response.json()
    assert response.status_code == 200 and data["plan"]
    state = STATES[data["session_id"]]
    assert not state.executions
    assert client.post("/api/ai3/executions", json=dict(session_id=state.id, plan_id=data["plan"]["id"], arguments={})).status_code == 422


class InlinePool:
    def submit(self, fn, *args):
        fn(*args)


def test_execution_idempotency_history_and_followup(monkeypatch):
    monkeypatch.setattr(execution, "_POOL", InlinePool())
    runner = Mock(return_value=({"n": 80, "index": 112}, ["테스트 엔진 한계"]))
    monkeypatch.setattr(execution, "run_tool", runner)
    state = session("owner", None)
    plan = save_plan(state, "land.basic_stats", "토지", LAND)
    first = execution.start(state, plan.id)
    second = execution.start(state, plan.id)
    assert first.id == second.id and runner.call_count == 1
    assert first.status == "succeeded" and state.history == [first.id]
    result = chat(state, ChatIn(message="방금 결과와 한계를 설명해줘"))
    assert result.history_ids == [first.id]
    assert "테스트 엔진 한계" in result.limitations
    assert runner.call_count == 1


@pytest.mark.parametrize("mode", ["expired", "superseded", "unknown"])
def test_plan_invalidity(mode):
    state = session("owner", None)
    plan = save_plan(state, "land.basic_stats", "토지", LAND)
    if mode == "expired": plan.expires_at = 0
    if mode == "superseded": save_plan(state, "land.basic_stats", "토지", LAND)
    with pytest.raises(HTTPException):
        execution.start(state, "missing" if mode == "unknown" else plan.id)


def test_failed_execution_never_success_history(monkeypatch):
    monkeypatch.setattr(execution, "_POOL", InlinePool())
    monkeypatch.setattr(execution, "run_tool", Mock(side_effect=HTTPException(422, "표본 부족")))
    state = session("owner", None)
    result = execution.start(state, save_plan(state, "land.basic_stats", "토지", LAND).id)
    assert result.status == "failed" and not state.history
    assert "표본 부족" in result.error


def test_cancel_waits_for_running_work_and_discards_result(monkeypatch):
    from app.ai3.schemas import ExecutionOut
    state = session("owner", None)
    state.executions["e"] = ExecutionOut(id="e", session_id=state.id, plan_id="p", status="running", created_at=time.time(), applied_arguments={})
    assert execution.cancel(state, "e").status == "cancel_requested"
    execution._run(state, "e", "land.basic_stats", LAND)
    assert execution.get(state, "e").status == "cancelled" and not state.history


@contextmanager
def fake_db(_):
    yield Mock()


def test_real_floor_adapter_uses_product_endpoint_without_insight(monkeypatch):
    from app.collective import router as product
    monkeypatch.setattr(adapters, "database", fake_db)
    endpoint = Mock(return_value={"n_total": 80, "cells": [{"index": 112}], "warnings": ["thin"]})
    monkeypatch.setattr(product, "building_floor_index", endpoint)
    result, limits = adapters.run_tool("collective.residential.index", dict(target_key="key", year_from=2021, year_to=2025))
    assert endpoint.call_args.kwargs["experiment"] is False
    assert endpoint.call_args.kwargs["contract_year_from"] == 2021
    assert "108" not in str(result) and "thin" in limits


def test_real_commercial_adapter_uses_same_gates(monkeypatch):
    from app.collective_commercial import router as product
    monkeypatch.setattr(adapters, "database", fake_db)
    endpoint = Mock(return_value={"n_total": 80, "cells": []})
    monkeypatch.setattr(product, "cluster_floor_index", endpoint)
    adapters.run_tool("collective.commercial.index", dict(target_key="road", year_from=2021, year_to=2025, floor_mode="shop"))
    assert endpoint.call_args.kwargs["experiment"] is False
    assert endpoint.call_args.kwargs["cluster_key"] == "road"


def test_twin_period_fallback_is_not_silently_used(monkeypatch):
    from app.regional_profile import router as product
    monkeypatch.setattr(adapters, "database", fake_db)
    monkeypatch.setattr(product, "get_profile_twin_sigungu", Mock(return_value=Mock(window_years=3)))
    with pytest.raises(HTTPException) as exc:
        adapters.run_tool("profile.twins", dict(sigungu_code="43113", window_years=5))
    assert exc.value.status_code == 422


def test_monthly_usage_and_missing_key(monkeypatch):
    call = Mock(return_value=None)
    monkeypatch.setattr(llm, "_openai_chat", call)
    monkeypatch.setattr(llm, "llm_configured", lambda: False)
    assert REAL_DRAFT({}) is None
    call.assert_not_called()


@pytest.mark.parametrize("text", ["CH2의 P50은 중앙값입니다.", "AI3는 제품 전체를 설명합니다.", "1) 표본의 한계를 봅니다.\n2) 검증 오차를 봅니다."])
def test_product_identifiers_and_list_markers_are_not_measurements(text):
    assert render_grounded(text, []) is not None


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_screen_metrics_rejected(number):
    with pytest.raises(ValueError):
        Context(metrics={"n": number})


@pytest.mark.parametrize("question", ["오늘 날씨 어때?", "이 아파트를 매수하는 것이 좋나요?", "적정가격은 얼마인가요?"])
def test_refusal_never_calls_model(question, monkeypatch):
    model = Mock()
    monkeypatch.setattr(llm, "draft", model)
    result = chat(session("owner", None), ChatIn(message=question))
    assert result.kind == "refusal" and result.evidence
    model.assert_not_called()


def test_cross_app_offline_navigation_targets_rent():
    result = chat(session("owner", None), ChatIn(message="토지 화면이지만 임대 전환율은 어디서 보나요?"))
    assert "매트릭스" not in result.answer and "건물" in result.answer


def test_internal_target_keys_are_never_in_model_view():
    aliases = {}
    view = external_view({"building_key": "private-address-key", "jibun_address": "secret-address", "n": 80}, aliases)
    assert "private-address" not in str(view) and "secret-address" not in str(view)
    assert aliases[view["building_key"]] == "private-address-key"
    assert external_view(view, aliases) == view


def test_target_reference_resolves_only_inside_server_plan():
    state = session("owner", None)
    state.target_refs["target-safe"] = "private-internal-key"
    result = chat(state, ChatIn(message="분석해줘", tool_id="collective.residential.index",
                               arguments=dict(target_key="target-safe", year_from=2021, year_to=2025)))
    assert result.plan.arguments["target_key"] == "private-internal-key"


def test_unknown_tool_is_clarified_without_execution():
    state = session("owner", None)
    result = chat(state, ChatIn(message="실행해줘", tool_id="shell.exec", arguments={"command": "whoami"}))
    assert result.kind == "clarify" and not state.executions


def test_invalid_calendar_month_fails_before_approval():
    with pytest.raises(ValueError):
        validate_arguments("land.basic_stats", {**LAND, "as_of_month": "2026-99-01"})


def test_http_dns_rebinding_host_rejected(client):
    assert client.get("/api/ai3/health", headers={"Host": "attacker.example", "Origin": "http://attacker.example"}).status_code == 401


def test_other_session_cannot_read_execution():
    from app.ai3.schemas import ExecutionOut
    alice = session("alice", None); bob = session("bob", None)
    alice.executions["e"] = ExecutionOut(id="e", session_id=alice.id, plan_id="p", status="succeeded", created_at=time.time(), applied_arguments={})
    with pytest.raises(HTTPException) as exc:
        execution.get(bob, "e")
    assert exc.value.status_code == 404


def test_http_approved_run_can_be_polled(client, monkeypatch):
    monkeypatch.setattr(execution, "_POOL", InlinePool())
    monkeypatch.setattr(execution, "run_tool", lambda *_: ({"n": 80}, []))
    planned = client.post("/api/ai3/chat", json=dict(message="조회해줘", tool_id="land.basic_stats", arguments=LAND)).json()
    body = dict(session_id=planned["session_id"], plan_id=planned["plan"]["id"])
    started = client.post("/api/ai3/executions", json=body)
    assert started.status_code == 200 and started.json()["status"] == "succeeded"
    polled = client.get(f"/api/ai3/executions/{started.json()['id']}", params={"session_id": body["session_id"]})
    assert polled.json()["result"] == {"n": 80}


def test_partial_plan_continues_with_short_reply(monkeypatch):
    state = session("owner", None)
    incomplete = chat(state, ChatIn(message="토지 통계 조회해줘", tool_id="land.basic_stats", arguments={"beopjungri_code": LAND["beopjungri_code"]}))
    assert incomplete.kind == "clarify" and state.draft_request
    observed = {}
    def model(payload):
        observed.update(payload)
        return dict(kind="plan", answer="계획입니다.", evidence_ids=["product"], tool_id="land.basic_stats", arguments=LAND)
    monkeypatch.setattr(llm, "draft", model)
    # 사용자 지정 코드를 그대로 다시 말하는 후속 입력. model이 코드를 추측할 수는 없다.
    response = chat(state, ChatIn(message=f"{LAND['beopjungri_code']}의 기준월은 2026-08-01, 창은 5년으로"))
    assert observed["allow_plan"] and response.plan and state.draft_request is None


def test_model_receives_only_sanitized_pending_target(monkeypatch):
    state = session("owner", None)
    plan = save_plan(state, "collective.residential.index", "주거", {"target_key": "private-address-key"})
    seen = {}
    monkeypatch.setattr(llm, "draft", lambda payload: seen.update(payload))
    chat(state, ChatIn(message="이 계획의 의미는?"))
    assert "private-address-key" not in str(seen)
    assert plan.arguments["target_key"] == "private-address-key"


def test_successful_model_answer_keeps_engine_limitations(monkeypatch):
    from app.ai3.schemas import ExecutionOut
    state = session("owner", None)
    state.executions["e"] = ExecutionOut(id="e", session_id=state.id, plan_id="p", status="succeeded", created_at=time.time(), applied_arguments={}, result={"n":80}, limitations=["외삽으로 중심값 숨김"])
    state.history = ["e"]
    monkeypatch.setattr(llm, "draft", lambda _: dict(kind="answer", answer="한계를 함께 확인해야 합니다.", evidence_ids=["product"]))
    result = chat(state, ChatIn(message="이번 결과 설명"))
    assert result.llm_used and "외삽으로 중심값 숨김" in result.limitations


@pytest.mark.parametrize("payload", [{"raw_rows": []}, {"transactions": []}, {"unknown_app": "land"}])
def test_context_cannot_accept_raw_rows(payload):
    with pytest.raises(ValueError):
        Context.model_validate(payload)


def test_plan_retention_is_bounded():
    state = session("owner", None)
    for _ in range(25): save_plan(state, "land.basic_stats", "토지", LAND)
    assert len(state.plans) == 20 and state.current_plan in state.plans


def test_model_timeout_falls_back_without_execution(monkeypatch):
    monkeypatch.setattr(llm, "draft", Mock(side_effect=TimeoutError()))
    state = session("owner", None)
    result = chat(state, ChatIn(message="MAPE란?"))
    assert not result.llm_used and not state.executions


def test_monthly_budget_stops_before_external_call(monkeypatch):
    call = Mock()
    monkeypatch.setattr(llm, "_openai_chat", call)
    monkeypatch.setattr(llm, "llm_configured", lambda: True)
    monkeypatch.setattr(llm, "_read_events", lambda _: [{"route": "ai3"}] * 40)
    monkeypatch.setattr(settings, "ai3_monthly_call_limit", 40)
    with pytest.raises(ValueError, match="한도"):
        REAL_DRAFT({"context": {"app": "land"}})
    call.assert_not_called()


def test_session_count_is_bounded(monkeypatch):
    monkeypatch.setattr("app.ai3.store.MAX_SESSIONS", 1)
    session("alice", None)
    with pytest.raises(HTTPException) as exc:
        session("bob", None)
    assert exc.value.status_code == 429


@pytest.mark.parametrize("value", ["sk-abcdefghijklmnop12345", "Bearer abcdefghijklmnop12345", "가경동 123-45번지", "세종대로 123"])
def test_accidental_credentials_and_street_numbers_redacted(value):
    result = redact_for_llm({"question": value, "turns": [value]})
    assert value not in str(result)
