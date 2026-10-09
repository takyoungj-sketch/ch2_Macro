#!/usr/bin/env python3
"""ch2_platform 웹 구독 자동 갱신 — cron에서 1일 1회 이상 실행."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.platform.billing_router import PLANS, PLANS_BY_ID
from app.platform.db import get_platform_session_factory
from app.platform.web_subscription import renew_due_subscriptions


def main() -> int:
    factory = get_platform_session_factory()
    if factory is None:
        print("DATABASE_URL_PLATFORM not configured", file=sys.stderr)
        return 1
    plan_prices = {p["id"]: p["price"] for p in PLANS if p["interval"] == "month"}
    plan_names = {
        p["id"]: f"CH2 {p['product']} month" for p in PLANS if p["interval"] == "month"
    }
    db = factory()
    try:
        n = renew_due_subscriptions(db, plan_prices=plan_prices, plan_names=plan_names)
        print(f"OK: renewed {n}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
