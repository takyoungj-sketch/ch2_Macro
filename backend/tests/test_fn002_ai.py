"""FN-002 unit 4: policy contracts, one trial period, and displayed/reserved limits."""

import asyncio
import ast
import subprocess
from dataclasses import asdict
from datetime import timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.ai import allowances as quota
from app.config import settings
from app.platform import fieldnote_ai_access as fieldnote
from app.platform import fieldnote_ai_router as route
from app.platform.billing_period import period_end
from test_access_v2 import END, START, USER, ReadDB, subscription


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'unit4.db'}")
    quota.meta.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def v2(monkeypatch):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", "v2")
    monkeypatch.setattr(settings, "ch2_policy_start", START)


@pytest.mark.parametrize("state", ["anonymous", "admin", "trial", "paid", "trial_ended", "payment_processing", "payment_failed"])
def test_fieldnote_contract_matches_shared_decision(v2, state):
    user, now, db = USER, END, ReadDB()
    if state == "anonymous":
        user = None
    elif state == "admin":
        user = SimpleNamespace(id=7, role="admin")
    elif state == "trial":
        now = END - timedelta(seconds=1)
    elif state == "paid":
        db = ReadDB(subs=[subscription(status="active", current_period_end=period_end(END, 1))])
    elif state == "payment_processing":
        db = ReadDB(subs=[subscription()])
    elif state == "payment_failed":
        db = ReadDB(subs=[subscription(status="past_due")])
    access = fieldnote.resolve_fieldnote_ai_access(db, user, now)
    assert set(asdict(access)) == {"tier", "period_start", "period_end", "deny_code"}
    expected_tier = {"anonymous": "none", "trial_ended": "expired", "payment_processing": "expired",
                     "payment_failed": "expired"}.get(state, state)
    assert access.tier == expected_tier
    if state in {"anonymous", "trial_ended", "payment_processing", "payment_failed"}:
        assert access.deny_code == {"anonymous": "login_required", "trial_ended": "trial_ended"}.get(state, "subscription_required")
        assert access.period_start is None and access.period_end is None
        assert quota.grant_for(db, user, now) is None
    elif state == "admin":
        assert (access.period_start, access.period_end) == fieldnote.calendar_month(now)
    else:
        grant = quota.grant_for(db, user, now)
        assert (grant.start, grant.end) == (access.period_start, access.period_end)
        assert grant.plan == ("trial" if state == "trial" else "bundle")


def test_trial_is_one_60_question_period_then_paid_gets_new_period(v2, engine):
    early = quota.grant_for(ReadDB(), USER, START + timedelta(days=1))
    late = quota.grant_for(ReadDB(), USER, END - timedelta(seconds=1))
    assert early == late
    assert (early.start, early.end) == (START, END)
    assert quota.LIMITS["trial"] == {"macro_question": 60}
    ticket = quota.reserve(engine, early, "macro_question", 60, "trial-all", "trial")
    quota.finish(ticket, {"ok": True})
    with pytest.raises(HTTPException) as denied:
        quota.reserve(engine, late, "macro_question", 1, "trial-over", "trial-over")
    assert denied.value.status_code == 429
    assert quota.snapshot(engine, late)["items"][0]["remaining"] == 0
    db = ReadDB(subs=[subscription(status="active", current_period_end=period_end(END, 1))])
    paid = quota.grant_for(db, USER, END)
    assert paid.plan == "bundle" and paid.start == END and paid.end == period_end(END, 1)
    assert quota.snapshot(engine, paid)["items"][0]["remaining"] == 250
    ticket = quota.reserve(engine, paid, "macro_question", 1, "paid-first", "paid")
    quota.finish(ticket, {"ok": True})
    assert quota.snapshot(engine, early)["items"][0]["used"] == 60


@pytest.mark.parametrize("tier", ["trial", "paid", "admin"])
@pytest.mark.parametrize("feature,suffix,limit", [(fieldnote.PHOTO, "photo", 2), (fieldnote.SHEET, "sheet", 3),
                                                (fieldnote.WRITE, "write", 4)])
def test_usage_limit_matches_actual_reservation_for_all_tiers(v2, engine, monkeypatch, tier, feature, suffix, limit):
    monkeypatch.setattr(settings, f"fieldnote_ai_{tier}_monthly_{suffix}", limit)
    now = START + timedelta(days=1) if tier == "trial" else END
    user = SimpleNamespace(id=7, role="admin") if tier == "admin" else USER
    db = ReadDB(subs=[subscription(status="active", current_period_end=period_end(END, 1))] if tier == "paid" else [])
    db.get_bind = lambda: engine
    access = fieldnote.resolve_fieldnote_ai_access(db, user, now)
    grant = quota.Grant(user.id, "admin", access.period_start, access.period_end) if tier == "admin" else quota.grant_for(db, user, now)
    monkeypatch.setattr(route, "resolve_fieldnote_ai_access", lambda *_: access)
    monkeypatch.setattr(quota, "grant_for", lambda *_: grant)
    def item(payload):
        return next(i for i in payload["items"] if i["feature"] == feature)
    assert item(route.fieldnote_allowance(db, user))["limit"] == limit
    ticket = quota.reserve(engine, grant, feature, limit, "last", "last", limit=fieldnote.monthly_limit(feature, tier))
    quota.finish(ticket, {"ok": True})
    for payload in [route.fieldnote_allowance(db, user), route._usage_body(engine, grant, access)]:
        assert (item(payload)["limit"], item(payload)["used"], item(payload)["remaining"]) == (limit, limit, 0)
    with pytest.raises(HTTPException) as denied:
        quota.reserve(engine, grant, feature, 1, "over", "over", limit=fieldnote.monthly_limit(feature, tier))
    assert denied.value.status_code == 429


@pytest.mark.parametrize("user", [None, USER])
@pytest.mark.parametrize("quota_on", [False, True])
def test_v2_anonymous_and_expired_never_reach_provider_or_device(v2, monkeypatch, user, quota_on):
    monkeypatch.setattr(settings, "ai_subscription_quota_enabled", quota_on)
    monkeypatch.setattr(settings, "openai_api_key", "test-placeholder")
    monkeypatch.setattr(route, "resolve_fieldnote_ai_access", lambda db, user: fieldnote.resolve_fieldnote_ai_access(db, user, END))
    monkeypatch.setattr(route.httpx, "AsyncClient", lambda **_: pytest.fail("provider called"))
    monkeypatch.setattr(route, "_check_and_increment_quota", lambda *_: pytest.fail("device path called"))
    body = route.AiProxyRequest(format=2, mode="short", photos=[])
    with pytest.raises(HTTPException) as denied:
        asyncio.run(route._proxy_openai(body, "device-ignored", ReadDB(), kind="short", user=user))
    assert denied.value.status_code == (401 if user is None else 403)
    assert denied.value.detail["code"] == ("login_required" if user is None else "trial_ended")


def _main_function(path, name, namespace):
    # Read only committed source; evaluate only the selected function, not main's settings.
    root = Path(__file__).resolve().parents[2]
    source = subprocess.check_output(["git", "show", f"3e46d81a:{path}"], cwd=root).decode("utf-8")
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    space = dict(namespace)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), space)
    return space[name]


@pytest.mark.parametrize("case", ["free", "fieldnote", "macro", "bundle", "play", "annual", "canceled", "pending", "expired", "upgrade"])
def test_legacy_results_equal_deployed_main_for_same_inputs(engine, monkeypatch, case):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", "legacy")
    monkeypatch.setattr(settings, "ch2_policy_start", None)
    now = (START + timedelta(days=5)).astimezone(timezone.utc)
    created, end = now - timedelta(days=10), now + timedelta(days=21)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE subscriptions (id INTEGER, user_id INTEGER, product TEXT, plan_id TEXT, source TEXT, status TEXT, created_at TEXT, current_period_end TEXT)"))
        conn.execute(text("CREATE TABLE entitlements (user_id INTEGER, product TEXT, active BOOLEAN, expires_at TEXT)"))
        if case != "free":
            for product in (["fieldnote"] if case == "fieldnote" else ["macro"] if case == "macro" else ["macro", "fieldnote"]):
                conn.execute(text("INSERT INTO entitlements VALUES (7,:p,TRUE,NULL)"), {"p": product})
            conn.execute(text("INSERT INTO subscriptions VALUES (1,7,:product,:plan,:source,:status,:created,:end)"), {
                "product": "macro" if case == "macro" else "fieldnote" if case == "fieldnote" else "bundle",
                "plan": "bundle_yearly" if case == "annual" else "bundle_monthly",
                "source": "play" if case == "play" else "web_toss",
                "status": case if case in {"canceled", "pending", "expired"} else "active",
                "created": created, "end": end if case != "expired" else now - timedelta(seconds=1)})
        if case == "upgrade":
            conn.execute(quota.balances.insert().values(user_id=7, feature="macro_question", period_start=now-timedelta(days=7),
                period_end=end-timedelta(days=2), limit_units=200, used=5, reserved=0, policy="old"))
    baseline_grant = _main_function("backend/app/ai/allowances.py", "grant_for", vars(quota))
    baseline_fieldnote = _main_function("backend/app/platform/fieldnote_ai_access.py", "resolve_fieldnote_ai_access", vars(fieldnote))
    baseline_snapshot = _main_function("backend/app/ai/allowances.py", "snapshot", vars(quota))
    current_grant = quota.grant_for
    with Session(engine) as db:
        expected_grant = baseline_grant(db, USER, now)
        actual_grant = current_grant(db, USER, now)
        assert actual_grant == expected_grant
        monkeypatch.setattr(quota, "grant_for", baseline_grant)
        expected_access = baseline_fieldnote(db, USER, now)
        monkeypatch.setattr(quota, "grant_for", current_grant)
        actual_access = fieldnote.resolve_fieldnote_ai_access(db, USER, now)
        assert actual_access == expected_access
        if actual_grant:
            old = baseline_snapshot(engine, expected_grant)
            new = quota.snapshot(engine, actual_grant)
            # POLICY version is an explicit unit-4 change; all allowance values stay equal.
            assert {k:v for k,v in old.items() if k != "policy"} == {k:v for k,v in new.items() if k != "policy"}
        if actual_access.tier == "paid" and actual_grant.plan == "bundle":
            old = baseline_snapshot(engine, expected_grant)
            new = route._usage_body(engine, actual_grant, actual_access)
            assert {k:v for k,v in old.items() if k != "policy"} == {k:v for k,v in new.items() if k != "policy"}
    assert quota.POLICY == "launch-2026-12-v2"
