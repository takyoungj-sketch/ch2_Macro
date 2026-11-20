"""웹(토스) 월 구독 — 빌링키 발급·자동 갱신·해지 예약.

청구는 설계 §3.2다. 조회 → 해지 확인 → 청구. 토스 호출은 트랜잭션 밖에서 하고,
반영 UPDATE는 cancel_at_period_end를 건드리지 않는다.
"""

from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.billing_period import KST, anchor, aware, next_period_end
from app.platform.entitlements import grant_bundle, upsert_entitlement
from app.platform.toss_client import TossApiError, charge_billing, get_payment_by_order, issue_billing_key

_log = logging.getLogger(__name__)

WEB_MONTH_PLAN_IDS = frozenset({"macro_monthly", "bundle_monthly"})
PLAN_ID = "ch2_monthly"
PRICE_KRW = 10000
ORDER_NAME = "CH2 월 구독"
ADVISORY_NS = 6006
_DECLINED_STATUSES = frozenset({"ABORTED", "EXPIRED", "CANCELED"})
_DECLINE_CODES = frozenset({
    "INVALID_STOPPED_CARD",
    "INVALID_REJECT_CARD",
    "INVALID_CARD_EXPIRATION",
    "INVALID_CARD_NUMBER",
    "INVALID_BILL_KEY_REQUEST",
    "NOT_SUPPORTED_CARD_TYPE",
    "NOT_SUPPORTED_INSTALLMENT_PLAN_CARD_OR_MERCHANT",
    "INVALID_CARD_INSTALLMENT_PLAN",
    "NOT_MATCHES_CUSTOMER_KEY",
    "BELOW_MINIMUM_AMOUNT",
    "NOT_REGISTERED_CARD_COMPANY",
    "NOT_SUPPORTED_MONTHLY_INSTALLMENT_PLAN",
    "INVALID_CARD_LOST_OR_STOLEN",
    "REJECT_CARD_PAYMENT",
    "REJECT_ACCOUNT_PAYMENT",
    "REJECT_CARD_COMPANY",
    "EXCEED_MAX_AUTH_COUNT",
    "KYC_BLOCKED",
})


def period_end_monthly(now: datetime | None = None) -> datetime:
    """옛 31일 계산. 새 청구 기간은 billing_period.py만 쓴다."""
    base = now or datetime.now(timezone.utc)
    return base + timedelta(days=31)


def order_id_for(sub_id: int, due_at: datetime) -> str:
    day = aware(due_at).astimezone(KST).strftime("%Y%m%d")
    return f"ch2-{int(sub_id)}-{day}"


def trial_end_for(created_at: datetime) -> datetime | None:
    start = settings.ch2_policy_start
    if start is None:
        return None
    return max(aware(created_at), aware(start)) + timedelta(days=30)


def interpret_lookup(*, payment: dict | None = None, error_code: str | None = None, transport: bool = False) -> str:
    if transport:
        return "unknown"
    if error_code == "NOT_FOUND_PAYMENT":
        return "absent"
    if error_code or not payment:
        return "unknown"
    status = str(payment.get("status") or "")
    try:
        amount = int(payment.get("totalAmount"))
    except (TypeError, ValueError):
        amount = None
    if status == "DONE" and amount == PRICE_KRW:
        return "approved"
    if status in _DECLINED_STATUSES:
        return "declined"
    return "unknown"


def interpret_charge_failure(status_code: int, error_code: str | None) -> str:
    if status_code in {400, 403} and error_code in _DECLINE_CODES:
        return "declined"
    return "unknown"


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
            WHERE user_id = :uid AND source = 'web_toss' AND id <> :keep
              AND status IN ('active', 'pending', 'past_due')
            """
        ),
        {"uid": user_id, "keep": keep_id},
    )


def has_blocking_subscription(db: Session, user_id: int) -> bool:
    """해지 예약이 없는 R2/R3가 있으면 새 카드 등록을 막는다."""
    row = db.execute(
        text(
            """
            SELECT id FROM subscriptions
            WHERE user_id = :uid AND source = 'web_toss' AND cancel_at_period_end = FALSE
              AND (
                (status = 'pending' AND toss_billing_key IS NOT NULL AND toss_billing_key <> '')
                OR status = 'active'
              )
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).first()
    db.rollback()
    return row is not None


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
    now: datetime | None = None,
) -> dict:
    now = aware(now or datetime.now(timezone.utc))
    row = db.execute(
        text(
            """
            SELECT s.id, s.user_id, s.product, s.plan_id, s.status, u.created_at
            FROM subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE s.source = 'web_toss' AND s.external_id = :ext
            """
        ),
        {"ext": pending_external_id},
    ).mappings().first()
    db.rollback()
    if not row:
        raise ValueError("pending_not_found")
    if int(row["user_id"]) != user_id:
        raise ValueError("forbidden")
    if str(row["status"]) != "pending":
        raise ValueError("not_pending")
    if int(amount) != PRICE_KRW or order_name != ORDER_NAME:
        raise ValueError("plan_not_billable")
    trial_end = trial_end_for(row["created_at"])
    if trial_end is None:
        raise ValueError("policy_start_missing")

    issued = issue_billing_key(auth_key, customer_key)
    billing_key = str(issued.get("billingKey") or "")
    if not billing_key:
        raise ValueError("billing_key_missing")
    due = trial_end if now < trial_end else now
    saved = db.execute(
        text(
            """
            UPDATE subscriptions
            SET toss_billing_key = :bk, next_billing_at = :due, updated_at = now()
            WHERE id = :sid AND user_id = :uid AND source = 'web_toss' AND status = 'pending'
              AND (toss_billing_key IS NULL OR toss_billing_key = '')
              AND NOT EXISTS (
                SELECT 1 FROM subscriptions o
                WHERE o.user_id = :uid AND o.id <> :sid AND o.source = 'web_toss'
                  AND o.cancel_at_period_end = FALSE
                  AND (
                    (o.status = 'pending' AND o.toss_billing_key IS NOT NULL AND o.toss_billing_key <> '')
                    OR o.status = 'active'
                  )
              )
            """
        ),
        {"bk": billing_key, "due": due, "sid": int(row["id"]), "uid": user_id},
    )
    if saved.rowcount != 1:
        db.rollback()
        raise ValueError("already_subscribed")
    db.commit()
    if now < trial_end:
        return {"id": int(row["id"]), "outcome": "scheduled"}
    outcome = _process_due(db, int(row["id"]), now)
    return {"id": int(row["id"]), "outcome": outcome}


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
    """R2·R3의 해지 예약. 행 잠금이나 토스 호출을 기다리지 않는다."""
    row = db.execute(
        text(
            """
            SELECT id FROM subscriptions
            WHERE user_id = :uid AND source = 'web_toss' AND status IN ('pending', 'active')
              AND (
                status = 'active'
                OR (toss_billing_key IS NOT NULL AND toss_billing_key <> '')
              )
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).first()
    if not row:
        db.rollback()
        return False
    db.execute(
        text(
            """
            UPDATE subscriptions
            SET cancel_at_period_end = :c, updated_at = now()
            WHERE id = :sid AND user_id = :uid
            """
        ),
        {"c": cancel, "sid": row[0], "uid": user_id},
    )
    db.commit()
    return True


def renew_due_subscriptions(db: Session, *, now: datetime | None = None) -> int:
    """next_billing_at이 지난 R2/R3를 조회 먼저로 처리한다. 반영 건수를 반환한다."""
    now = aware(now or datetime.now(timezone.utc))
    ids = db.execute(
        text(
            """
            SELECT id FROM subscriptions
            WHERE source = 'web_toss'
              AND status IN ('pending', 'active')
              AND toss_billing_key IS NOT NULL AND toss_billing_key <> ''
              AND next_billing_at IS NOT NULL AND next_billing_at <= :now
            ORDER BY id
            """
        ),
        {"now": now},
    ).scalars().all()
    db.rollback()
    granted = 0
    for sub_id in ids:
        if _process_due(db, int(sub_id), now) == "approved":
            granted += 1
    return granted


def _process_due(db: Session, sub_id: int, now: datetime) -> str:
    if not _try_lock(db, sub_id):
        return "skipped"
    locked = True
    try:
        row = _reread(db, sub_id)
        db.rollback()
        if row is None or not _still_due(row, now):
            return "skipped"
        plan_id = str(row["plan_id"] or "")
        if plan_id != PLAN_ID:
            _log.warning("renew skip sub_id=%s unknown plan_id=%s", sub_id, plan_id)
            return "skipped"
        customer_key = str(row["toss_customer_key"] or "")
        billing_key = str(row["toss_billing_key"] or "")
        if not customer_key or not billing_key:
            _log.warning("renew skip sub_id=%s missing billing customer", sub_id)
            return "skipped"
        due = aware(row["next_billing_at"])
        order_id = order_id_for(sub_id, due)
        kind, payment = _lookup(order_id)
        if kind == "absent" and bool(row["cancel_at_period_end"]):
            _mark_expired(db, row)
            return "expired"
        if kind == "unknown":
            _warn_if_stale(sub_id, order_id, due, now)
            return "unknown"
        if kind == "approved":
            return "approved" if _grant(db, row, order_id) else "unknown"
        if kind == "declined":
            _mark_past_due(db, row)
            return "declined"
        try:
            payment = charge_billing(
                billing_key,
                customer_key=customer_key,
                amount=PRICE_KRW,
                order_id=order_id,
                order_name=ORDER_NAME,
                customer_email=str(row["email"] or "") or None,
                idempotency_key=order_id,
            )
        except TossApiError as exc:
            if interpret_charge_failure(exc.status_code, exc.code) == "declined":
                _mark_past_due(db, row)
                return "declined"
            _warn_if_stale(sub_id, order_id, due, now)
            return "unknown"
        except httpx.TransportError:
            _warn_if_stale(sub_id, order_id, due, now)
            return "unknown"
        charged = interpret_lookup(payment=payment)
        if charged == "approved":
            fresh = _reread(db, sub_id)
            db.rollback()
            if fresh is None:
                return "unknown"
            return "approved" if _grant(db, fresh, order_id) else "unknown"
        if charged == "declined":
            _mark_past_due(db, row)
            return "declined"
        _warn_if_stale(sub_id, order_id, due, now)
        return "unknown"
    finally:
        if locked:
            _unlock(db, sub_id)


def _lookup(order_id: str) -> tuple[str, dict | None]:
    try:
        payment = get_payment_by_order(order_id)
    except TossApiError as exc:
        return interpret_lookup(error_code=exc.code), None
    except httpx.TransportError:
        return "unknown", None
    return interpret_lookup(payment=payment), payment


def _still_due(row, now: datetime) -> bool:
    if str(row["status"]) not in {"pending", "active"}:
        return False
    if not str(row["toss_billing_key"] or ""):
        return False
    due = row["next_billing_at"]
    return due is not None and aware(due) <= now


def _reread(db: Session, sub_id: int):
    return db.execute(
        text(
            """
            SELECT s.id, s.user_id, s.product, s.plan_id, s.status, s.created_at,
                   s.current_period_end, s.next_billing_at, s.cancel_at_period_end,
                   s.toss_billing_key, u.toss_customer_key, u.email, u.created_at AS user_created_at
            FROM subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE s.id = :sid AND s.source = 'web_toss'
            """
        ),
        {"sid": sub_id},
    ).mappings().first()


def _try_lock(db: Session, sub_id: int) -> bool:
    locked = db.execute(
        text("SELECT pg_try_advisory_lock(:ns, CAST(:sid AS integer))"),
        {"ns": ADVISORY_NS, "sid": sub_id},
    ).scalar()
    db.commit()
    return bool(locked)


def _unlock(db: Session, sub_id: int) -> None:
    db.execute(
        text("SELECT pg_advisory_unlock(:ns, CAST(:sid AS integer))"),
        {"ns": ADVISORY_NS, "sid": sub_id},
    )
    db.commit()


def _grant(db: Session, row, order_id: str) -> bool:
    trial_end = trial_end_for(row["user_created_at"])
    if trial_end is None:
        _log.error("billing grant skipped sub_id=%s policy_start_missing", row["id"])
        return False
    due = aware(row["next_billing_at"])
    old_end = aware(row["current_period_end"]) if row["current_period_end"] else due
    period_end = next_period_end(anchor({"created_at": row["created_at"]}, trial_end), old_end)
    try:
        updated = db.execute(
            text(
                """
                UPDATE subscriptions
                SET status = 'active', external_id = :oid, current_period_end = :end,
                    next_billing_at = :end, updated_at = now()
                WHERE id = :sid AND status = :status AND next_billing_at = :due
                """
            ),
            {
                "oid": order_id,
                "end": period_end,
                "sid": int(row["id"]),
                "status": row["status"],
                "due": row["next_billing_at"],
            },
        )
        if updated.rowcount != 1:
            db.rollback()
            _log.warning("billing grant skipped sub_id=%s row changed", row["id"])
            return False
        sub_id = int(row["id"])
        user_id = int(row["user_id"])
        expire_other_web_subs(db, user_id, sub_id)
        if str(row["product"]) == "bundle":
            grant_bundle(db, user_id=user_id, expires_at=period_end, source_sub_id=sub_id)
        else:
            upsert_entitlement(
                db, user_id=user_id, product=str(row["product"]), expires_at=period_end, source_sub_id=sub_id
            )
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        _log.warning("billing grant conflict sub_id=%s order_id=%s", row["id"], order_id)
        return False


def _mark_past_due(db: Session, row) -> None:
    db.execute(
        text(
            """
            UPDATE subscriptions
            SET status = 'past_due', updated_at = now()
            WHERE id = :sid AND status = :status AND next_billing_at = :due
            """
        ),
        {"sid": int(row["id"]), "status": row["status"], "due": row["next_billing_at"]},
    )
    db.commit()


def _mark_expired(db: Session, row) -> None:
    db.execute(
        text(
            """
            UPDATE subscriptions
            SET status = 'expired', updated_at = now()
            WHERE id = :sid AND status = :status AND next_billing_at = :due
              AND cancel_at_period_end = TRUE
            """
        ),
        {"sid": int(row["id"]), "status": row["status"], "due": row["next_billing_at"]},
    )
    db.commit()


def _warn_if_stale(sub_id: int, order_id: str, due: datetime, now: datetime) -> None:
    if due <= now - timedelta(hours=24):
        _log.warning("billing result unknown for over 24h sub_id=%s order_id=%s", sub_id, order_id)
