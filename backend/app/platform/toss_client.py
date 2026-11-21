"""토스페이먼츠 REST — 빌링키·자동결제 승인·주문 조회."""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings

TOSS_CONFIRM_URL = "https://api.tosspayments.com/v1/payments/confirm"
TOSS_ISSUE_BILLING_URL = "https://api.tosspayments.com/v1/billing/authorizations/issue"
TOSS_ORDER_URL = "https://api.tosspayments.com/v1/payments/orders/{order_id}"
TOSS_DELETE_BILLING_URL = "https://api.tosspayments.com/v1/billing/{billing_key}"
_READ_TIMEOUT = 30.0
_CHARGE_TIMEOUT = 60.0


def _basic_auth() -> str:
    raw = f"{settings.toss_secret_key}:"
    return "Basic " + base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _headers(idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": _basic_auth(), "Content-Type": "application/json"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


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


def delete_billing_key(billing_key: str) -> None:
    url = TOSS_DELETE_BILLING_URL.format(billing_key=quote(billing_key, safe=""))
    with httpx.Client(timeout=_READ_TIMEOUT) as client:
        res = client.delete(url, headers=_headers())
    if res.status_code >= 400:
        raise TossApiError(res.status_code, res.text)


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


def get_payment_by_order(order_id: str) -> dict[str, Any]:
    url = TOSS_ORDER_URL.format(order_id=quote(order_id, safe=""))
    with httpx.Client(timeout=_READ_TIMEOUT) as client:
        res = client.get(url, headers=_headers())
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
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    url = f"https://api.tosspayments.com/v1/billing/{quote(billing_key, safe='')}"
    body: dict[str, Any] = {
        "customerKey": customer_key,
        "amount": amount,
        "orderId": order_id,
        "orderName": order_name,
    }
    if customer_email:
        body["customerEmail"] = customer_email
    with httpx.Client(timeout=_CHARGE_TIMEOUT) as client:
        res = client.post(url, headers=_headers(idempotency_key), json=body)
    if res.status_code >= 400:
        raise TossApiError(res.status_code, res.text)
    return res.json()


class TossApiError(Exception):
    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        self.code = _error_code(body)
        super().__init__(f"toss_api_{status_code}")


def _error_code(body: str) -> str | None:
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return None
    code = data.get("code") if isinstance(data, dict) else None
    return str(code) if code else None
