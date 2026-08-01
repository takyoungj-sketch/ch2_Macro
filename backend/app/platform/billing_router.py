"""Play Billing RTDN · 웹 PG(토스) webhook — entitlement 갱신."""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.db import get_platform_db
from app.platform.deps import CurrentUser, require_user
from app.platform.entitlements import create_subscription, list_entitlements

router = APIRouter(prefix="/billing", tags=["platform-billing"])
_log = logging.getLogger(__name__)

# Play subscription SKU → product mapping (Play Console와 동기)
PLAY_SKU_MAP = {
    "fieldnote_monthly": "fieldnote",
    "fieldnote_yearly": "fieldnote",
    "macro_monthly": "macro",
    "macro_yearly": "macro",
    "bundle_monthly": "bundle",
    "bundle_yearly": "bundle",
}


class PlayVerifyRequest(BaseModel):
    purchase_token: str = Field(min_length=10)
    product_id: str = Field(min_length=3)
    package_name: str = Field(default="com.ch2data.fieldnote")


class TossWebhookPayload(BaseModel):
    orderId: str
    product: str = Field(description="fieldnote | macro | bundle")
    user_id: int
    amount: int | None = None


def _period_end_yearly() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=365)


def _period_end_monthly() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=31)


@router.post("/play/verify")
def verify_play_purchase(
    body: PlayVerifyRequest,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    """클라이언트 Play Billing 구매 후 서버 검증(스텁 — Play Developer API 연동 전 entitlement 부여)."""
    product = PLAY_SKU_MAP.get(body.product_id)
    if not product:
        raise HTTPException(400, "unknown_product_id")
    period_end = _period_end_yearly() if "yearly" in body.product_id else _period_end_monthly()
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
    return {"ok": True, "subscription_id": sub_id, "entitlements": ent}


@router.post("/play/rtdn")
async def play_rtdn_webhook(request: Request, db: Session = Depends(get_platform_db)):
    """Google Play Real-time Developer Notifications (Pub/Sub push body)."""
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


@router.post("/toss/webhook")
def toss_webhook(body: TossWebhookPayload, db: Session = Depends(get_platform_db)):
    """토스페이먼츠 결제 완료 webhook (Macro 웹 — 서명 검증은 운영 시 추가)."""
    if body.product not in {"fieldnote", "macro", "bundle"}:
        raise HTTPException(400, "invalid_product")
    user = db.execute(
        text("SELECT id FROM users WHERE id=:id"),
        {"id": body.user_id},
    ).first()
    if not user:
        raise HTTPException(404, "user_not_found")
    period_end = _period_end_yearly()
    sub_id = create_subscription(
        db,
        user_id=body.user_id,
        product=body.product,
        source="web_toss",
        external_id=body.orderId,
        period_end=period_end,
    )
    return {"ok": True, "subscription_id": sub_id}


@router.get("/plans")
def list_plans():
    return {
        "currency": "KRW",
        "plans": [
            {"id": "fieldnote_monthly", "product": "fieldnote", "price": 10000, "interval": "month"},
            {"id": "fieldnote_yearly", "product": "fieldnote", "price": 100000, "interval": "year"},
            {"id": "macro_monthly", "product": "macro", "price": 10000, "interval": "month"},
            {"id": "macro_yearly", "product": "macro", "price": 100000, "interval": "year"},
            {"id": "bundle_monthly", "product": "bundle", "price": 15000, "interval": "month"},
            {"id": "bundle_yearly", "product": "bundle", "price": 150000, "interval": "year"},
        ],
    }
