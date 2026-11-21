"""FN-006 billing cycle. Toss is mocked. Concurrent cases use a throwaway local database."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.orm import sessionmaker

from app.config import Settings, settings
from app.platform.billing_period import KST, anchor, next_period_end
from app.platform.access import resolve_access
from app.platform.db import get_platform_db
from app.platform.deps import CurrentUser, require_user
from app.platform.toss_client import TossApiError
from app.platform import toss_client
from app.platform import billing_router as billing
from app.platform import web_subscription as ws
from test_access_v2 import END, START, USER, ReadDB, subscription

BACKEND = Path(__file__).resolve().parents[1]
DUE = END
NOW = END


def test_order_id_uses_kst_calendar_day():
    due = datetime(2026, 11, 30, 15, 30, tzinfo=timezone.utc)
    created = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert ws.order_id_for(12, due, created) == "ch2-12-1767323045000-20261201"


@pytest.mark.parametrize(
    ("payment", "code", "transport", "kind"),
    [
        ({"status": "DONE", "totalAmount": 10000}, None, False, "approved"),
        ({"status": "DONE", "totalAmount": 15000}, None, False, "unknown"),
        ({"status": "ABORTED", "totalAmount": 10000}, None, False, "declined"),
        ({"status": "EXPIRED"}, None, False, "declined"),
        ({"status": "CANCELED"}, None, False, "declined"),
        ({"status": "PARTIAL_CANCELED", "totalAmount": 10000}, None, False, "unknown"),
        ({"status": "READY"}, None, False, "unknown"),
        ({"status": "IN_PROGRESS"}, None, False, "unknown"),
        (None, "NOT_FOUND_PAYMENT", False, "absent"),
        (None, "DUPLICATED_ORDER_ID", False, "unknown"),
        (None, None, True, "unknown"),
    ],
)
def test_lookup_interpretation(payment, code, transport, kind):
    assert ws.interpret_lookup(payment=payment, error_code=code, transport=transport) == kind


def test_only_card_declines_close_the_row():
    assert ws.interpret_charge_failure(403, "REJECT_CARD_PAYMENT") == "declined"
    assert ws.interpret_charge_failure(400, "INVALID_STOPPED_CARD") == "declined"
    assert ws.interpret_charge_failure(400, "DUPLICATED_ORDER_ID") == "unknown"
    assert ws.interpret_charge_failure(409, "IDEMPOTENT_REQUEST_PROCESSING") == "unknown"
    assert ws.interpret_charge_failure(500, "FAILED_INTERNAL_SYSTEM_PROCESSING") == "unknown"
    assert ws.interpret_charge_failure(400, None) == "unknown"


def test_processing_before_renewal_is_not_paid(monkeypatch):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", "v2")
    monkeypatch.setattr(settings, "ch2_policy_start", START)
    access = resolve_access(ReadDB(subs=[subscription()]), USER, END)
    assert access.state == "expired" and access.reason == "payment_processing"
    assert access.billing == "scheduled"
    assert not any(access.features.values())


def test_prepare_rejects_an_open_subscription(monkeypatch):
    app = FastAPI()
    app.include_router(billing.router, prefix="/api")
    app.dependency_overrides[get_platform_db] = lambda: object()
    app.dependency_overrides[require_user] = lambda: USER
    monkeypatch.setattr(settings, "ch2_policy_start", START)
    monkeypatch.setattr(billing, "toss_configured", lambda: True)
    monkeypatch.setattr(billing, "has_blocking_subscription", lambda *a, **k: True)
    monkeypatch.setattr(billing, "create_billing_pending", lambda *a, **k: pytest.fail("pending created"))
    response = TestClient(app).post("/api/billing/toss/billing/prepare", json={"plan_id": "ch2_monthly"})
    assert response.status_code == 409
    assert response.json()["detail"] == "already_subscribed"


def _local_platform_url():
    raw = os.environ.get("CH2_TEST_PG_URL", "").strip()
    if not raw:
        pytest.skip("CH2_TEST_PG_URL 없음")
    url = make_url(raw)
    if (url.host or "").lower() not in {"localhost", "127.0.0.1"}:
        pytest.skip("시험 DB 호스트가 로컬이 아님")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    return url


@pytest.fixture(scope="module")
def platform():
    url = _local_platform_url()
    name = f"ch2_fn006_{uuid.uuid4().hex}"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # noqa: BLE001
        admin.dispose()
        pytest.skip(type(exc).__name__)
    target = url.set(database=name)
    engine = None
    try:
        engine = create_engine(target, pool_pre_ping=True)
        with engine.begin() as conn:
            conn.execute(text(
                """
                CREATE TABLE users (
                    id BIGSERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    provider VARCHAR(32) NOT NULL DEFAULT 'google',
                    provider_sub VARCHAR(255) NOT NULL,
                    nickname VARCHAR(80) NOT NULL UNIQUE,
                    role VARCHAR(32) NOT NULL DEFAULT 'member',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    toss_customer_key VARCHAR(50)
                );
                CREATE TABLE subscriptions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    product VARCHAR(32) NOT NULL,
                    source VARCHAR(32) NOT NULL,
                    external_id VARCHAR(255),
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    current_period_end TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    plan_id VARCHAR(64),
                    toss_billing_key VARCHAR(200),
                    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
                    next_billing_at TIMESTAMPTZ,
                    CONSTRAINT subscriptions_status_chk CHECK (
                        status IN ('active', 'canceled', 'expired', 'pending', 'past_due')
                    )
                );
                CREATE UNIQUE INDEX idx_subscriptions_external ON subscriptions (source, external_id)
                    WHERE external_id IS NOT NULL;
                CREATE TABLE entitlements (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    product VARCHAR(32) NOT NULL,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    expires_at TIMESTAMPTZ,
                    source_sub BIGINT REFERENCES subscriptions(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (user_id, product)
                );
                """
            ))
        yield {"engine": engine, "dsn": target.render_as_string(hide_password=False)}
    finally:
        try:
            if engine is not None:
                engine.dispose()
        finally:
            try:
                with admin.connect() as conn:
                    conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            finally:
                admin.dispose()


@pytest.fixture
def db(platform, monkeypatch):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", "v2")
    monkeypatch.setattr(settings, "ch2_policy_start", START)
    session = sessionmaker(bind=platform["engine"])()
    session.execute(text("TRUNCATE TABLE entitlements, subscriptions, users RESTART IDENTITY CASCADE"))
    session.commit()
    yield session
    session.close()


def _user(db, created=START - timedelta(days=100)) -> int:
    return int(db.execute(
        text(
            """
            INSERT INTO users (email, provider, provider_sub, nickname, created_at, toss_customer_key)
            VALUES ('member@example.invalid', 'google', 'sub-fn006', 'fn006', :created, 'customer-key-test-value')
            RETURNING id
            """
        ),
        {"created": created},
    ).scalar())


def _sub(db, user_id, **kwargs) -> int:
    values = {
        "uid": user_id,
        "status": "pending",
        "plan": "ch2_monthly",
        "created": START,
        "end": None,
        "due": DUE,
        "cancel": False,
        "key": "billing-key-test",
        "ext": "prep-fn006",
    }
    values.update(kwargs)
    db.commit()
    return int(db.execute(
        text(
            """
            INSERT INTO subscriptions (
                user_id, product, source, external_id, status, plan_id, created_at,
                current_period_end, next_billing_at, cancel_at_period_end, toss_billing_key
            )
            VALUES (
                :uid, 'bundle', 'web_toss', :ext, :status, :plan, :created,
                :end, :due, :cancel, :key
            )
            RETURNING id
            """
        ),
        values,
    ).scalar())


def _row(db, sub_id):
    return db.execute(
        text(
            """
            SELECT status, cancel_at_period_end, external_id, current_period_end, next_billing_at
            FROM subscriptions WHERE id = :sid
            """
        ),
        {"sid": sub_id},
    ).mappings().one()


@pytest.mark.parametrize(
    ("status", "period_end", "reason"),
    [
        ("expired", None, "trial_ended"),  # R2c -> R5, no approved charge
        ("past_due", None, "payment_failed"),
        ("expired", END - timedelta(days=1), "subscription_required"),  # historical paid period
    ],
)
def test_expired_reason_uses_recorded_paid_period(monkeypatch, status, period_end, reason):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", "v2")
    monkeypatch.setattr(settings, "ch2_policy_start", START)
    access = resolve_access(
        ReadDB(subs=[subscription(status=status, current_period_end=period_end)]), USER, END
    )
    assert access.state == "expired" and access.reason == reason
    assert not any(access.features.values())


def test_platform_fixture_drops_database_when_schema_setup_fails(monkeypatch):
    statements = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement):
            statements.append(str(statement))

    class AdminEngine:
        def connect(self):
            return Connection()

        def dispose(self):
            statements.append("ADMIN_DISPOSE")

    class TargetEngine:
        def begin(self):
            raise RuntimeError("injected schema initialization failure")

        def dispose(self):
            statements.append("TARGET_DISPOSE")

    engines = iter([AdminEngine(), TargetEngine()])
    monkeypatch.setattr(sys.modules[__name__], "_local_platform_url", lambda: make_url("postgresql://localhost/postgres"))
    monkeypatch.setattr(sys.modules[__name__], "create_engine", lambda *a, **k: next(engines))
    setup = platform.__wrapped__()
    with pytest.raises(RuntimeError, match="injected schema initialization failure"):
        next(setup)
    assert any("CREATE DATABASE" in sql for sql in statements)
    assert any("DROP DATABASE IF EXISTS" in sql for sql in statements)
    assert "TARGET_DISPOSE" in statements and "ADMIN_DISPOSE" in statements


def test_conflicting_activation_deletes_unstored_key_and_keeps_409(caplog, monkeypatch):
    monkeypatch.setattr(settings, "ch2_policy_start", START)
    billing_key = "key-value-must-never-be-logged"
    deleted = []

    class Result:
        def __init__(self, row=None):
            self.row = row

        def mappings(self):
            return self

        def first(self):
            return self.row

    class ConflictDB:
        def execute(self, statement, params=None):
            query = str(statement)
            if "JOIN users" in query:
                return Result({"id": 42, "user_id": USER.id, "product": "bundle", "plan_id": "ch2_monthly",
                               "status": "pending", "created_at": START - timedelta(days=100)})
            if "FROM users" in query:
                return Result()
            if "SELECT id FROM subscriptions" in query:
                return Result({"id": 99})
            raise AssertionError(query)

        def rollback(self):
            pass

        def commit(self):
            raise AssertionError("conflict path must not commit")

    monkeypatch.setattr(ws, "issue_billing_key", lambda *a, **k: {"billingKey": billing_key})

    def delete(key):
        deleted.append(key)
        raise TossApiError(503, "cleanup unavailable")

    monkeypatch.setattr(ws, "delete_billing_key", delete)
    with pytest.raises(ValueError, match="already_subscribed"):
        ws.activate_with_billing_key(
            ConflictDB(), user_id=USER.id, pending_external_id="pending-test", auth_key="auth-key-test",
            customer_key="customer-key-test", amount=10000, order_name="CH2 월 구독", user_email=None,
            now=END - timedelta(days=1),
        )
    assert deleted == [billing_key]
    assert "orphan Toss billing key cleanup failed" in caplog.text
    assert billing_key not in caplog.text


def test_billing_activate_maps_conflict_to_http_409(monkeypatch):
    monkeypatch.setattr(settings, "ch2_billing_paused", False)
    monkeypatch.setattr(billing, "toss_configured", lambda: True)
    monkeypatch.setattr(billing, "ensure_toss_customer_key", lambda *a, **k: "customer-key-test")
    monkeypatch.setattr(billing, "activate_with_billing_key", lambda *a, **k: (_ for _ in ()).throw(ValueError("already_subscribed")))

    class PendingDB:
        def execute(self, *_a, **_k):
            return type("PendingResult", (), {
                "mappings": lambda self: self,
                "first": lambda self: {"plan_id": "ch2_monthly"},
            })()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        billing.toss_billing_activate(
            billing.TossBillingActivateRequest(
                auth_key="auth-key-test", customer_key="customer-key-test", pending_id="pending-test"
            ), user=USER, db=PendingDB(),
        )
    assert exc.value.status_code == 409 and exc.value.detail == "already_subscribed"


def _renewal_module():
    path = BACKEND / "scripts" / "platform_billing_renewal.py"
    spec = importlib.util.spec_from_file_location("fn010_platform_billing_renewal", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_billing_pause_setting_defaults_off(monkeypatch):
    monkeypatch.delenv("CH2_BILLING_PAUSED", raising=False)
    assert Settings(_env_file=None).ch2_billing_paused is False


def test_paused_renewal_stops_before_creating_session(monkeypatch, capsys):
    renewal = _renewal_module()
    monkeypatch.setattr(settings, "ch2_billing_paused", True)
    monkeypatch.setattr(renewal, "get_platform_session_factory", lambda: pytest.fail("DB factory called"))
    monkeypatch.setattr(renewal, "renew_due_subscriptions", lambda *_a, **_k: pytest.fail("renewal called"))
    assert renewal.main() == 0
    assert capsys.readouterr().out.strip() == "PAUSED"


def test_unpaused_renewal_keeps_existing_runner_behavior(monkeypatch, capsys):
    renewal = _renewal_module()
    calls = []

    class Session:
        def close(self):
            calls.append("closed")

    monkeypatch.setattr(settings, "ch2_billing_paused", False)
    monkeypatch.setattr(renewal, "get_platform_session_factory", lambda: lambda: Session())
    monkeypatch.setattr(renewal, "renew_due_subscriptions", lambda db: calls.append("renewed") or 2)
    assert renewal.main() == 0
    assert calls == ["renewed", "closed"]
    assert capsys.readouterr().out.strip() == "OK: renewed 2"


def test_billing_pause_blocks_prepare_and_activate_before_side_effects(monkeypatch):
    monkeypatch.setattr(settings, "ch2_billing_paused", True)
    monkeypatch.setattr(billing, "toss_configured", lambda: pytest.fail("Toss checked while paused"))
    monkeypatch.setattr(billing, "ensure_toss_customer_key", lambda *_a, **_k: pytest.fail("customer touched"))
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as prepared:
        billing.toss_billing_prepare(billing.TossBillingPrepareRequest(plan_id="ch2_monthly"), USER, object())
    with pytest.raises(HTTPException) as activated:
        billing.toss_billing_activate(
            billing.TossBillingActivateRequest(
                auth_key="auth-key-test", customer_key="customer-key-test", pending_id="pending-test"
            ), USER, object(),
        )
    assert (prepared.value.status_code, prepared.value.detail) == (503, "billing_paused")
    assert (activated.value.status_code, activated.value.detail) == (503, "billing_paused")


def test_billing_status_only_adds_pause_flag_when_enabled(monkeypatch):
    class StableAccess:
        def status(self):
            return {"state": "anonymous", "features": {"macro_full": False, "map_hub": False, "ai": False}}

    monkeypatch.setattr(billing, "resolve_access", lambda *_a, **_k: StableAccess())
    monkeypatch.setattr(settings, "ch2_billing_paused", False)
    unpaused = billing.billing_status(None, None)
    assert "billing_paused" not in unpaused
    monkeypatch.setattr(settings, "ch2_billing_paused", True)
    paused = billing.billing_status(None, None)
    assert paused["billing_paused"] is True
    assert {key: value for key, value in paused.items() if key != "billing_paused"} == unpaused


def test_pause_does_not_change_existing_paid_access(monkeypatch):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", "v2")
    monkeypatch.setattr(settings, "ch2_policy_start", START)
    monkeypatch.setattr(settings, "ch2_billing_paused", True)
    paid_until = END + timedelta(days=30)
    access = resolve_access(
        ReadDB(subs=[subscription(status="active", current_period_end=paid_until, next_billing_at=paid_until)]),
        USER, END,
    )
    assert access.state == "paid" and all(access.features.values())


def test_delete_billing_key_uses_official_delete_endpoint(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        text = ""

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def delete(self, url, headers):
            calls.append((url, headers))
            return Response()

    monkeypatch.setattr(toss_client.httpx, "Client", lambda **_kwargs: Client())
    toss_client.delete_billing_key("test/key")
    assert calls[0][0] == "https://api.tosspayments.com/v1/billing/test%2Fkey"


def test_unpaused_due_runner_processes_each_due_row_once(monkeypatch):
    calls = []

    class ScalarResult:
        def all(self):
            return [42]

    class Result:
        def scalars(self):
            return ScalarResult()

    class DueSession:
        def execute(self, *_a, **_k):
            return Result()

        def rollback(self):
            calls.append("rollback")

    monkeypatch.setattr(settings, "ch2_billing_paused", False)
    monkeypatch.setattr(ws, "_process_due", lambda db, sub_id, now: calls.append(sub_id) or "approved")
    assert ws.renew_due_subscriptions(DueSession(), now=END) == 1
    assert calls == ["rollback", 42]


def _patch(monkeypatch, lookup, charge):
    monkeypatch.setattr(ws, "get_payment_by_order", lookup)
    monkeypatch.setattr(ws, "charge_billing", charge)


def _not_found(order_id):
    raise TossApiError(404, '{"code":"NOT_FOUND_PAYMENT","message":"존재하지 않는 결제 정보 입니다."}')


def _done(order_id):
    return {"status": "DONE", "totalAmount": 10000, "orderId": order_id}


def test_trial_registration_stores_key_without_charge(db, monkeypatch):
    calls = []
    monkeypatch.setattr(ws, "issue_billing_key", lambda *a, **k: {"billingKey": "issued-key"})
    _patch(monkeypatch, lambda *a, **k: calls.append("lookup"), lambda billing_key, **k: calls.append("charge"))
    user_id = _user(db)
    db.commit()
    _, external_id = ws.create_billing_pending(db, user_id=user_id, plan_id="ch2_monthly", product="bundle")
    result = ws.activate_with_billing_key(
        db, user_id=user_id, pending_external_id=external_id, auth_key="auth-key-test",
        customer_key="customer-key-test-value", amount=10000, order_name="CH2 월 구독",
        user_email=None, now=END - timedelta(days=1),
    )
    assert result["outcome"] == "scheduled" and calls == []
    row = db.execute(text("SELECT status, next_billing_at, current_period_end, toss_billing_key IS NOT NULL AS keyed FROM subscriptions WHERE id = :sid"), {"sid": result["id"]}).mappings().one()
    assert row["status"] == "pending" and row["keyed"] and row["current_period_end"] is None
    assert row["next_billing_at"] == END


def test_lookup_done_grants_without_another_charge(db, monkeypatch):
    charged = []
    _patch(monkeypatch, _done, lambda billing_key, **k: charged.append(k["order_id"]))
    user_id = _user(db)
    sub_id = _sub(db, user_id, due=END, end=None, created=START)
    db.commit()
    assert ws.renew_due_subscriptions(db, now=NOW) == 1
    assert charged == []
    row = _row(db, sub_id)
    expected = next_period_end(anchor({"created_at": START}, END), END)
    assert row["status"] == "active" and row["external_id"] == ws.order_id_for(sub_id, END, START)
    assert row["current_period_end"] == expected and row["cancel_at_period_end"] is False
    assert db.execute(text("SELECT count(*) FROM entitlements WHERE user_id = :uid AND active"), {"uid": user_id}).scalar() == 2


def test_absent_then_approval_charges_once(db, monkeypatch):
    charged = []
    _patch(monkeypatch, _not_found, lambda billing_key, **k: charged.append(k) or {"status": "DONE", "totalAmount": 10000})
    user_id = _user(db)
    sub_id = _sub(db, user_id)
    db.commit()
    assert ws.renew_due_subscriptions(db, now=NOW) == 1
    assert [call["order_id"] for call in charged] == [ws.order_id_for(sub_id, DUE, START)]
    assert charged[0]["idempotency_key"] == charged[0]["order_id"]
    assert charged[0]["order_name"] == "CH2 월 구독" and charged[0]["amount"] == 10000
    assert _row(db, sub_id)["status"] == "active"


def test_clear_decline_does_not_grant(db, monkeypatch):
    def charge(billing_key, **kwargs):
        raise TossApiError(403, '{"code":"REJECT_CARD_PAYMENT"}')

    _patch(monkeypatch, _not_found, charge)
    user_id = _user(db)
    sub_id = _sub(db, user_id, status="active", end=DUE)
    db.commit()
    assert ws.renew_due_subscriptions(db, now=NOW) == 0
    assert _row(db, sub_id)["status"] == "past_due"
    assert db.execute(text("SELECT count(*) FROM entitlements")).scalar() == 0


def test_lookup_timeout_does_not_charge_or_change_state(db, monkeypatch):
    def lookup(order_id):
        raise httpx.ConnectTimeout("timeout")

    _patch(monkeypatch, lookup, lambda billing_key, **k: pytest.fail("charged after unknown lookup"))
    user_id = _user(db)
    sub_id = _sub(db, user_id)
    db.commit()
    assert ws.renew_due_subscriptions(db, now=NOW) == 0
    row = _row(db, sub_id)
    assert row["status"] == "pending" and row["external_id"] == "prep-fn006"


def test_charge_timeout_is_resolved_by_the_next_lookup(db, monkeypatch):
    calls = {"n": 0}

    def lookup(order_id):
        if calls["n"]:
            return _done(order_id)
        raise TossApiError(404, '{"code":"NOT_FOUND_PAYMENT"}')

    def charge(billing_key, **kwargs):
        calls["n"] += 1
        raise httpx.ConnectTimeout("timeout")

    _patch(monkeypatch, lookup, charge)
    user_id = _user(db)
    sub_id = _sub(db, user_id)
    db.commit()
    assert ws.renew_due_subscriptions(db, now=NOW) == 0
    assert _row(db, sub_id)["status"] == "pending"
    assert ws.renew_due_subscriptions(db, now=NOW) == 1
    assert calls["n"] == 1 and _row(db, sub_id)["status"] == "active"


def test_cancel_before_processing_expires_without_charge(db, monkeypatch):
    _patch(monkeypatch, _not_found, lambda billing_key, **k: pytest.fail("charged a canceled row"))
    user_id = _user(db)
    sub_id = _sub(db, user_id, cancel=True)
    db.commit()
    before = resolve_access(db, CurrentUser(user_id, "member@example.invalid", "fn006", "member"), NOW)
    assert before.state == "expired" and before.reason == "trial_ended"
    assert ws.renew_due_subscriptions(db, now=NOW) == 0
    assert _row(db, sub_id)["status"] == "expired"


def test_unknown_then_cancel_grants_when_lookup_is_done(db, monkeypatch):
    phase = {"lookup": "timeout"}

    def lookup(order_id):
        if phase["lookup"] == "timeout":
            raise httpx.ConnectTimeout("timeout")
        return _done(order_id)

    _patch(monkeypatch, lookup, lambda billing_key, **k: pytest.fail("second charge"))
    user_id = _user(db)
    sub_id = _sub(db, user_id, status="active", end=DUE)
    db.commit()
    ws.renew_due_subscriptions(db, now=NOW)
    assert ws.set_cancel_at_period_end(db, user_id, True)
    phase["lookup"] = "done"
    assert ws.renew_due_subscriptions(db, now=NOW) == 1
    row = _row(db, sub_id)
    assert row["status"] == "active" and row["cancel_at_period_end"] is True
    assert row["current_period_end"] > DUE


def test_unknown_then_cancel_expires_when_payment_is_absent(db, monkeypatch):
    phase = {"lookup": "absent", "charges": 0}

    def lookup(order_id):
        if phase["lookup"] == "done":
            return _done(order_id)
        raise TossApiError(404, '{"code":"NOT_FOUND_PAYMENT"}')

    def charge(billing_key, **kwargs):
        phase["charges"] += 1
        raise httpx.ConnectTimeout("timeout")

    _patch(monkeypatch, lookup, charge)
    user_id = _user(db)
    sub_id = _sub(db, user_id)
    db.commit()
    ws.renew_due_subscriptions(db, now=NOW)
    ws.set_cancel_at_period_end(db, user_id, True)
    ws.renew_due_subscriptions(db, now=NOW)
    assert phase["charges"] == 1
    assert _row(db, sub_id)["status"] == "expired"


def test_repeated_unknown_results_use_one_order_and_grant_once(db, monkeypatch, caplog):
    script = ["unknown", "charge", "unknown", "charge", "done"]
    step = {"n": 0}
    charged = []

    def lookup(order_id):
        kind = script[step["n"]]
        step["n"] += 1
        if kind == "unknown":
            raise httpx.ConnectTimeout("timeout")
        if kind == "done":
            return _done(order_id)
        raise TossApiError(404, '{"code":"NOT_FOUND_PAYMENT"}')

    def charge(billing_key, **kwargs):
        charged.append(kwargs["order_id"])
        raise httpx.ConnectTimeout("timeout")

    _patch(monkeypatch, lookup, charge)
    user_id = _user(db)
    sub_id = _sub(db, user_id, due=NOW - timedelta(hours=25))
    db.commit()
    with caplog.at_level("WARNING"):
        for _ in range(4):
            assert ws.renew_due_subscriptions(db, now=NOW) == 0
        assert ws.renew_due_subscriptions(db, now=NOW) == 1
    assert charged and set(charged) == {ws.order_id_for(sub_id, NOW - timedelta(hours=25), START)}
    assert _row(db, sub_id)["status"] == "active"
    assert "billing result unknown for over 24h" in caplog.text


def test_old_plan_is_not_charged(db, monkeypatch, caplog):
    _patch(monkeypatch, _not_found, lambda billing_key, **k: pytest.fail("charged an old plan"))
    user_id = _user(db)
    sub_id = _sub(db, user_id, plan="bundle_monthly", ext="old-plan")
    db.commit()
    with caplog.at_level("WARNING"):
        assert ws.renew_due_subscriptions(db, now=NOW) == 0
    assert _row(db, sub_id)["status"] == "pending"
    assert "unknown plan_id=bundle_monthly" in caplog.text


_CHILD = r"""
import os
import time
from datetime import datetime
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.platform.billing_period import KST
import app.platform.web_subscription as ws
from app.platform.toss_client import TossApiError

settings.ch2_policy_start = datetime(2026, 12, 1, tzinfo=KST)
mode = os.environ["FN006_MODE"]
log_path = os.environ["FN006_LOG"]
ready = os.environ.get("FN006_READY") or ""

def lookup(order_id):
    raise TossApiError(404, '{"code":"NOT_FOUND_PAYMENT"}')

def charge(billing_key, **kwargs):
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(kwargs["order_id"] + "\n")
        handle.flush()
    if ready:
        with open(ready, "w", encoding="utf-8") as handle:
            handle.write("ready")
    if mode == "slow":
        time.sleep(1.5)
    return {"status": "DONE", "totalAmount": 10000}

ws.get_payment_by_order = lookup
ws.charge_billing = charge
engine = create_engine(os.environ["FN006_DSN"])
db = sessionmaker(bind=engine)()
try:
    ws.renew_due_subscriptions(db, now=datetime.fromisoformat(os.environ["FN006_NOW"]))
finally:
    db.close()
    engine.dispose()
"""


def _spawn(platform, mode, log_path, ready=None):
    env = os.environ.copy()
    env.update({
        "FN006_DSN": platform["dsn"],
        "FN006_NOW": NOW.isoformat(),
        "FN006_MODE": mode,
        "FN006_LOG": str(log_path),
    })
    if ready:
        env["FN006_READY"] = str(ready)
    return subprocess.Popen([sys.executable, "-c", _CHILD], cwd=BACKEND, env=env)


def _wait_ready(path: Path):
    deadline = time.time() + 8
    while time.time() < deadline:
        if path.exists():
            return
        time.sleep(0.05)
    raise AssertionError("renewal did not reach the charge call")


def test_two_processes_charge_once(db, platform, tmp_path):
    user_id = _user(db)
    sub_id = _sub(db, user_id, ext="race-row")
    db.commit()
    log_path = tmp_path / "charges.txt"
    first = _spawn(platform, "slow", log_path)
    second = _spawn(platform, "slow", log_path)
    assert first.wait(timeout=15) == 0
    assert second.wait(timeout=15) == 0
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    assert lines == [ws.order_id_for(sub_id, DUE, START)]
    assert _row(db, sub_id)["status"] == "active"


def test_cancel_during_charge_does_not_wait_and_keeps_the_flag(db, platform, tmp_path):
    user_id = _user(db)
    sub_id = _sub(db, user_id, ext="cancel-race")
    db.commit()
    ready = tmp_path / "ready"
    worker = _spawn(platform, "slow", tmp_path / "charges.txt", ready)
    _wait_ready(ready)
    started = time.perf_counter()
    assert ws.set_cancel_at_period_end(db, user_id, True)
    elapsed = time.perf_counter() - started
    assert elapsed < 0.5
    assert worker.wait(timeout=15) == 0
    row = _row(db, sub_id)
    assert row["status"] == "active" and row["cancel_at_period_end"] is True
    assert row["current_period_end"] is not None


def test_pool_size_one_cannot_take_the_same_lock(platform):
    engine = create_engine(platform["dsn"], pool_size=1, max_overflow=0, pool_timeout=1)
    held = ws._acquire_billing_lock(engine, 900001)
    assert held is not None
    try:
        with pytest.raises(PoolTimeout):
            ws._acquire_billing_lock(engine, 900001)
    finally:
        ws._release_billing_lock(held, 900001)
    again = ws._acquire_billing_lock(engine, 900001)
    assert again is not None
    ws._release_billing_lock(again, 900001)
    engine.dispose()


def test_late_approval_extends_the_original_period_once(db, platform, monkeypatch):
    user_id = _user(db)
    sub_id = _sub(db, user_id, ext="late-row")
    db.commit()
    expected = next_period_end(anchor({"created_at": START}, END), END)

    def charge(billing_key, **kwargs):
        other = sessionmaker(bind=platform["engine"])()
        try:
            snap = dict(ws._reread(other, sub_id))
            other.rollback()
            assert ws._grant(other, snap, kwargs["order_id"]) is True
        finally:
            other.close()
        return {"status": "DONE", "totalAmount": 10000}

    _patch(monkeypatch, _not_found, charge)
    assert ws.renew_due_subscriptions(db, now=NOW) == 0
    row = _row(db, sub_id)
    assert row["status"] == "active"
    assert row["current_period_end"] == expected
    assert row["external_id"] == ws.order_id_for(sub_id, DUE, START)


def test_same_order_done_twice_extends_once(db, monkeypatch):
    _patch(monkeypatch, _done, lambda billing_key, **k: pytest.fail("lookup done must not charge"))
    user_id = _user(db)
    sub_id = _sub(db, user_id, ext="done-twice")
    db.commit()
    assert ws.renew_due_subscriptions(db, now=NOW) == 1
    end = _row(db, sub_id)["current_period_end"]
    assert ws.renew_due_subscriptions(db, now=NOW) == 0
    assert _row(db, sub_id)["current_period_end"] == end


def test_concurrent_activation_keeps_one_order(db, platform, monkeypatch):
    issued = {"n": 0}
    gate = threading.Lock()

    def issue(*args, **kwargs):
        with gate:
            issued["n"] += 1
            return {"billingKey": f"issued-{issued['n']}"}

    monkeypatch.setattr(ws, "issue_billing_key", issue)
    monkeypatch.setattr(ws, "delete_billing_key", lambda *_a, **_k: None)
    user_id = _user(db)
    db.commit()
    _, first = ws.create_billing_pending(db, user_id=user_id, plan_id="ch2_monthly", product="bundle")
    _, second = ws.create_billing_pending(db, user_id=user_id, plan_id="ch2_monthly", product="bundle")
    barrier = threading.Barrier(2)
    results = []

    def activate(external_id):
        session = sessionmaker(bind=platform["engine"])()
        try:
            barrier.wait(timeout=5)
            results.append(ws.activate_with_billing_key(
                session, user_id=user_id, pending_external_id=external_id, auth_key="auth-key-test",
                customer_key="customer-key-test-value", amount=10000, order_name="CH2 월 구독",
                user_email=None, now=START + timedelta(days=1),
            ))
        except ValueError as exc:
            results.append(str(exc))
        finally:
            session.close()

    workers = [threading.Thread(target=activate, args=(ext,)) for ext in (first, second)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=15)
    assert sorted(
        item if isinstance(item, str) else item["outcome"] for item in results
    ) == ["already_subscribed", "scheduled"]
    charged = []
    _patch(monkeypatch, _not_found, lambda billing_key, **k: charged.append(k["order_id"]) or {"status": "DONE", "totalAmount": 10000})
    assert ws.renew_due_subscriptions(db, now=END) == 1
    assert len(charged) == 1


def test_unknown_row_blocks_a_second_registration(db, monkeypatch):
    monkeypatch.setattr(ws, "issue_billing_key", lambda *a, **k: {"billingKey": "not-stored"})
    monkeypatch.setattr(ws, "delete_billing_key", lambda *_a, **_k: None)
    user_id = _user(db)
    unknown_id = _sub(db, user_id, ext="unknown-open", key="kept-key")
    db.commit()
    _, external_id = ws.create_billing_pending(db, user_id=user_id, plan_id="ch2_monthly", product="bundle")
    with pytest.raises(ValueError, match="already_subscribed"):
        ws.activate_with_billing_key(
            db, user_id=user_id, pending_external_id=external_id, auth_key="auth-key-test",
            customer_key="customer-key-test-value", amount=10000, order_name="CH2 월 구독",
            user_email=None, now=END - timedelta(days=1),
        )
    rows = db.execute(text(
        "SELECT id, status, toss_billing_key, next_billing_at FROM subscriptions ORDER BY id"
    )).mappings().all()
    unknown = next(row for row in rows if row["id"] == unknown_id)
    other = next(row for row in rows if row["id"] != unknown_id)
    assert unknown["status"] == "pending" and unknown["toss_billing_key"] == "kept-key"
    assert unknown["next_billing_at"] == DUE
    assert other["toss_billing_key"] is None


def _toss_order_ok(value: str) -> bool:
    return 6 <= len(value) <= 64 and all(char.isalnum() or char in "-_" for char in value)


def test_order_id_generation_and_toss_limits():
    due = datetime(2026, 12, 21, tzinfo=timezone.utc)
    first = datetime(2026, 11, 21, tzinfo=timezone.utc)
    second = datetime(2026, 11, 21, 0, 0, 1, tzinfo=timezone.utc)
    older = ws.order_id_for(1, due, first)
    newer = ws.order_id_for(1, due, second)
    assert older != newer
    assert _toss_order_ok(older) and _toss_order_ok(newer)
    widest = ws.order_id_for(
        9223372036854775807,
        datetime(2026, 12, 21, tzinfo=timezone.utc),
        datetime(9999, 12, 31, 12, 0, tzinfo=timezone.utc),
    )
    assert _toss_order_ok(widest)
    assert ws.order_id_for(1, due, first) == older


def test_previous_generation_done_does_not_grant(db, monkeypatch):
    user_id = _user(db)
    sub_id = _sub(db, user_id)
    db.commit()
    old_order = ws.order_id_for(sub_id, DUE, START - timedelta(days=400))
    new_order = ws.order_id_for(sub_id, DUE, START)
    charged = []

    def lookup(order_id):
        if order_id == old_order:
            return {"status": "DONE", "totalAmount": 10000, "orderId": old_order}
        raise TossApiError(404, '{"code":"NOT_FOUND_PAYMENT"}')

    def charge(billing_key, **kwargs):
        charged.append(kwargs["order_id"])
        raise httpx.TransportError("new order is not approved in this test")

    _patch(monkeypatch, lookup, charge)
    assert ws.renew_due_subscriptions(db, now=NOW) == 0
    assert charged == [new_order]
    assert _row(db, sub_id)["status"] == "pending"
    assert db.execute(text("SELECT count(*) FROM entitlements")).scalar() == 0


def test_same_generation_retry_grants_existing_done_once(db, monkeypatch):
    user_id = _user(db)
    sub_id = _sub(db, user_id)
    db.commit()
    order_id = ws.order_id_for(sub_id, DUE, START)
    charged = []

    def lookup(requested):
        if requested == order_id and charged:
            return {"status": "DONE", "totalAmount": 10000, "orderId": order_id}
        raise TossApiError(404, '{"code":"NOT_FOUND_PAYMENT"}')

    def charge(billing_key, **kwargs):
        charged.append(kwargs["order_id"])
        return {"status": "DONE", "totalAmount": 10000, "orderId": kwargs["order_id"]}

    _patch(monkeypatch, lookup, charge)
    assert ws.renew_due_subscriptions(db, now=NOW) == 1
    assert ws.renew_due_subscriptions(db, now=NOW) == 0
    assert charged == [order_id]
    assert _row(db, sub_id)["status"] == "active"
    assert db.execute(text("SELECT count(*) FROM entitlements WHERE active")).scalar() == 2


def test_missing_created_at_skips_without_toss(db, monkeypatch, caplog):
    user_id = _user(db)
    sub_id = _sub(db, user_id)
    db.commit()
    original = ws._reread

    def hidden(session, sid):
        row = original(session, sid)
        if row is None:
            return None
        data = dict(row)
        data["created_at"] = None
        return data

    monkeypatch.setattr(ws, "_reread", hidden)
    _patch(
        monkeypatch,
        lambda order_id: pytest.fail("lookup"),
        lambda billing_key, **k: pytest.fail("charge"),
    )
    with caplog.at_level("WARNING"):
        assert ws.renew_due_subscriptions(db, now=NOW) == 0
    assert _row(db, sub_id)["status"] == "pending"
    assert "missing created_at" in caplog.text


def test_lookup_rejects_a_different_order_id(monkeypatch):
    monkeypatch.setattr(
        ws,
        "get_payment_by_order",
        lambda order_id: {"status": "DONE", "totalAmount": 10000, "orderId": "ch2-other"},
    )
    assert ws._lookup("ch2-1-1-20261221")[0] == "unknown"
    monkeypatch.setattr(
        ws,
        "get_payment_by_order",
        lambda order_id: {"status": "DONE", "totalAmount": 10000, "orderId": order_id},
    )
    assert ws._lookup("ch2-1-1-20261221")[0] == "approved"
    monkeypatch.setattr(
        ws,
        "get_payment_by_order",
        lambda order_id: {"status": "DONE", "totalAmount": 10000},
    )
    assert ws._lookup("ch2-1-1-20261221")[0] == "approved"
