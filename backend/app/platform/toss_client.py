"""토스페이먼츠 REST — 빌링키·자동결제 승인."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.config import settings

TOSS_CONFIRM_URL = "https://api.tosspayments.com/v1/payments/confirm"
TOSS_ISSUE_BILLING_URL = "https://api.tosspayments.com/v1/billing/authorizations/issue"


def _basic_auth() -> str:
    raw = f"{settings.toss_secret_key}:"
    return "Basic " + base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _headers() -> dict[str, str]:
    return {"Authorization": _basic_auth(), "Content-Type": "application/json"}


def toss_configured() -> bool:
    return bool((settings.toss_client_key or "").strip() and (settings.toss_secret_key or "").strip())


def issue_billing_key(auth_key: str, customer_key: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            TOSS_ISSUE_BILLING_URL,
            headers=_headers(),
            json={"authKey": auth_key, "customerKey": customer_key},
        )
    if res.status_code >= 400:
        raise TossApiError(res.status_code, res.text)
    return res.json()


def confirm_payment(payment_key: str, order_id: str, amount: int) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            TOSS_CONFIRM_URL,
            headers=_headers(),
            json={"paymentKey": payment_key, "orderId": order_id, "amount": amount},
        )
    if res.status_code >= 400:
        raise TossApiError(res.status_code, res.text)
    return res.json()


def charge_billing(
    billing_key: str,
    *,
    customer_key: str,
    amount: int,
    order_id: str,
    order_name: str,
    customer_email: str | None = None,
) -> dict[str, Any]:
    url = f"https://api.tosspayments.com/v1/billing/{billing_key}"
    body: dict[str, Any] = {
        "customerKey": customer_key,
        "amount": amount,
        "orderId": order_id,
        "orderName": order_name,
    }
    if customer_email:
        body["customerEmail"] = customer_email
    with httpx.Client(timeout=30.0) as client:
        res = client.post(url, headers=_headers(), json=body)
    if res.status_code >= 400:
        raise TossApiError(res.status_code, res.text)
    return res.json()


class TossApiError(Exception):
    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"toss_api_{status_code}")
