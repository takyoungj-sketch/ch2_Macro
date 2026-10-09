"""웹 구독 빌링 헬퍼."""

from datetime import datetime, timezone

from app.platform.web_subscription import period_end_monthly, WEB_MONTH_PLAN_IDS


def test_web_month_plan_ids():
    assert "macro_monthly" in WEB_MONTH_PLAN_IDS
    assert "bundle_monthly" in WEB_MONTH_PLAN_IDS
    assert "macro_yearly" not in WEB_MONTH_PLAN_IDS


def test_period_end_monthly():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = period_end_monthly(start)
    assert (end - start).days == 31
