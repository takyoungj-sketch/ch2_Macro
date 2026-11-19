"""FN-002 unit 2: account APIs preserve keys and the product gate preserves paths."""

import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config import settings
from app.platform import auth_router, billing_router
from app.platform.access import resolve_access
from app.platform.db import get_platform_db
from app.platform.deps import get_optional_user, require_user
from app import product_gate
from test_access_v2 import END, START, USER, ReadDB, subscription


@pytest.fixture(autouse=True)
def fixed_policy(monkeypatch):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", "v2")
    monkeypatch.setattr(settings, "ch2_policy_start", START)


def test_auth_keys_and_values_across_modes(monkeypatch):
    keys = {"user_id", "products", "fieldnote", "macro"}
    for mode, now, expected in [("legacy", END, False), ("v2", END - timedelta(seconds=1), True),
                                 ("v2", END, False)]:
        monkeypatch.setattr(settings, "ch2_entitlement_mode", mode)
        monkeypatch.setattr(auth_router, "resolve_access", lambda db, user: resolve_access(db, user, now))
        value = auth_router.auth_entitlements(USER, ReadDB())
        assert set(value) == keys
        assert value["products"] == {"macro": expected, "fieldnote": expected}
        assert value["macro"] is expected and value["fieldnote"] is expected


def test_subscription_legacy_snapshot_preserved(monkeypatch):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", "legacy")
    monkeypatch.setattr(billing_router, "resolve_access", lambda db, user: resolve_access(db, user, END))
    ent = [{"product": "macro", "active": True, "expires_at": None}]
    monkeypatch.setattr(billing_router, "get_web_subscription", lambda db, uid: None)
    assert billing_router.subscription_me(USER, ReadDB(ent=ent)) == {
        "active": False, "entitlements": {"macro": True, "fieldnote": False}}
    sub = subscription(plan_id="macro_monthly", product="macro", status="past_due", current_period_end=END)
    monkeypatch.setattr(billing_router, "get_web_subscription", lambda db, uid: sub)
    assert billing_router.subscription_me(USER, ReadDB(ent=ent)) == {
        "active": True, "product": "macro", "plan_id": "macro_monthly", "price": 10000,
        "status": "past_due", "current_period_end": END, "next_billing_at": END,
        "cancel_at_period_end": False, "entitlements": {"macro": True, "fieldnote": False}}


def test_scheduled_subscription_has_same_keys_but_is_not_paid(monkeypatch):
    monkeypatch.setattr(billing_router, "resolve_access", lambda db, user: resolve_access(db, user, END))
    value = billing_router.subscription_me(USER, ReadDB(subs=[subscription()]))
    assert set(value) == {"active", "product", "plan_id", "price", "status", "current_period_end",
                          "next_billing_at", "cancel_at_period_end", "entitlements"}
    assert value["active"] is False and not any(value["entitlements"].values())


def test_public_status_http_and_exact_offline_boundary(monkeypatch):
    app = FastAPI()
    app.include_router(billing_router.router, prefix="/api")
    app.dependency_overrides[get_platform_db] = lambda: ReadDB()
    app.dependency_overrides[get_optional_user] = lambda: None
    monkeypatch.setattr(billing_router, "resolve_access", lambda db, user: resolve_access(db, user, END))
    client = TestClient(app)
    response = client.get("/api/billing/status")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "anonymous" and data["offline_until"] == data["server_time"]
    app.dependency_overrides[get_optional_user] = lambda: USER
    monkeypatch.setattr(billing_router, "resolve_access", lambda db, user: resolve_access(db, user, END - timedelta(seconds=1)))
    assert client.get("/api/billing/status").json()["offline_until"] == END.isoformat()


@pytest.mark.parametrize("now,status,reason", [(END - timedelta(seconds=1), None, None),
                                                (END, 403, "payment_processing")])
def test_real_caller_access_and_gate_use_unified_decision(monkeypatch, now, status, reason):
    db = ReadDB(subs=[subscription()])
    original_execute = db.execute
    def execute(sql, params=None):
        if "SELECT id, role" in str(sql):
            return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: {"id": USER.id, "role": "member"}))
        return original_execute(sql, params)
    db.execute = execute
    db.close = lambda: None
    monkeypatch.setattr(product_gate, "get_platform_session_factory", lambda: lambda: db)
    monkeypatch.setattr(product_gate, "decode_access_token", lambda token: {"sub": str(USER.id)})
    monkeypatch.setattr(product_gate, "resolve_access", lambda db, user: resolve_access(db, user, now))
    request = Request({"type": "http", "method": "GET", "path": "/api/rent/meta",
                       "headers": [(b"authorization", b"Bearer test-only")], "query_string": b""})
    response = asyncio.run(product_gate.product_gate_response(request))
    if status is None:
        assert response is None
    else:
        assert response.status_code == status
        assert json.loads(response.body) == {"detail": "구독이 필요합니다.", "code": "subscription_required",
                                              "detail_reason": reason}


def test_anonymous_gate_detail_and_code(monkeypatch):
    monkeypatch.setattr(product_gate, "get_platform_session_factory", lambda: None)
    request = Request({"type": "http", "method": "GET", "path": "/api/rent/meta", "headers": [], "query_string": b""})
    response = asyncio.run(product_gate.product_gate_response(request))
    assert response.status_code == 401
    assert json.loads(response.body) == {"detail": "로그인이 필요합니다.", "code": "login_required", "detail_reason": "login_required"}
