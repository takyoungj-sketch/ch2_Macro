"""D-085 Codex B1 검토 반영: AI 과거 근거·제품 지식·저장 결과, QA 토큰 구독 통과."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import admin_auth
from app.feature_gates import FEATURES, HIDDEN_DETAIL
from tests.test_feature_gates import (  # noqa: F401 — 픽스처 재사용
    LAND_BODY,
    _as_role,
    _clean_env,
    _client_with_probes,
    _DbProbe,
    fake_rows,
)

# _clean_env 가 _token_ok 를 False 로 바꾸기 전 원본.
_ORIG_TOKEN_OK = admin_auth._token_ok


def _req():
    from starlette.requests import Request

    return Request({"type": "http", "headers": [], "method": "POST", "path": "/api/ai/chat"})


def _open_gates(monkeypatch):
    from app import product_gate
    from app.ai import router as ai_router
    from app.config import settings

    async def _open(_request):
        return None

    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr(settings, "ai_subscription_quota_enabled", False)
    monkeypatch.setattr(product_gate, "product_gate_response", _open)
    monkeypatch.setattr(ai_router, "check_ai_rate_limit", lambda _r: None)


def _land_regression_ctx():
    return {
        "app": "land", "panel": "LandRegressionTab", "scope": {"region_label": "지역 A"},
        "facts": {
            "n": 123, "adj_r_squared": 0.456, "model_type": "log",
            "coefficients": [{"name": "log_area", "label": "log(면적)", "coef": -0.24}],
        },
    }


# ── 1. 과거 근거 재생 ─────────────────────────────────────────

def test_previous_regression_evidence_not_replayed_after_hide(monkeypatch):
    """Codex 재현: 관리자 때 남은 회귀 근거(123건·R² 0.456)가, 같은 세션의 비관리자 요청
    「아까 회귀 결과」에 previous 로 넘어가면 안 된다. 안내 문구도 만들지 않는다."""
    _open_gates(monkeypatch)
    payloads = []

    def draft(*, user, system, json_response, timeout=45):
        payload = json.loads(user)
        payloads.append(payload)
        if "passages" in payload:
            return json.dumps({"general_indices": []})
        current = payload["sources"].get("current", {}).get("facts", {})
        if current:
            key = next(iter(current))
            return json.dumps({"kind": "screen", "answer": "{{" + key + "}}입니다."}, ensure_ascii=False)
        return json.dumps({"kind": "knowledge", "answer": "어떤 결과를 말씀하시는지 알려 주세요."}, ensure_ascii=False)

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", draft)
    c = _client_with_probes()
    _as_role(monkeypatch, "admin")
    first = c.post("/api/ai/chat", json={"message": "표본은 몇 건이야?", "context": _land_regression_ctx()})
    assert first.status_code == 200, first.text
    sid = first.json()["session_id"]
    assert "123" in json.dumps(payloads[-1], ensure_ascii=False)  # 관리자에게는 보인다

    _as_role(monkeypatch, "member")
    payloads.clear()
    second = c.post("/api/ai/chat", json={
        "message": "아까 회귀 결과 다시 알려줘", "session_id": sid, "context": _land_regression_ctx(),
    })
    assert second.status_code == 200, second.text
    sent = json.dumps(payloads, ensure_ascii=False)
    assert "123" not in sent and "0.456" not in sent
    for payload in payloads:
        assert "previous" not in payload.get("sources", {})
    answer = second.json()["answer"]
    assert "123" not in answer and "0.456" not in answer
    assert "보여 줄 수 없" not in answer and "비공개" not in answer


def test_admin_keeps_previous_evidence(monkeypatch):
    """관리자는 그대로 previous 근거를 쓴다(과잉 삭제 없음)."""
    _open_gates(monkeypatch)
    payloads = []

    def draft(*, user, system, json_response, timeout=45):
        payload = json.loads(user)
        payloads.append(payload)
        if "passages" in payload:
            return json.dumps({"general_indices": []})
        for source in ("current", "previous"):
            facts = payload["sources"].get(source, {}).get("facts", {})
            if facts:
                return json.dumps({"kind": "screen", "answer": "{{" + next(iter(facts)) + "}}입니다."}, ensure_ascii=False)
        return json.dumps({"kind": "knowledge", "answer": "알려 주세요."}, ensure_ascii=False)

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", draft)
    c = _client_with_probes()
    _as_role(monkeypatch, "admin")
    sid = c.post("/api/ai/chat", json={"message": "표본?", "context": _land_regression_ctx()}).json()["session_id"]
    payloads.clear()
    empty = {"app": "land", "panel": "LandRegressionTab", "facts": {}}
    c.post("/api/ai/chat", json={"message": "아까 회귀 결과 알려줘", "session_id": sid, "context": empty})
    assert any("previous" in p.get("sources", {}) for p in payloads)


def test_session_history_purged_by_current_features(monkeypatch):
    from app.ai.feature_filter import ai_feature_scope
    from app.ai.schemas import AiContext
    from app.ai.sessions import MemorySessionStore, SessionTurn, get_or_create, session_owner, set_session_store

    set_session_store(MemorySessionStore())
    ctx = AiContext(app="land", panel="LandRegressionTab", facts={"n": 123, "linked_n": 4})
    try:
        _as_role(monkeypatch, "admin")
        with session_owner("user:1"), ai_feature_scope(_req(), ctx):
            s = get_or_create(None)
            s.add_turn(SessionTurn(role="assistant", message="표본 123건"))
            s.push_analysis({"id": "a", "n": 123, "scope": {"app": "land", "panel": "LandRegressionTab"}})
            s.push_context({"panel": "LandRegressionTab", "n": 123})
            sid = s.session_id
        with session_owner("user:1"), ai_feature_scope(_req(), None):
            s = get_or_create(sid)
            s.add_turn(SessionTurn(role="assistant", message="일반 안내"))
        assert s.analysis_history[0]["_features"] == ["land_ledger_link", "land_regression"]
        assert len(s.turns) == 2  # 관리자 요청에서는 지우지 않는다

        _as_role(monkeypatch, "member")
        with session_owner("user:1"), ai_feature_scope(_req(), None):
            s = get_or_create(sid)
        assert [t.message for t in s.turns] == ["일반 안내"]
        assert s.analysis_history == [] and s.context_snapshots == []
    finally:
        set_session_store(MemorySessionStore())


def test_unbound_scope_does_not_purge(monkeypatch):
    """기능 상태가 묶이지 않은 내부 호출은 세션을 지우지 않는다."""
    from app.ai.feature_filter import ai_feature_scope
    from app.ai.schemas import AiContext
    from app.ai.sessions import MemorySessionStore, get_or_create, session_owner, set_session_store

    set_session_store(MemorySessionStore())
    try:
        _as_role(monkeypatch, "admin")
        ctx = AiContext(app="land", panel="LandRegressionTab", facts={"n": 1})
        with session_owner("user:2"), ai_feature_scope(_req(), ctx):
            s = get_or_create(None)
            s.push_analysis({"id": "a", "n": 1, "scope": {}})
            sid = s.session_id
        with session_owner("user:2"):
            assert len(get_or_create(sid).analysis_history) == 1
    finally:
        set_session_store(MemorySessionStore())


# ── 3. 제품 지식 ───────────────────────────────────────────────

def test_product_knowledge_hides_features_for_users(monkeypatch):
    from app.ai.feature_filter import RENT_HIDDEN_GUIDE, ai_feature_scope
    from app.ai.knowledge.product import (
        format_all_domain_cards,
        format_knowledge_source_answer,
        product_knowledge_excerpt,
        product_knowledge_pack,
    )

    _as_role(monkeypatch, "member")
    with ai_feature_scope(_req(), None):
        land = product_knowledge_pack(app="land", panel="PaidMatrixCell")
        cross = product_knowledge_excerpt(app="rent", panel="RentListCard", message="토지와 임대는 뭐가 달라?")
        rent = product_knowledge_pack(app="rent", panel="RentListCard")
        source = format_knowledge_source_answer(app="rent")
        cards = format_all_domain_cards()
    for text in (land, cross, source, cards):
        assert "유료 필지 회귀" not in text and "매트릭스 셀 회귀" not in text
        assert "공시지가 연결" not in text
    for text in (rent, cards, source):
        assert text.count(RENT_HIDDEN_GUIDE) == 1
        assert "집합부동산(매매)" in text

    _as_role(monkeypatch, "admin")
    with ai_feature_scope(_req(), None):
        land = product_knowledge_pack(app="land", panel="PaidMatrixCell")
        rent = product_knowledge_pack(app="rent", panel="RentListCard")
    assert "유료 필지 회귀" in land
    assert RENT_HIDDEN_GUIDE not in rent


def test_rent_floor_question_gets_collective_guidance(monkeypatch):
    """임대 화면 층·면적 질문 → AI 에 넘기는 제품 지식에 집합 매매 분석 안내가 들어간다."""
    _open_gates(monkeypatch)
    payloads = []

    def draft(*, user, system, json_response, timeout=45):
        payload = json.loads(user)
        payloads.append(payload)
        if "passages" in payload:
            return json.dumps({"general_indices": []})
        return json.dumps({"kind": "knowledge", "answer": "집합부동산(매매) 단지 분석에서 볼 수 있습니다."}, ensure_ascii=False)

    monkeypatch.setattr("app.ai.dialogue.llm._openai_chat", draft)
    _as_role(monkeypatch, "member")
    ctx = {"app": "rent", "panel": "RentBuildingDetail", "facts": {"detail_tab": "regression"}}
    r = _client_with_probes().post("/api/ai/chat", json={"message": "층이나 면적에 따라 전세가 얼마나 달라?", "context": ctx})
    assert r.status_code == 200, r.text
    knowledge = "\n".join(payloads[-1]["product_knowledge"])
    assert "집합부동산(매매)" in knowledge and "효용지수" in knowledge
    assert "유료 필지 회귀" not in knowledge


# ── 저장된 AI 결과 ─────────────────────────────────────────────

def test_stored_result_filtered_by_current_features():
    from app.ai.feature_filter import stored_result_visible

    land_reg = {"answer": "표본 123건", "answer_context": {"app": "land", "panel": "LandRegressionTab"}}
    rent_reg = {"answer": "x", "answer_context": {"app": "rent", "panel": "RentBuildingDetail", "화면": "regression"}}
    ledger = {"answer": "x", "answer_context": {"app": "land", "panel": "TrendCard"}, "feature_tags": ["land_ledger_link"]}
    plain = {"answer": "x", "answer_context": {"app": "land", "panel": "TrendCard"}, "feature_tags": []}
    none = frozenset()
    assert not stored_result_visible(land_reg, none)
    assert not stored_result_visible(rent_reg, none)
    assert not stored_result_visible(ledger, none)
    assert stored_result_visible(plain, none)
    for payload in (land_reg, rent_reg, ledger, plain):
        assert stored_result_visible(payload, frozenset(FEATURES))


# ── 2. QA 토큰은 기능 경로의 구독 검사도 통과 ───────────────────────────

def test_qa_token_reaches_rent_regression_through_real_gates(monkeypatch):
    """실제 미들웨어(토큰·구독 게이트 포함)로: QA 토큰 → 임대 회귀 기존 503 경로까지 간다."""
    from app.config import settings
    from app.main import app
    from app.rent.db import get_rent_db
    from app.rent.query_guard import REGRESSION_TIMEOUT_MESSAGE
    from tests.test_rent_query_guard import FakeDB, _Canceled

    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr(settings, "qa_audit_token", "qa-test-token")
    monkeypatch.setattr(admin_auth, "_token_ok", _ORIG_TOKEN_OK)
    _as_role(monkeypatch, None)

    db = FakeDB(heavy_error=_Canceled())

    def _rent():
        yield db

    app.dependency_overrides[get_rent_db] = _rent
    c = TestClient(app)
    url = "/api/rent/buildings/abc123/regression/run"
    r = c.post(url, params={"asset_type": "apartment"}, json={"asset_type": "apartment"},
               headers={"X-Qa-Audit-Token": "qa-test-token"})
    assert r.status_code == 503, r.text
    assert r.json()["detail"] == REGRESSION_TIMEOUT_MESSAGE
    r = c.post(url, params={"asset_type": "apartment"}, json={}, headers={"X-Qa-Audit-Token": "wrong"})
    assert r.status_code == 403 and r.json()["detail"] == HIDDEN_DETAIL
    # 공개 뒤에는 QA 토큰 우회 없이 기존 구독 게이트를 탄다.
    monkeypatch.setenv("FEATURE_RENT_REGRESSION", "public")
    r = c.post(url, params={"asset_type": "apartment"}, json={}, headers={"X-Qa-Audit-Token": "qa-test-token"})
    assert r.status_code == 401


def test_qa_token_ledger_list_passes_subscription_gate(monkeypatch, fake_rows):
    from app.config import settings

    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr(settings, "qa_audit_token", "qa-test-token")
    monkeypatch.setattr(admin_auth, "_token_ok", _ORIG_TOKEN_OK)
    _as_role(monkeypatch, None)
    c = _client_with_probes(land_probe=_DbProbe())
    body = {**LAND_BODY, "trait_enrich": True}
    r = c.post("/api/paid/matrix-cell-transactions", json=body, headers={"X-Qa-Audit-Token": "qa-test-token"})
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["official_price_won"] == 120000.0
    r = c.post("/api/paid/matrix-cell-transactions", json=body)
    assert r.status_code == 401  # 토큰 없으면 기존 구독 게이트
