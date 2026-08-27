"""Play Billing RTDN · 웹 PG(토스) — entitlement 갱신."""

from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.db import get_platform_db
from app.platform.deps import CurrentUser, require_user
from app.platform.entitlements import activate_subscription, create_subscription, list_entitlements

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

PLANS = [
    {"id": "fieldnote_monthly", "product": "fieldnote", "price": 10000, "interval": "month"},
    {"id": "fieldnote_yearly", "product": "fieldnote", "price": 100000, "interval": "year"},
    {"id": "macro_monthly", "product": "macro", "price": 10000, "interval": "month"},
    {"id": "macro_yearly", "product": "macro", "price": 100000, "interval": "year"},
    {"id": "bundle_monthly", "product": "bundle", "price": 15000, "interval": "month"},
    {"id": "bundle_yearly", "product": "bundle", "price": 150000, "interval": "year"},
]
PLANS_BY_ID = {p["id"]: p for p in PLANS}

TOSS_CONFIRM_URL = "https://api.tosspayments.com/v1/payments/confirm"


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


def _period_end_for_plan(plan: dict) -> datetime:
    if plan["interval"] == "year":
        return datetime.now(timezone.utc) + timedelta(days=365)
    return datetime.now(timezone.utc) + timedelta(days=31)


def _basic_auth_toss() -> str:
    raw = f"{settings.toss_secret_key}:"
    return "Basic " + base64.b64encode(raw.encode("utf-8")).decode("ascii")


@router.post("/play/verify")
def verify_play_purchase(
    body: PlayVerifyRequest,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    """Play 구매 검증. 기본은 stub 거부 — PLAY_BILLING_ALLOW_STUB=1 일 때만 부여."""
    product = PLAY_SKU_MAP.get(body.product_id)
    if not product:
        raise HTTPException(400, "unknown_product_id")
    if not settings.play_billing_allow_stub:
        raise HTTPException(
            503,
            "Play Developer API 미연동. 지금은 구매를 확인할 수 없습니다.",
        )
    period_end = _period_end_for_plan(PLANS_BY_ID.get(body.product_id, {"interval": "month"}))
    external_id = f"{body.package_name}:{body.product_id}:{body.purchase_token[:48]}"
    sub_id = create_subscription(
        db,
        user_id=user.id,
        product=product,
        source="play",
        external_id=external_id,
        period_end=period_end,
    )
    ent = list_entitlements(db, user.id)
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
    return {"enabled": bool(key and (settings.toss_secret_key or "").strip()), "clientKey": key or None}


@router.post("/toss/prepare")
def toss_prepare(
    body: TossPrepareRequest,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
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


@router.post("/toss/confirm")
def toss_confirm(
    body: TossConfirmRequest,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
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
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            TOSS_CONFIRM_URL,
            headers={
                "Authorization": _basic_auth_toss(),
                "Content-Type": "application/json",
            },
            json={
                "paymentKey": body.paymentKey,
                "orderId": body.orderId,
                "amount": body.amount,
            },
        )
    if res.status_code >= 400:
        _log.warning("Toss confirm failed status=%s body=%s", res.status_code, res.text[:500])
        raise HTTPException(400, "toss_confirm_failed")
    sub_id = activate_subscription(db, external_id=body.orderId, source="web_toss")
    ent = list_entitlements(db, user.id)
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
