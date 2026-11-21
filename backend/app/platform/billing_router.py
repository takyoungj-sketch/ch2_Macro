"""Play Billing RTDN · 웹 PG(토스) — entitlement 갱신."""

from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.db import get_platform_db
from app.platform.deps import CurrentUser, get_optional_user, require_user
from app.platform.access import resolve_access
from app.platform.entitlements import activate_subscription, create_subscription, list_entitlements, apply_staff_entitlements
from app.platform.toss_client import TossApiError, confirm_payment, toss_configured
from app.platform.web_subscription import (
    ORDER_NAME,
    activate_with_billing_key,
    create_billing_pending,
    ensure_toss_customer_key,
    get_web_subscription,
    has_blocking_subscription,
    set_cancel_at_period_end,
)

router = APIRouter(prefix="/billing", tags=["platform-billing"])
_log = logging.getLogger(__name__)

PLAY_SKU_MAP = {
    "fieldnote_monthly": "fieldnote",
    "fieldnote_yearly": "fieldnote",
    "macro_monthly": "macro",
    "macro_yearly": "macro",
    "bundle_monthly": "bundle",
    "bundle_yearly": "bundle",
}

_LEGACY_PLANS = [
    {"id": "fieldnote_monthly", "product": "fieldnote", "price": 10000, "interval": "month"},
    {"id": "fieldnote_yearly", "product": "fieldnote", "price": 100000, "interval": "year"},
    {"id": "macro_monthly", "product": "macro", "price": 10000, "interval": "month"},
    {"id": "macro_yearly", "product": "macro", "price": 100000, "interval": "year"},
    {"id": "bundle_monthly", "product": "bundle", "price": 15000, "interval": "month"},
    {"id": "bundle_yearly", "product": "bundle", "price": 150000, "interval": "year"},
]
PLANS = [{"id": "ch2_monthly", "product": "bundle", "price": 10000, "interval": "month"}]
PLANS_BY_ID = {p["id"]: p for p in PLANS}
# Historical rows keep their original price in legacy read responses. Not saleable.
_HISTORICAL_PLANS_BY_ID = {p["id"]: p for p in _LEGACY_PLANS + PLANS}


def _play_stub_enabled() -> bool:
    return settings.ch2_deploy_env in {"local", "test"} and settings.play_billing_allow_stub


def _require_play_stub() -> None:
    if not _play_stub_enabled():
        raise HTTPException(410, "play_billing_disabled")


def _single_payment_disabled() -> None:
    raise HTTPException(410, "single_payment_disabled")

class PlayVerifyRequest(BaseModel):
    purchase_token: str = Field(min_length=10)
    product_id: str = Field(min_length=3)
    package_name: str = Field(default="com.ch2data.fieldnote")


class TossWebhookPayload(BaseModel):
    eventType: str | None = None
    data: dict | None = None
    orderId: str | None = None
    product: str | None = None
    user_id: int | None = None
    amount: int | None = None


class TossPrepareRequest(BaseModel):
    plan_id: str


class TossConfirmRequest(BaseModel):
    paymentKey: str = Field(min_length=8)
    orderId: str = Field(min_length=8)
    amount: int = Field(gt=0)


class TossBillingPrepareRequest(BaseModel):
    plan_id: str


class TossBillingActivateRequest(BaseModel):
    auth_key: str = Field(min_length=8)
    customer_key: str = Field(min_length=2)
    pending_id: str = Field(min_length=8)


class SubscriptionCancelRequest(BaseModel):
    cancel_at_period_end: bool = True


def _period_end_for_plan(plan: dict) -> datetime:
    if plan["interval"] == "year":
        return datetime.now(timezone.utc) + timedelta(days=365)
    return datetime.now(timezone.utc) + timedelta(days=31)


@router.post("/play/verify", dependencies=[Depends(_require_play_stub)])
def verify_play_purchase(
    body: PlayVerifyRequest,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    """Stub grants require both an explicit local/test environment and opt-in."""
    _require_play_stub()
    product = PLAY_SKU_MAP.get(body.product_id)
    if not product:
        raise HTTPException(400, "unknown_product_id")
    period_end = _period_end_for_plan(_HISTORICAL_PLANS_BY_ID.get(body.product_id, {"interval": "month"}))
    external_id = f"{body.package_name}:{body.product_id}:{body.purchase_token[:48]}"
    sub_id = create_subscription(
        db,
        user_id=user.id,
        product=product,
        source="play",
        external_id=external_id,
        period_end=period_end,
    )
    ent = apply_staff_entitlements(user.role, list_entitlements(db, user.id))
    return {"ok": True, "subscription_id": sub_id, "entitlements": ent, "stub": True}


@router.post("/play/rtdn")
async def play_rtdn_webhook(request: Request, db: Session = Depends(get_platform_db)):
    """Google Play Real-time Developer Notifications — 로그만 (권한 회수는 Play API 연동 후)."""
    raw = await request.body()
    try:
        envelope = json.loads(raw)
        data_b64 = envelope.get("message", {}).get("data")
        if data_b64:
            payload = json.loads(base64.b64decode(data_b64))
            _log.info("Play RTDN: %s", payload.get("subscriptionNotification", payload))
    except Exception as exc:
        _log.warning("RTDN parse error: %s", exc)
    return {"ok": True}


@router.get("/toss/config")
def toss_config():
    key = (settings.toss_client_key or "").strip()
    return {
        "enabled": toss_configured(),
        "clientKey": key or None,
        "billing": True,
        "play_stub": _play_stub_enabled(),
    }


@router.get("/subscription/me")
def subscription_me(
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    access = resolve_access(db, user)
    sub = get_web_subscription(db, user.id) if access.mode == "legacy" or access.state == "admin" else access.subscription
    ent = access.products
    if not sub:
        return {"active": access.mode == "v2" and access.state in {"trial", "paid", "admin"}, "entitlements": ent}
    plan = _HISTORICAL_PLANS_BY_ID.get(str(sub.get("plan_id") or ""))
    return {
        "active": True if access.mode == "legacy" else access.state in {"trial", "paid", "admin"},
        "product": sub.get("product"),
        "plan_id": sub.get("plan_id"),
        "price": plan["price"] if plan else None,
        "status": sub.get("status"),
        "current_period_end": sub.get("current_period_end") if access.mode == "legacy" else access.period_end,
        "next_billing_at": sub.get("next_billing_at"),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        "entitlements": ent,
    }


@router.get("/status")
def billing_status(
    user: CurrentUser | None = Depends(get_optional_user),
    db: Session = Depends(get_platform_db),
):
    result = resolve_access(db, user).status()
    if settings.ch2_billing_paused:
        result["billing_paused"] = True
    return result


@router.post("/subscription/cancel")
def subscription_cancel(
    body: SubscriptionCancelRequest,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    ok = set_cancel_at_period_end(db, user.id, body.cancel_at_period_end)
    if not ok:
        raise HTTPException(404, "active_subscription_not_found")
    return {"ok": True, "cancel_at_period_end": bool(body.cancel_at_period_end)}


@router.post("/toss/billing/prepare")
def toss_billing_prepare(
    body: TossBillingPrepareRequest,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    if settings.ch2_billing_paused:
        raise HTTPException(503, "billing_paused")
    plan = PLANS_BY_ID.get(body.plan_id)
    if not plan:
        raise HTTPException(400, "unknown_plan")
    if settings.ch2_policy_start is None:
        raise HTTPException(503, "policy_start_missing")
    if not toss_configured():
        raise HTTPException(503, "토스 결제 키가 아직 설정되지 않았습니다.")
    if has_blocking_subscription(db, user.id):
        raise HTTPException(409, "already_subscribed")
    customer_key = ensure_toss_customer_key(db, user.id)
    _, pending_id = create_billing_pending(
        db, user_id=user.id, plan_id=plan["id"], product=plan["product"]
    )
    return {
        "clientKey": settings.toss_client_key,
        "customerKey": customer_key,
        "pendingId": pending_id,
        "planId": plan["id"],
        "amount": plan["price"],
        "orderName": ORDER_NAME,
    }


@router.post("/toss/billing/activate")
def toss_billing_activate(
    body: TossBillingActivateRequest,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    if settings.ch2_billing_paused:
        raise HTTPException(503, "billing_paused")
    if not toss_configured():
        raise HTTPException(503, "토스 결제 키가 아직 설정되지 않았습니다.")
    stored = ensure_toss_customer_key(db, user.id)
    if body.customer_key != stored:
        raise HTTPException(403, "customer_key_mismatch")
    row = db.execute(
        text(
            """
            SELECT plan_id FROM subscriptions
            WHERE source = 'web_toss' AND external_id = :ext AND user_id = :uid
            """
        ),
        {"ext": body.pending_id, "uid": user.id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "pending_not_found")
    plan = PLANS_BY_ID.get(str(row["plan_id"]))
    if not plan:
        raise HTTPException(400, "unknown_plan")
    try:
        result = activate_with_billing_key(
            db,
            user_id=user.id,
            pending_external_id=body.pending_id,
            auth_key=body.auth_key,
            customer_key=body.customer_key,
            amount=plan["price"],
            order_name=ORDER_NAME,
            user_email=user.email,
        )
    except ValueError as exc:
        code = str(exc)
        if code in {"pending_not_found", "not_pending"}:
            raise HTTPException(404, code) from exc
        if code == "forbidden":
            raise HTTPException(403, code) from exc
        if code == "already_subscribed":
            raise HTTPException(409, code) from exc
        if code == "policy_start_missing":
            raise HTTPException(503, code) from exc
        raise HTTPException(400, code) from exc
    except TossApiError as exc:
        _log.warning("billing activate failed status=%s code=%s", exc.status_code, exc.code)
        raise HTTPException(400, "toss_billing_failed") from exc
    ent = apply_staff_entitlements(user.role, list_entitlements(db, user.id))
    return {
        "ok": True,
        "subscription_id": result["id"],
        "outcome": result["outcome"],
        "entitlements": ent,
    }


@router.post("/toss/prepare", dependencies=[Depends(_single_payment_disabled)])
def toss_prepare(
    body: TossPrepareRequest,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    _single_payment_disabled()
    if not (settings.toss_client_key or "").strip() or not (settings.toss_secret_key or "").strip():
        raise HTTPException(503, "토스 결제 키가 아직 설정되지 않았습니다.")
    plan = PLANS_BY_ID.get(body.plan_id)
    if not plan or plan["product"] not in {"macro", "bundle"}:
        raise HTTPException(400, "unknown_plan")
    order_id = f"ch2-{user.id}-{plan['id']}-{int(time.time())}"
    create_subscription(
        db,
        user_id=user.id,
        product=plan["product"],
        source="web_toss",
        external_id=order_id,
        period_end=_period_end_for_plan(plan),
        status="pending",
        grant=False,
    )
    return {
        "orderId": order_id,
        "amount": plan["price"],
        "orderName": f"CH2 {plan['product']} {plan['interval']}",
        "customerKey": f"ch2-user-{user.id}",
        "clientKey": settings.toss_client_key,
    }


@router.post("/toss/confirm", dependencies=[Depends(_single_payment_disabled)])
def toss_confirm(
    body: TossConfirmRequest,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    _single_payment_disabled()
    if not (settings.toss_secret_key or "").strip():
        raise HTTPException(503, "토스 시크릿 키가 없습니다.")
    row = db.execute(
        text(
            """
            SELECT id, user_id, product, status
            FROM subscriptions
            WHERE source = 'web_toss' AND external_id = :oid
            """
        ),
        {"oid": body.orderId},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "order_not_found")
    if int(row["user_id"]) != user.id:
        raise HTTPException(403, "forbidden")
    plan_amount = None
    for plan in PLANS:
        if plan["product"] == row["product"] and abs(plan["price"] - body.amount) < 1:
            plan_amount = plan["price"]
            break
    if plan_amount is None or plan_amount != body.amount:
        raise HTTPException(400, "amount_mismatch")
    try:
        confirm_payment(body.paymentKey, body.orderId, body.amount)
    except TossApiError as exc:
        _log.warning("Toss confirm failed status=%s body=%s", exc.status_code, exc.body[:500])
        raise HTTPException(400, "toss_confirm_failed") from exc
    sub_id = activate_subscription(db, external_id=body.orderId, source="web_toss")
    ent = apply_staff_entitlements(user.role, list_entitlements(db, user.id))
    return {"ok": True, "subscription_id": sub_id, "entitlements": ent}


@router.post("/toss/webhook")
def toss_webhook(
    request: Request,
    body: TossWebhookPayload,
    db: Session = Depends(get_platform_db),
    x_webhook_secret: str | None = Header(default=None, alias="X-Toss-Webhook-Secret"),
):
    """토스 웹훅. 시크릿이 없거나 불일치하면 권한을 부여하지 않는다."""
    expected = (settings.toss_webhook_secret or "").strip()
    if not expected:
        raise HTTPException(503, "toss_webhook_not_configured")
    sent = (x_webhook_secret or request.headers.get("tosspayments-webhook-signature") or "").strip()
    if sent != expected:
        raise HTTPException(401, "invalid_webhook_secret")
    order_id = body.orderId or (body.data or {}).get("orderId")
    if not order_id:
        raise HTTPException(400, "orderId required")
    sub_id = activate_subscription(db, external_id=str(order_id), source="web_toss")
    if not sub_id:
        raise HTTPException(404, "order_not_found")
    return {"ok": True, "subscription_id": sub_id}


@router.get("/plans")
def list_plans():
    return {"currency": "KRW", "plans": PLANS}
