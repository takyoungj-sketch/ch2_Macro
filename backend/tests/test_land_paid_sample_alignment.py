from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app import land_stats_snapshot
from app.land_regression import _prepare_df
from app.routers import paid
from app.schemas import LandRegressionRequest, MatrixYearlyRequest, PaidAnalysisRequest
from app.stats_utils import outlier_keep_mask


@pytest.mark.parametrize("start,end", [(date(2026, 1, 1), None), (date(2026, 2, 1), date(2026, 1, 1))])
def test_paid_rejects_invalid_rolling_bounds(start, end):
    req = PaidAnalysisRequest(rolling_matrix_period_start=start, rolling_matrix_period_end=end)
    with pytest.raises(HTTPException) as exc:
        paid._effective_paid_request(req)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("exclude_outlier", [False, True])
def test_paid_analysis_sql_honors_rolling_dates(monkeypatch, exclude_outlier):
    start, end = date(2024, 11, 1), date(2026, 10, 31)
    req = paid._effective_paid_request(PaidAnalysisRequest(
        years=[2023], rolling_matrix_period_start=start,
        rolling_matrix_period_end=end, exclude_outlier=exclude_outlier,
    ))

    class QueryCaptured(Exception):
        pass

    def capture_query(db, sql, params):
        assert "lt.contract_date >= :rolling_ps" in sql
        assert "lt.contract_date <= :rolling_pe" in sql
        assert "lt.contract_year = :filter_year" not in sql
        assert (params["rolling_ps"], params["rolling_pe"]) == (start, end)
        raise QueryCaptured

    monkeypatch.setattr(paid, "_paid_execute", capture_query)
    monkeypatch.setattr(paid, "expand_to_ledger_codes", lambda db, codes: codes)
    with pytest.raises(QueryCaptured):
        paid._analyze_core(req, resolved_codes=["4377025626"], db=Mock())


def test_rolling_trend_filters_whole_cell_before_splitting(monkeypatch):
    first, second = date(2025, 1, 1), date(2026, 1, 1)
    points = [SimpleNamespace(d=first, px=p) for p in [1, 2, 2, 2, 3, 3, 3, 5]]
    points.append(SimpleNamespace(d=second, px=10))
    monkeypatch.setattr(paid, "_matrix_cell_merged_where", lambda body, db: ("TRUE", {}))
    monkeypatch.setattr(paid, "_paid_execute", lambda *args: Mock(fetchall=lambda: points))
    body = MatrixYearlyRequest(
        zone_type="농림", land_category="임", rolling_matrix_period_start=first,
        rolling_matrix_period_end=date(2026, 12, 31), rolling_bucket_count=2,
        exclude_outlier=True, outlier_iqr_multiplier=1.5,
    )
    trend = paid.matrix_yearly(body, db=Mock())
    assert [bucket.count for bucket in trend.rows] == [7, 0]


def test_regression_does_not_trim_an_already_filtered_cell_twice():
    prices = [1, 2, 2, 2, 3, 3, 3, 5, 8, 10, 30]
    rows = [
        {"unit_price_per_sqm": p, "area_sqm": 200, "contract_year": 2026}
        for p, keep in zip(prices, outlier_keep_mask(prices, iqr_multiplier=1.5)) if keep
    ]
    req = LandRegressionRequest(
        zone_type="농림", land_category="임", exclude_outlier=True,
        exclude_outliers_iqr=True, outlier_iqr_multiplier=1.5,
    )
    df, _ = _prepare_df(rows, req)
    assert len(df) == len(rows) == 10

    local_only, _ = _prepare_df(rows, req.model_copy(update={"exclude_outlier": False}))
    assert len(local_only) < len(rows)


def test_latest_completed_month_and_explicit_override(monkeypatch):
    old_month, published = date(2026, 9, 1), date(2026, 10, 1)
    monkeypatch.setattr(land_stats_snapshot, "settings", SimpleNamespace(
        stats_v2_default_as_of_month=None, stats_v2_assumed_today=None,
    ))
    monkeypatch.setattr(
        land_stats_snapshot, "latest_land_stats_publication",
        lambda db: (published, datetime(2026, 11, 8, tzinfo=timezone.utc)),
    )
    assert land_stats_snapshot.preferred_land_stats_month(Mock(), None) == published
    assert land_stats_snapshot.preferred_land_stats_month(Mock(), old_month) == old_month


def test_paid_cache_changes_when_the_same_month_is_republished():
    req = PaidAnalysisRequest(years=[2026])
    month = date(2026, 10, 1)
    previous = paid._make_cache_key(req, as_of=month, published_at=datetime(2026, 11, 8, tzinfo=timezone.utc))
    current = paid._make_cache_key(req, as_of=month, published_at=datetime(2026, 11, 9, tzinfo=timezone.utc))
    assert previous != current
