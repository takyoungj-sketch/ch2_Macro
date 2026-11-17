"""D-085 관리자 전용 기능 스위치. DB 없이 돈다(역할·DB 의존성은 바꿔 끼운다)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import admin_auth, feature_gates
from app.feature_gates import (
    FEATURES,
    HIDDEN_DETAIL,
    LAND_LEDGER_LINK,
    LAND_REGRESSION,
    RENT_REGRESSION,
    feature_mode,
    gated_feature_for_path,
)

LAND_BODY = {"zone_type": "계획관리지역", "land_category": "전", "region_codes": ["4311110100"]}
TRAIT_KEYS = (
    "trait_link_status",
    "trait_link_label",
    "trait_price_status",
    "official_price_won",
    "official_price_year",
    "trait_asof",
    "trait_unverified",
    "recovered_lot",
)


# ── 역할 바꿔 끼우기 ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    from app.config import settings

    for name in FEATURES:
        monkeypatch.delenv(f"FEATURE_{name.upper()}", raising=False)
        monkeypatch.setattr(settings, f"feature_{name}", "")
    monkeypatch.setattr(admin_auth, "_token_ok", lambda _r: False)
    yield
    from app.main import app

    app.dependency_overrides.clear()


def _as_role(monkeypatch, role):
    monkeypatch.setattr(admin_auth, "caller_role", lambda _r: role)


@pytest.fixture
def no_product_gate(monkeypatch):
    """구독 게이트(D-080)를 빼고 라우트 의존성만 본다."""
    from app import product_gate
    from app.config import settings

    async def _open(_request):
        return None

    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr(product_gate, "product_gate_response", _open)


class _DbProbe:
    def __init__(self):
        self.opened = 0


def _client_with_probes(rent_probe=None, land_probe=None) -> TestClient:
    from app.db import get_db
    from app.main import app
    from app.rent.db import get_rent_db

    if rent_probe is not None:
        def _rent():
            rent_probe.opened += 1
            yield object()

        app.dependency_overrides[get_rent_db] = _rent
    if land_probe is not None:
        def _land():
            land_probe.opened += 1
            yield object()

        app.dependency_overrides[get_db] = _land
    return TestClient(app)


# ── 레지스트리 ───────────────────────────────────────────────

def test_registry_defaults_are_admin():
    assert FEATURES == {RENT_REGRESSION: "admin", LAND_REGRESSION: "admin", LAND_LEDGER_LINK: "admin"}
    for name in FEATURES:
        assert feature_mode(name) == "admin"


@pytest.mark.parametrize("raw,expected", [("public", "public"), ("OFF", "off"), (" admin ", "admin"), ("yes", "admin"), ("", "admin")])
def test_env_override(monkeypatch, raw, expected):
    monkeypatch.setenv("FEATURE_RENT_REGRESSION", raw)
    assert feature_mode(RENT_REGRESSION) == expected


def test_dotenv_settings_fallback_and_env_priority(monkeypatch):
    """운영 서비스는 backend/.env 를 pydantic settings 로만 읽는다 — 그 값도 써야 한다."""
    from app.config import settings

    monkeypatch.setattr(settings, "feature_land_ledger_link", "public")
    assert feature_mode(LAND_LEDGER_LINK) == "public"
    monkeypatch.setenv("FEATURE_LAND_LEDGER_LINK", "off")
    assert feature_mode(LAND_LEDGER_LINK) == "off"


def test_settings_fields_map_env_names():
    from app.config import Settings

    s = Settings(_env_file=None, FEATURE_RENT_REGRESSION="public")
    assert s.feature_rent_regression == "public"


def test_unknown_feature_raises():
    with pytest.raises(KeyError):
        feature_mode("nope")
    with pytest.raises(KeyError):
        feature_gates.require_feature("nope")


@pytest.mark.parametrize("role,mode,expected", [
    (None, "admin", False), ("member", "admin", False), ("admin", "admin", True),
    (None, "public", True), ("admin", "off", False),
])
def test_feature_enabled_matrix(monkeypatch, role, mode, expected):
    from starlette.requests import Request

    _as_role(monkeypatch, role)
    monkeypatch.setenv("FEATURE_LAND_REGRESSION", mode)
    req = Request({"type": "http", "headers": [], "method": "GET", "path": "/"})
    assert feature_gates.feature_enabled(req, LAND_REGRESSION) is expected


def test_qa_token_counts_as_admin(monkeypatch):
    from starlette.requests import Request

    _as_role(monkeypatch, None)
    monkeypatch.setattr(admin_auth, "_token_ok", lambda _r: True)
    req = Request({"type": "http", "headers": [], "method": "GET", "path": "/"})
    assert feature_gates.is_admin(req) is True


def test_role_is_looked_up_once_per_request(monkeypatch):
    from starlette.requests import Request

    calls = []
    monkeypatch.setattr(admin_auth, "caller_role", lambda _r: calls.append(1) or "admin")
    req = Request({"type": "http", "headers": [], "method": "GET", "path": "/"})
    for name in FEATURES:
        feature_gates.feature_enabled(req, name)
    assert len(calls) == 1


def test_gated_paths():
    assert gated_feature_for_path("POST", "/api/rent/buildings/" + "a" * 64 + "/regression/run") == RENT_REGRESSION
    assert gated_feature_for_path("POST", "/api/rent/regression/run") == RENT_REGRESSION
    for suffix in ("", "/suggest", "/predict"):
        assert gated_feature_for_path("POST", "/api/paid/matrix-cell-transactions/regression" + suffix) == LAND_REGRESSION
    assert gated_feature_for_path("POST", "/api/paid/matrix-cell-transactions") is None
    assert gated_feature_for_path("GET", "/api/rent/regression/run") is None
    assert gated_feature_for_path("POST", "/api/rent/buildings/abc/transactions") is None


# ── /api/features ─────────────────────────────────────────────

@pytest.mark.parametrize("role", [None, "member"])
def test_features_for_users_is_empty(monkeypatch, role):
    _as_role(monkeypatch, role)
    r = _client_with_probes().get("/api/features")
    assert r.status_code == 200  # 제품 게이트를 거쳐도 열려 있다
    assert r.json() == {"features": [], "private": []}
    assert "no-store" in r.headers["cache-control"]
    assert "Cookie" in r.headers["vary"]


def test_features_for_admin_lists_private(monkeypatch):
    _as_role(monkeypatch, "admin")
    r = _client_with_probes().get("/api/features")
    body = r.json()
    assert set(body["features"]) == set(FEATURES)
    assert set(body["private"]) == set(FEATURES)


def test_public_feature_is_listed_without_badge(monkeypatch):
    _as_role(monkeypatch, None)
    monkeypatch.setenv("FEATURE_RENT_REGRESSION", "public")
    body = _client_with_probes().get("/api/features").json()
    assert body == {"features": [RENT_REGRESSION], "private": []}
    _as_role(monkeypatch, "admin")
    body = _client_with_probes().get("/api/features").json()
    assert RENT_REGRESSION in body["features"] and RENT_REGRESSION not in body["private"]


# ── 임대 회귀 403 (DB 세션 전에) ──────────────────────────────────

@pytest.mark.parametrize("role", [None, "member"])
def test_rent_regression_403_before_db(monkeypatch, no_product_gate, role):
    _as_role(monkeypatch, role)
    probe = _DbProbe()
    c = _client_with_probes(rent_probe=probe)
    r1 = c.post("/api/rent/buildings/abc/regression/run", params={"asset_type": "apartment"}, json={})
    r2 = c.post("/api/rent/regression/run", params=[("building_key", "a"), ("building_key", "b")], json={})
    assert (r1.status_code, r2.status_code) == (403, 403)
    assert r1.json()["detail"] == HIDDEN_DETAIL
    assert probe.opened == 0


def test_rent_regression_admin_reaches_db(monkeypatch, no_product_gate):
    _as_role(monkeypatch, "admin")
    probe = _DbProbe()
    r = _client_with_probes(rent_probe=probe).post(
        "/api/rent/buildings/abc/regression/run", params={"asset_type": "apartment"}, json={}
    )
    assert r.status_code != 403
    assert probe.opened == 1


def test_product_gate_rule_blocks_before_subscription(monkeypatch):
    """미들웨어 이중 방어: 구독 판정(401)보다 403 이 먼저다."""
    from app.config import settings

    monkeypatch.setattr(settings, "api_token", "")
    _as_role(monkeypatch, None)
    c = _client_with_probes()
    r = c.post("/api/rent/regression/run", params={"building_key": "a"}, json={})
    assert r.status_code == 403 and r.json()["detail"] == HIDDEN_DETAIL
    r = c.post("/api/paid/matrix-cell-transactions/regression/predict", json=LAND_BODY)
    assert r.status_code == 403 and r.json()["detail"] == HIDDEN_DETAIL
    monkeypatch.setenv("FEATURE_RENT_REGRESSION", "public")
    r = c.post("/api/rent/regression/run", params={"building_key": "a"}, json={})
    assert r.status_code == 401  # 공개 후에는 기존 구독 게이트(D-080)


# ── 토지 회귀 403 ───────────────────────────────────────────────

@pytest.mark.parametrize("suffix", ["", "/suggest", "/predict"])
def test_land_regression_403_before_db(monkeypatch, no_product_gate, suffix):
    _as_role(monkeypatch, "member")
    probe = _DbProbe()
    r = _client_with_probes(land_probe=probe).post(
        "/api/paid/matrix-cell-transactions/regression" + suffix, json=LAND_BODY
    )
    assert r.status_code == 403
    assert probe.opened == 0


# ── land_ledger_link ───────────────────────────────────────────

def _fake_rows():
    return [{
        "id": 1, "contract_year": 2025, "contract_month": 3, "contract_date": None,
        "beopjungri_code": "4311110100", "sigungu_name": "청주시", "eupmyeondong_name": "우암동",
        "beopjungri_name": "우암동", "lot_display": "1-1", "land_category": "전",
        "partial_ownership_label": "단독", "deal_type": "중개", "area_sqm": 330.0,
        "total_price_10k": 10000.0, "unit_price_per_sqm": 30.3, "road_condition": "세로",
        "is_partial_ownership": False,
        "trait_link_status": "exact", "trait_link_label": "일치", "trait_price_status": "same_year",
        "official_price_won": 120000.0, "official_price_year": 2025, "trait_asof": None,
        "trait_unverified": False, "recovered_lot": "1-1",
    }]


@pytest.fixture
def fake_rows(monkeypatch):
    from app import land_trait_link
    from app.routers import paid

    seen = []

    def _fetch(body, db, *, trait_enrich=False):
        seen.append(trait_enrich)
        rows = _fake_rows()
        if not trait_enrich:
            for row in rows:
                for key in TRAIT_KEYS:
                    row.pop(key, None)
        return rows

    monkeypatch.setattr(paid, "_fetch_matrix_cell_filtered_transactions", _fetch)
    monkeypatch.setattr(land_trait_link, "table_ready", lambda _db: True)
    return seen


@pytest.mark.parametrize("role", [None, "member"])
def test_ledger_request_rejected_for_users(monkeypatch, no_product_gate, fake_rows, role):
    _as_role(monkeypatch, role)
    c = _client_with_probes(land_probe=_DbProbe())
    body = {**LAND_BODY, "trait_enrich": True}
    assert c.post("/api/paid/matrix-cell-transactions", json=body).status_code == 403
    assert c.post("/api/paid/matrix-cell-transactions/export", json=body).status_code == 403
    assert fake_rows == []  # 원거래 조회 전에 거절


def test_user_list_has_no_ledger_keys(monkeypatch, no_product_gate, fake_rows):
    _as_role(monkeypatch, "member")
    r = _client_with_probes(land_probe=_DbProbe()).post("/api/paid/matrix-cell-transactions", json=LAND_BODY)
    assert r.status_code == 200
    item = r.json()["items"][0]
    for key in TRAIT_KEYS:
        assert key not in item
    assert r.json()["trait_enrich_applied"] is False


def test_admin_list_keeps_ledger_values(monkeypatch, no_product_gate, fake_rows):
    _as_role(monkeypatch, "admin")
    r = _client_with_probes(land_probe=_DbProbe()).post(
        "/api/paid/matrix-cell-transactions", json={**LAND_BODY, "trait_enrich": True}
    )
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["official_price_won"] == 120000.0 and item["recovered_lot"] == "1-1"
    assert r.json()["trait_enrich_applied"] is True


def test_user_csv_has_no_ledger_columns(monkeypatch, no_product_gate, fake_rows):
    from app.land_trait_link import TRAIT_CSV_HEADER

    _as_role(monkeypatch, "member")
    r = _client_with_probes(land_probe=_DbProbe()).post("/api/paid/matrix-cell-transactions/export", json=LAND_BODY)
    assert r.status_code == 200
    head = r.content.decode("utf-8-sig").splitlines()[0]
    for col in TRAIT_CSV_HEADER:
        assert col not in head


@pytest.mark.parametrize("suffix", ["", "/predict"])
def test_assessed_variable_rejected_when_ledger_hidden(monkeypatch, no_product_gate, fake_rows, suffix):
    """회귀를 공개해도 대장 연결이 비공개면 공시지가 변수는 거절."""
    _as_role(monkeypatch, "member")
    monkeypatch.setenv("FEATURE_LAND_REGRESSION", "public")
    body = {**LAND_BODY, "variables": {"assessed_land_price": True}}
    r = _client_with_probes(land_probe=_DbProbe()).post(
        "/api/paid/matrix-cell-transactions/regression" + suffix, json=body
    )
    assert r.status_code == 403 and r.json()["detail"] == HIDDEN_DETAIL
    assert fake_rows == []


# ── 캐시 키 ─────────────────────────────────────────────────

def test_analysis_cache_key_split_by_gate():
    import hashlib
    import json
    from datetime import date

    from app.routers.paid import _make_cache_key, _request_stable_payload
    from app.schemas import PaidAnalysisRequest

    req = PaidAnalysisRequest(region_codes=["4311110100"])
    as_of = date(2026, 10, 1)
    legacy = hashlib.sha256(json.dumps({
        "request": _request_stable_payload(req.model_dump(mode="json")),
        "as_of_month": as_of.isoformat(),
        "published_at": None,
    }, sort_keys=True).encode()).hexdigest()
    assert _make_cache_key(req, as_of=as_of) == legacy  # 사용자 기본 = 예전 키
    admin = _make_cache_key(req, as_of=as_of, gate="land_ledger_link,land_regression,rent_regression")
    assert admin != legacy


# ── AI 입구 ─────────────────────────────────────────────────

def _ctx(app, panel, facts):
    from app.ai.schemas import AiContext

    return AiContext(app=app, panel=panel, facts=facts)


def _req():
    from starlette.requests import Request

    return Request({"type": "http", "headers": [], "method": "POST", "path": "/api/ai/chat"})


def test_ai_strips_rent_regression_for_users(monkeypatch):
    from app.ai.feature_filter import filter_ai_context

    _as_role(monkeypatch, "member")
    ctx = _ctx("rent", "RentBuildingDetail", {"detail_tab": "regression", "coefficients": [{"name": "floor"}]})
    out = filter_ai_context(ctx, _req())
    assert out.facts == {"detail_tab": "regression"}
    other = filter_ai_context(_ctx("rent", "RentBuildingDetail", {"detail_tab": "conversion", "building_rate": 4.1}), _req())
    assert other.facts["building_rate"] == 4.1


def test_ai_strips_land_regression_panels_and_ledger(monkeypatch):
    from app.ai.feature_filter import filter_ai_context

    _as_role(monkeypatch, None)
    reg = filter_ai_context(_ctx("land", "LandRegressionTab", {"r_squared": 0.4}), _req())
    assert reg.facts == {}
    facts = {
        "rows": [{"official_price_won": 1, "unit_price_per_sqm": 2}],
        "coefficients": [{"name": "log_assessed_land_price", "coef": 0.5}, {"name": "log_area", "coef": -0.2}],
        "analysis": {"sample_groups": [{"key": "우암동", "n": 3, "linked_n": 2, "unlinked_n": 1}], "assessed_years": [2025]},
        "base_screen": {"app": "rent", "panel": "RentBuildingDetail", "facts": {"detail_tab": "regression", "n": 9}},
    }
    out = filter_ai_context(_ctx("land", "TrendCard", facts), _req()).facts
    assert out["rows"] == [{"unit_price_per_sqm": 2}]
    assert out["coefficients"] == [{"name": "log_area", "coef": -0.2}]
    assert out["analysis"] == {"sample_groups": [{"key": "우암동", "n": 3}]}
    assert out["base_screen"]["facts"] == {"detail_tab": "regression"}


def test_ai_keeps_everything_for_admin(monkeypatch):
    from app.ai.feature_filter import filter_ai_context

    _as_role(monkeypatch, "admin")
    facts = {"coefficients": [{"name": "log_assessed_land_price"}], "linked_n": 3}
    out = filter_ai_context(_ctx("land", "LandRegressionTab", facts), _req())
    assert out.facts == facts


def test_ai_history_entry_is_filtered(monkeypatch):
    from app.ai import router as ai_router
    from app.ai.schemas import AiHistoryRecordResponse

    _as_role(monkeypatch, "member")
    seen = []

    def _record(body):
        seen.append(body.context.facts)
        return AiHistoryRecordResponse(session_id="s", recorded=False)

    monkeypatch.setattr(ai_router, "handle_history_record", _record)
    monkeypatch.setattr(ai_router, "check_ai_rate_limit", lambda _r: None)
    from app import product_gate

    async def _open(_request):
        return None

    monkeypatch.setattr(product_gate, "product_gate_response", _open)
    r = _client_with_probes().post("/api/ai/history", json={
        "context": {"app": "land", "panel": "LandRegressionTab", "facts": {"r_squared": 0.4, "linked_n": 2}},
    })
    assert r.status_code == 200
    assert seen == [{}]
