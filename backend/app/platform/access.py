"""Read-only account access decision; no grants, charges or schema changes."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.billing_period import anchor, aware, current_period
from app.platform.deps import CurrentUser

_log = logging.getLogger(__name__)


def policy_config() -> tuple[str, datetime | None, str | None]:
    mode = settings.ch2_entitlement_mode
    start = settings.ch2_policy_start
    error = "policy_start_missing" if mode == "v2" and start is None else None
    return ("legacy" if error else mode), start, error


def log_policy_config() -> None:
    if policy_config()[2]:
        _log.error("CH2 entitlement configuration error: policy_start_missing; using legacy")


@dataclass(frozen=True)
class Access:
    state: str
    reason: str | None
    mode: str
    server_time: datetime
    config_error: str | None = None
    products: dict[str, bool] = field(default_factory=lambda: {"macro": False, "fieldnote": False})
    trial_ends_at: datetime | None = None
    paid_until: datetime | None = None
    next_billing_at: datetime | None = None
    billing: str = "none"
    cancel_at_period_end: bool = False
    period_start: datetime | None = None
    period_end: datetime | None = None
    subscription: dict | None = None

    @property
    def features(self) -> dict[str, bool]:
        return {"macro_full": self.products["macro"], "map_hub": self.products["fieldnote"],
                "ai": self.products["fieldnote"]}

    @property
    def rejection_code(self) -> str:
        return self.reason if self.reason in {"login_required", "trial_ended"} else "subscription_required"

    def status(self) -> dict:
        offline_until = self.server_time
        if any(self.products.values()):
            offline_until += timedelta(hours=72)
            if self.period_end is not None:
                offline_until = min(offline_until, self.period_end)
        result = {"policy_active": self.mode == "v2", "mode": self.mode, "state": self.state,
                  "reason": self.reason, "features": self.features, "trial_ends_at": self.trial_ends_at,
                  "paid_until": self.paid_until, "next_billing_at": self.next_billing_at,
                  "billing": self.billing, "cancel_at_period_end": self.cancel_at_period_end,
                  "price_krw": 10000, "server_time": self.server_time, "offline_until": offline_until}
        if self.config_error:
            result["config_error"] = self.config_error
        return result


def resolve_access(db: Session | None, user: CurrentUser | None, now: datetime | None = None) -> Access:
    now = aware(now or datetime.now(timezone.utc))
    mode, policy_start, error = policy_config()
    base = {"mode": mode, "server_time": now, "config_error": error}
    if user is None:
        return Access("anonymous", "login_required", **base)
    if user.role == "admin":
        return Access("admin", None, products={"macro": True, "fieldnote": True}, **base)
    if mode == "legacy":
        rows = db.execute(text("SELECT product, active, expires_at FROM entitlements WHERE user_id = :uid"),
                          {"uid": user.id}).mappings().all()
        products = {"macro": False, "fieldnote": False}
        ends = []
        for row in rows:
            product = str(row["product"])
            end = aware(row["expires_at"]) if row["expires_at"] else None
            # Preserve the legacy boundary and per-product grants.
            if product in products and row["active"] and (end is None or end >= now):
                products[product] = True
                if end:
                    ends.append(end)
        opened = any(products.values())
        return Access("paid" if opened else "expired", None if opened else "subscription_required",
                      products=products, paid_until=max(ends) if ends else None,
                      period_end=min(ends) if ends else None, **base)

    created = db.execute(text("SELECT created_at FROM users WHERE id = :uid"),
                         {"uid": user.id}).mappings().first()
    if not created:
        return Access("anonymous", "login_required", **base)
    trial_start = max(aware(created["created_at"]), aware(policy_start))
    trial_end = trial_start + timedelta(days=30)
    # Only a boolean crosses the DB boundary; never load billing credentials.
    rows = db.execute(text("""
        SELECT id, product, plan_id, status, created_at, current_period_end,
               next_billing_at, cancel_at_period_end,
               (toss_billing_key IS NOT NULL AND toss_billing_key <> '') AS has_billing_key
        FROM subscriptions WHERE user_id = :uid AND source = 'web_toss'
        ORDER BY updated_at DESC, id DESC
        """), {"uid": user.id}).mappings().all()
    paid = [r for r in rows if r["status"] == "active" and r["current_period_end"]
            and aware(r["current_period_end"]) > now]
    sub = max(paid, key=lambda r: aware(r["current_period_end"])) if paid else (rows[0] if rows else None)
    billing, next_at, cancel = "none", None, False
    if sub:
        cancel = bool(sub["cancel_at_period_end"])
        next_at = aware(sub["next_billing_at"]) if sub["next_billing_at"] else None
        if sub["status"] == "pending" and sub["has_billing_key"]:
            billing = "scheduled_canceled" if cancel else "scheduled"
        elif sub["status"] == "active" and sub["current_period_end"] and aware(sub["current_period_end"]) > now:
            billing = "active_canceled" if cancel else "active"
        elif sub["status"] == "past_due":
            billing = "failed"
    base.update(trial_ends_at=trial_end, billing=billing, next_billing_at=next_at,
                cancel_at_period_end=cancel, subscription=dict(sub) if sub else None)
    paid_end = aware(paid[0]["current_period_end"]) if paid else None
    if paid:
        paid_end = max(aware(r["current_period_end"]) for r in paid)
    if trial_start <= now < trial_end:
        return Access("trial", None, products={"macro": True, "fieldnote": True}, paid_until=paid_end,
                      period_start=trial_start, period_end=trial_end, **base)
    if paid:
        start, end = current_period(anchor(sub, trial_end), paid_end)
        return Access("paid", None, products={"macro": True, "fieldnote": True}, paid_until=paid_end,
                      period_start=start, period_end=end, **base)
    reason = "trial_ended"
    if sub and sub["status"] in {"pending", "active"} and sub["has_billing_key"] and not cancel and next_at and next_at <= now:
        reason = "payment_processing"
    elif sub and sub["status"] == "past_due":
        reason = "payment_failed"
    elif any(r["status"] in {"active", "past_due", "expired", "canceled"} for r in rows):
        reason = "subscription_required"
    return Access("expired", reason, **base)
