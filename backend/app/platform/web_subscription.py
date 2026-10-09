"""웹(토스) 월 구독 — 빌링키 발급·자동 갱신·해지 예약."""

from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.entitlements import grant_bundle, upsert_entitlement
from app.platform.toss_client import TossApiError, charge_billing, issue_billing_key

_log = logging.getLogger(__name__)

WEB_MONTH_PLAN_IDS = frozenset({"macro_monthly", "bundle_monthly"})


def period_end_monthly(now: datetime | None = None) -> datetime:
    base = now or datetime.now(timezone.utc)
    return base + timedelta(days=31)


def ensure_toss_customer_key(db: Session, user_id: int) -> str:
    row = db.execute(
        text("SELECT toss_customer_key FROM users WHERE id = :uid"),
        {"uid": user_id},
    ).mappings().first()
    if row and row.get("toss_customer_key"):
        return str(row["toss_customer_key"])
    key = f"ch2.{secrets.token_urlsafe(18)}"
    db.execute(
        text("UPDATE users SET toss_customer_key = :k, updated_at = now() WHERE id = :uid"),
        {"k": key, "uid": user_id},
    )
    db.commit()
    return key


def expire_other_web_subs(db: Session, user_id: int, keep_id: int) -> None:
    db.execute(
        text(
            """
            UPDATE subscriptions
            SET status = 'expired', updated_at = now()
            WHERE user_id = :uid AND source = 'web_toss' AND id <> :keep AND status IN ('active', 'pending', 'past_due')
            """
        ),
        {"uid": user_id, "keep": keep_id},
    )


def create_billing_pending(
    db: Session,
    *,
    user_id: int,
    plan_id: str,
    product: str,
) -> tuple[int, str]:
    external_id = f"ch2-bill-prep-{user_id}-{int(time.time())}-{secrets.token_hex(4)}"
    row = db.execute(
        text(
            """
            INSERT INTO subscriptions (
                user_id, product, source, external_id, status,
                plan_id, current_period_end, cancel_at_period_end
            )
            VALUES (:uid, :product, 'web_toss', :ext, 'pending', :plan, NULL, FALSE)
            RETURNING id
            """
        ),
        {"uid": user_id, "product": product, "ext": external_id, "plan": plan_id},
    ).mappings().first()
    db.commit()
    return int(row["id"]), external_id


def activate_with_billing_key(
    db: Session,
    *,
    user_id: int,
    pending_external_id: str,
    auth_key: str,
    customer_key: str,
    amount: int,
    order_name: str,
    user_email: str | None,
) -> int:
    row = db.execute(
        text(
            """
            SELECT id, user_id, product, plan_id, status
            FROM subscriptions
            WHERE source = 'web_toss' AND external_id = :ext
            """
        ),
        {"ext": pending_external_id},
    ).mappings().first()
    if not row:
        raise ValueError("pending_not_found")
    if int(row["user_id"]) != user_id:
        raise ValueError("forbidden")
    if str(row["status"]) != "pending":
        raise ValueError("not_pending")

    issued = issue_billing_key(auth_key, customer_key)
    billing_key = str(issued.get("billingKey") or "")
    if not billing_key:
        raise ValueError("billing_key_missing")

    charge_order_id = f"ch2-{user_id}-{row['plan_id']}-{int(time.time())}"
    charge_billing(
        billing_key,
        customer_key=customer_key,
        amount=amount,
        order_id=charge_order_id,
        order_name=order_name,
        customer_email=user_email,
    )

    period_end = period_end_monthly()
    sub_id = int(row["id"])
    expire_other_web_subs(db, user_id, sub_id)
    db.execute(
        text(
            """
            UPDATE subscriptions
            SET status = 'active',
                external_id = :charge_oid,
                toss_billing_key = :bk,
                current_period_end = :end,
                next_billing_at = :end,
                cancel_at_period_end = FALSE,
                updated_at = now()
            WHERE id = :sid
            """
        ),
        {
            "charge_oid": charge_order_id,
            "bk": billing_key,
            "end": period_end,
            "sid": sub_id,
        },
    )
    product = str(row["product"])
    if product == "bundle":
        grant_bundle(db, user_id=user_id, expires_at=period_end, source_sub_id=sub_id)
    else:
        upsert_entitlement(
            db, user_id=user_id, product=product, expires_at=period_end, source_sub_id=sub_id
        )
    db.commit()
    return sub_id


def get_web_subscription(db: Session, user_id: int) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT id, product, plan_id, status, current_period_end,
                   next_billing_at, cancel_at_period_end, created_at
            FROM subscriptions
            WHERE user_id = :uid AND source = 'web_toss'
              AND status IN ('active', 'past_due')
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).mappings().first()
    if not row:
        return None
    return dict(row)


def set_cancel_at_period_end(db: Session, user_id: int, cancel: bool) -> bool:
    row = get_web_subscription(db, user_id)
    if not row:
        return False
    db.execute(
        text(
            """
            UPDATE subscriptions
            SET cancel_at_period_end = :c, updated_at = now()
            WHERE id = :sid AND user_id = :uid
            """
        ),
        {"c": cancel, "sid": row["id"], "uid": user_id},
    )
    db.commit()
    return True


def renew_due_subscriptions(db: Session, *, plan_prices: dict[str, int], plan_names: dict[str, str]) -> int:
    """next_billing_at이 지난 active 구독에 자동결제 시도. 처리 건수 반환."""
    rows = db.execute(
        text(
            """
            SELECT s.id, s.user_id, s.product, s.plan_id, s.toss_billing_key,
                   u.toss_customer_key, u.email
            FROM subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE s.source = 'web_toss'
              AND s.status = 'active'
              AND s.cancel_at_period_end = FALSE
              AND s.toss_billing_key IS NOT NULL
              AND s.next_billing_at IS NOT NULL
              AND s.next_billing_at <= now()
            """
        )
    ).mappings().all()
    count = 0
    for row in rows:
        plan_id = str(row["plan_id"] or "")
        amount = plan_prices.get(plan_id)
        if amount is None:
            _log.warning("renew skip sub_id=%s unknown plan_id=%s", row["id"], plan_id)
            continue
        customer_key = str(row["toss_customer_key"] or "")
        billing_key = str(row["toss_billing_key"] or "")
        if not customer_key or not billing_key:
            continue
        order_id = f"ch2-renew-{row['user_id']}-{plan_id}-{int(time.time())}"
        order_name = plan_names.get(plan_id, f"CH2 {row['product']} month")
        try:
            charge_billing(
                billing_key,
                customer_key=customer_key,
                amount=amount,
                order_id=order_id,
                order_name=order_name,
                customer_email=str(row["email"] or "") or None,
            )
        except TossApiError as exc:
            _log.warning("renew failed sub_id=%s %s", row["id"], exc.body[:200])
            db.execute(
                text(
                    "UPDATE subscriptions SET status = 'past_due', updated_at = now() WHERE id = :sid"
                ),
                {"sid": row["id"]},
            )
            db.commit()
            continue
        period_end = period_end_monthly()
        sub_id = int(row["id"])
        user_id = int(row["user_id"])
        product = str(row["product"])
        db.execute(
            text(
                """
                UPDATE subscriptions
                SET external_id = :oid,
                    current_period_end = :end,
                    next_billing_at = :end,
                    status = 'active',
                    updated_at = now()
                WHERE id = :sid
                """
            ),
            {"oid": order_id, "end": period_end, "sid": sub_id},
        )
        if product == "bundle":
            grant_bundle(db, user_id=user_id, expires_at=period_end, source_sub_id=sub_id)
        else:
            upsert_entitlement(
                db, user_id=user_id, product=product, expires_at=period_end, source_sub_id=sub_id
            )
        db.commit()
        count += 1
    return count
