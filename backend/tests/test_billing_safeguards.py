"""Always-on FN-002 sale/stub guards, using no external services or DB."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.platform import billing_router as billing
from app.platform.db import get_platform_db
from app.platform.deps import get_optional_user, require_user
from test_access_v2 import START, USER, ReadDB


class NoIO:
    def __getattr__(self, name):
        raise AssertionError(f"no database IO allowed: {name}")


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(billing.router, prefix="/api")
    app.dependency_overrides[get_platform_db] = lambda: NoIO()
    app.dependency_overrides[require_user] = lambda: USER
    app.dependency_overrides[get_optional_user] = lambda: USER
    monkeypatch.setattr(settings, "ch2_deploy_env", "production")
    return TestClient(app)


@pytest.mark.parametrize("mode", ["legacy", "v2"])
@pytest.mark.parametrize("path,body", [("prepare", {"plan_id": "bundle_monthly"}),
                                      ("confirm", {"paymentKey": "test-key-only", "orderId": "test-order-only", "amount": 10000})])
def test_single_payment_is_410_without_any_io(client, monkeypatch, mode, path, body):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", mode)
    monkeypatch.setattr(billing, "confirm_payment", lambda *a, **kw: pytest.fail("external payment called"))
    assert client.post(f"/api/billing/toss/{path}", json=body).status_code == 410
    # Also deny before auth and before valid-body dependency execution.
    client.app.dependency_overrides[require_user] = lambda: pytest.fail("auth should not run")
    assert client.post(f"/api/billing/toss/{path}", json={}).status_code == 410


@pytest.mark.parametrize("mode", ["legacy", "v2"])
@pytest.mark.parametrize("stub", [False, True])
def test_production_rejects_stub_even_with_flag(client, monkeypatch, mode, stub):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", mode)
    monkeypatch.setattr(settings, "play_billing_allow_stub", stub)
    response = client.post("/api/billing/play/verify", json={"purchase_token": "test-token-only", "product_id": "bundle_yearly"})
    assert response.status_code == 410 and response.json()["detail"] == "play_billing_disabled"
    assert client.get("/api/billing/toss/config").json()["play_stub"] is False
    client.app.dependency_overrides[require_user] = lambda: pytest.fail("disabled stub must stop before auth")
    assert client.post("/api/billing/play/verify", json={}).status_code == 410


@pytest.mark.parametrize("env", ["local", "test"])
def test_local_stub_requires_opt_in_and_is_visible(client, monkeypatch, env):
    monkeypatch.setattr(settings, "ch2_deploy_env", env)
    monkeypatch.setattr(settings, "play_billing_allow_stub", False)
    body = billing.PlayVerifyRequest(purchase_token="test-token-only", product_id="bundle_yearly")
    with pytest.raises(HTTPException) as exc:
        billing.verify_play_purchase(body, USER, NoIO())
    assert exc.value.status_code == 410
    monkeypatch.setattr(settings, "play_billing_allow_stub", True)
    monkeypatch.setattr(billing, "create_subscription", lambda *a, **kw: 123)
    monkeypatch.setattr(billing, "list_entitlements", lambda *a: {"macro": True, "fieldnote": True})
    assert billing.verify_play_purchase(body, USER, NoIO())["stub"] is True
    assert billing.toss_config()["play_stub"] is True


@pytest.mark.parametrize("mode", ["legacy", "v2"])
def test_only_unified_plan_is_sold(client, monkeypatch, mode):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", mode)
    monkeypatch.setattr(settings, "ch2_policy_start", START)
    assert client.get("/api/billing/plans").json() == {"currency": "KRW", "plans": [
        {"id": "ch2_monthly", "product": "bundle", "price": 10000, "interval": "month"}]}
    for plan_id in [p["id"] for p in billing._LEGACY_PLANS] + ["unknown"]:
        response = client.post("/api/billing/toss/billing/prepare", json={"plan_id": plan_id})
        assert response.status_code == 400 and response.json()["detail"] == "unknown_plan"


@pytest.mark.parametrize("mode", ["legacy", "v2"])
def test_missing_start_blocks_sales_in_all_modes(client, monkeypatch, mode):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", mode)
    monkeypatch.setattr(settings, "ch2_policy_start", None)
    response = client.post("/api/billing/toss/billing/prepare", json={"plan_id": "ch2_monthly"})
    assert response.status_code == 503 and response.json()["detail"] == "policy_start_missing"
    if mode == "v2":
        client.app.dependency_overrides[get_platform_db] = lambda: ReadDB()
        data = client.get("/api/billing/status").json()
        assert data["policy_active"] is False and data["config_error"] == "policy_start_missing"


def test_new_plan_prepare_uses_existing_writer_without_charging(client, monkeypatch):
    monkeypatch.setattr(settings, "ch2_policy_start", START)
    monkeypatch.setattr(billing, "toss_configured", lambda: True)
    monkeypatch.setattr(billing, "has_blocking_subscription", lambda *a, **kw: False)
    monkeypatch.setattr(billing, "ensure_toss_customer_key", lambda *a: "test-customer")
    calls = []
    monkeypatch.setattr(billing, "create_billing_pending", lambda *a, **kw: (calls.append(kw) or (1, "test-pending")))
    monkeypatch.setattr(billing, "activate_with_billing_key", lambda *a, **kw: pytest.fail("must not charge"))
    response = client.post("/api/billing/toss/billing/prepare", json={"plan_id": "ch2_monthly"})
    assert response.status_code == 200
    assert response.json()["amount"] == 10000
    assert response.json()["orderName"] == "CH2 월 구독"
    assert calls == [{"user_id": USER.id, "plan_id": "ch2_monthly", "product": "bundle"}]


def test_unset_deploy_environment_is_production(monkeypatch):
    monkeypatch.delenv("CH2_DEPLOY_ENV", raising=False)
    config = Settings(_env_file=None, PLAY_BILLING_ALLOW_STUB=True)
    assert config.ch2_deploy_env == "production" and config.play_billing_allow_stub
