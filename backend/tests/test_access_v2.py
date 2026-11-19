"""FN-002: deterministic policy decisions, without database connections."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.config import Settings, settings
from app.platform.access import log_policy_config, resolve_access
from app.platform.billing_period import KST, anchor, current_period, next_period_end, period_end
from app.platform.deps import CurrentUser

START = datetime(2026, 12, 1, tzinfo=KST)
END = START + timedelta(days=30)
USER = CurrentUser(7, "member@example.invalid", "member", "member")


class ReadDB:
    def __init__(self, created=START - timedelta(days=100), subs=(), ent=()):
        self.created, self.subs, self.ent = created, list(subs), list(ent)

    def execute(self, sql, params=None):
        query = str(sql)
        assert query.lstrip().startswith("SELECT")
        assert params == {"uid": USER.id}
        if "FROM users" in query:
            rows = [{"created_at": self.created}] if self.created else []
        elif "FROM subscriptions" in query:
            assert "AS has_billing_key" in query
            rows = self.subs
        elif "FROM entitlements" in query:
            rows = self.ent
        else:
            raise AssertionError(query)
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows, first=lambda: rows[0] if rows else None))


def subscription(**kwargs):
    return dict(id=1, product="bundle", plan_id="ch2_monthly", status="pending", created_at=START,
                current_period_end=None, next_billing_at=END, cancel_at_period_end=False,
                has_billing_key=True, **kwargs) if not kwargs else {
                    **subscription(), **kwargs}


@pytest.fixture(autouse=True)
def policy(monkeypatch):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", "v2")
    monkeypatch.setattr(settings, "ch2_policy_start", START)


def test_defaults_do_not_activate_policy_or_stub():
    config = Settings(_env_file=None, CH2_ENTITLEMENT_MODE="legacy", CH2_DEPLOY_ENV="production")
    assert config.ch2_entitlement_mode == "legacy"
    assert config.ch2_deploy_env == "production"


def test_anonymous_and_admin_never_need_db():
    denied = resolve_access(None, None, END)
    assert (denied.state, denied.reason) == ("anonymous", "login_required")
    assert denied.status()["offline_until"] == END
    assert not any(denied.features.values())
    admin = resolve_access(None, CurrentUser(8, "a@example.invalid", "a", "admin"), END)
    assert admin.state == "admin" and all(admin.features.values())
    assert admin.status()["offline_until"] == END + timedelta(hours=72)


@pytest.mark.parametrize("created", [START - timedelta(days=400), START, START + timedelta(days=3)])
def test_trial_uses_max_and_exact_boundary(created):
    trial_start = max(created, START)
    end = trial_start + timedelta(days=30)
    db = ReadDB(created)
    before = resolve_access(db, USER, end - timedelta(seconds=1))
    assert before.state == "trial" and before.trial_ends_at == end
    assert before.period_start == trial_start
    assert before.status()["offline_until"] == end
    for now in [end, end + timedelta(seconds=1)]:
        denied = resolve_access(db, USER, now)
        assert denied.state == "expired" and denied.reason == "trial_ended"
        assert not any(denied.features.values())


@pytest.mark.parametrize("cancel,billing", [(False, "scheduled"), (True, "scheduled_canceled")])
def test_card_registration_is_not_paid_and_does_not_shorten_trial(cancel, billing):
    db = ReadDB(subs=[subscription(cancel_at_period_end=cancel)])
    before = resolve_access(db, USER, END - timedelta(hours=1))
    assert before.state == "trial" and before.billing == billing and before.paid_until is None
    after = resolve_access(db, USER, END)
    assert after.state == "expired" and not any(after.features.values())
    assert after.reason == ("trial_ended" if cancel else "payment_processing")
    assert after.rejection_code in {"trial_ended", "subscription_required"}


def test_pending_without_key_is_none():
    access = resolve_access(ReadDB(subs=[subscription(has_billing_key=False)]), USER, END)
    assert access.billing == "none" and access.reason == "trial_ended"


@pytest.mark.parametrize("cancel", [False, True])
def test_only_active_unexpired_is_paid(cancel):
    end = period_end(END, 1)
    db = ReadDB(subs=[subscription(status="active", current_period_end=end, next_billing_at=end,
                                   cancel_at_period_end=cancel)])
    paid = resolve_access(db, USER, END)
    assert paid.state == "paid" and all(paid.features.values())
    assert (paid.period_start, paid.period_end) == (END, end)
    assert paid.billing == ("active_canceled" if cancel else "active")
    assert paid.status()["offline_until"] == END + timedelta(hours=72)
    assert resolve_access(db, USER, end).state == "expired"


@pytest.mark.parametrize("status,reason", [("past_due", "payment_failed"), ("expired", "subscription_required"),
                                          ("canceled", "subscription_required")])
def test_denial_reasons_are_separate_from_compatible_code(status, reason):
    access = resolve_access(ReadDB(subs=[subscription(status=status)]), USER, END)
    assert access.state == "expired" and access.reason == reason
    assert access.rejection_code == "subscription_required"


def test_existing_legacy_grants_do_not_leak_into_v2():
    ent = [{"product": "macro", "active": True, "expires_at": None}]
    assert not resolve_access(ReadDB(ent=ent), USER, END).products["macro"]


def test_missing_policy_falls_back_and_logs(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ch2_policy_start", None)
    access = resolve_access(ReadDB(ent=[{"product": "macro", "active": True, "expires_at": None}]), USER, END)
    assert access.mode == "legacy" and access.products == {"macro": True, "fieldnote": False}
    assert access.status()["config_error"] == "policy_start_missing"
    assert access.status()["policy_active"] is False
    log_policy_config()
    assert "policy_start_missing" in caplog.text


def test_legacy_preserves_each_product_and_expiry_boundary(monkeypatch):
    monkeypatch.setattr(settings, "ch2_entitlement_mode", "legacy")
    db = ReadDB(ent=[{"product": "macro", "active": True, "expires_at": END},
                     {"product": "fieldnote", "active": True, "expires_at": END - timedelta(seconds=1)}])
    access = resolve_access(db, USER, END)
    assert access.products == {"macro": True, "fieldnote": False}
    assert resolve_access(db, USER, END + timedelta(microseconds=1)).state == "expired"


@pytest.mark.parametrize("year,feb", [(2026, 28), (2028, 29)])
def test_calendar_anchor_does_not_drift(year, feb):
    start = datetime(year, 1, 31, 0, 25, tzinfo=KST)
    assert [period_end(start, k).day for k in (1, 2, 3)] == [feb, 31, 30]
    assert next_period_end(start, period_end(start, 1)) == period_end(start, 2)
    assert next_period_end(start, period_end(start, 2) + timedelta(days=4)) == period_end(start, 3)
    assert current_period(start, period_end(start, 2)) == (period_end(start, 1), period_end(start, 2))
    # UTC is still Jan 30; calendar calculations must use the Jan 31 KST anchor.
    assert period_end(start.astimezone(timezone.utc), 2).day == 31
    assert anchor({"created_at": start - timedelta(days=2)}, start) == start
    assert anchor({"created_at": start + timedelta(days=2)}, start) == start + timedelta(days=2)
