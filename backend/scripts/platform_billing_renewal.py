#!/usr/bin/env python3
"""ch2_platform 웹 구독 자동 갱신. 운영 cron은 10분 주기이며 이 스크립트는 설치하지 않는다."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.platform.db import get_platform_session_factory
from app.platform.web_subscription import renew_due_subscriptions


def main() -> int:
    factory = get_platform_session_factory()
    if factory is None:
        print("DATABASE_URL_PLATFORM not configured", file=sys.stderr)
        return 1
    db = factory()
    try:
        n = renew_due_subscriptions(db)
        print(f"OK: renewed {n}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
