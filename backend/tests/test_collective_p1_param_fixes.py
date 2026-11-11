"""집합 1단계 Phase 3 — C-05 날짜 필터 누락(비주거 3 API) · N-3 코호트 회귀 '미상 제외'.

로컬 DB 고정 사례(COLLECTIVE_DATABASE_URL 없으면 skip). 라우트 함수를 세션으로 직접 호출한다.
대농로(청주 흥덕구 복대동) 집합상가 5년 창(2021-11-01~2026-10-31): 화면 n=223, 날짜 무시 시 371.
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest
from sqlalchemy import text

from app.collective import cohort_router
from app.collective.schemas import CohortRegressionRunRequest
from app.collective_commercial import router as crouter

D0, D1 = date(2021, 11, 1), date(2026, 10, 31)


@pytest.fixture(scope="module")
def db():
    from app.collective.db import get_collective_session_factory

    factory = get_collective_session_factory()
    if factory is None:
        pytest.skip("COLLECTIVE_DATABASE_URL not configured")
    s = factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="module")
def daenong(db):
    row = db.execute(text(
        """select cluster_key from commercial_clusters
           where addr2 like '청주%' and road_name like '대농로%' and asset_type='collective_shop'
           order by n_total desc limit 1""")).first()
    if row is None:
        pytest.skip("대농로 cluster 없음")
    return row[0]


def test_signatures_accept_contract_dates():
    for fn in (crouter.list_cluster_addresses, crouter.cluster_histogram, crouter.cluster_stats_by_year):
        params = inspect.signature(fn).parameters
        assert "contract_date_from" in params and "contract_date_to" in params


def test_daenong_addresses_sum_is_223_not_371(db, daenong):
    with_dates = crouter.list_cluster_addresses(daenong, db=db, addr1=None, addr2=None, addr3_list=[], addr4_list=[],
                                                contract_year_from=None, contract_year_to=None,
                                                contract_date_from=D0, contract_date_to=D1)
    without = crouter.list_cluster_addresses(daenong, db=db, addr1=None, addr2=None, addr3_list=[], addr4_list=[],
                                             contract_year_from=None, contract_year_to=None)
    assert sum(i.count for i in with_dates.items) == 223
    assert sum(i.count for i in without.items) == 371


def test_daenong_histogram_n_is_223(db, daenong):
    h = crouter.cluster_histogram(daenong, db=db, addr1=None, addr2=None, addr3_list=[], addr4_list=[],
                                  contract_year_from=None, contract_year_to=None,
                                  contract_date_from=D0, contract_date_to=D1, bins=12, contract_year=None)
    assert h.n == 223


def test_daenong_by_year_uses_dates(db, daenong):
    y = crouter.cluster_stats_by_year(daenong, db=db, addr1=None, addr2=None, addr3_list=[], addr4_list=[],
                                      contract_year_from=None, contract_year_to=None,
                                      contract_date_from=D0, contract_date_to=D1)
    assert sum(p.count for p in y.points) == 223
    assert y.data_source == "live"


def test_cohort_regression_honours_categorical_missing(db):
    rows = db.execute(text(
        """select building_key from collective_transactions
           where is_valid and asset_type='apartment' and addr2='청주시' and addr4='가경동'
             and contract_date >= :d0 and contract_date <= :d1
           group by 1 having count(*) >= 60 and count(*) filter (where dong is null or btrim(dong)='') >= 10
           order by count(*) desc limit 2"""), {"d0": D0, "d1": D1}).fetchall()
    if len(rows) < 2:
        pytest.skip("동 미상 거래가 있는 가경동 단지 2곳 없음")
    keys = [r[0] for r in rows]
    base = dict(building_keys=keys, asset_type="apartment", contract_date_from=D0, contract_date_to=D1)
    keep = cohort_router.cohort_regression(CohortRegressionRunRequest(**base, categorical_missing="keep_unknown"), db=db)
    drop = cohort_router.cohort_regression(CohortRegressionRunRequest(**base, categorical_missing="drop"), db=db)
    assert drop.categorical_missing == "drop"
    assert drop.n_excluded_missing > 0
    assert drop.n < keep.n
