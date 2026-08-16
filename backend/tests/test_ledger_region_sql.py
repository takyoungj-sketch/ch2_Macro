"""ledger_region_sql — ANY 재발 방지 단위 테스트."""

import inspect

import pytest

from app.ledger_region_sql import (
    EXPAND_REGION_CODES_FLAG,
    beopjungri_eq_or_in,
)
from app.routers import free_v2, paid


def test_beopjungri_single_uses_eq():
    sql, params = beopjungri_eq_or_in(["5111012400"], column="lt.beopjungri_code")
    assert sql == "lt.beopjungri_code = :region_code"
    assert params == {"region_code": "5111012400"}
    assert EXPAND_REGION_CODES_FLAG not in params


def test_beopjungri_multi_uses_expanding_in():
    sql, params = beopjungri_eq_or_in(
        ["5111012400", "5111012500"], column="lt.beopjungri_code"
    )
    assert sql == "lt.beopjungri_code IN :region_codes"
    assert params["region_codes"] == ["5111012400", "5111012500"]
    assert params[EXPAND_REGION_CODES_FLAG] is True


def test_beopjungri_rejects_empty():
    with pytest.raises(ValueError):
        beopjungri_eq_or_in([])


def test_paid_build_conditions_single_eq():
    parts, params = paid._build_conditions(
        ["5111012400"],
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        False,
        db=None,
    )
    joined = " AND ".join(parts)
    assert "lt.beopjungri_code = :region_code" in joined
    assert "ANY(" not in joined
    assert EXPAND_REGION_CODES_FLAG not in params
    assert params["region_code"] == "5111012400"


def test_paid_build_conditions_multi_in():
    parts, params = paid._build_conditions(
        ["5111012400", "5111012500"],
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        False,
        db=None,
    )
    joined = " AND ".join(parts)
    assert "lt.beopjungri_code IN :region_codes" in joined
    assert "ANY(" not in joined
    assert params[EXPAND_REGION_CODES_FLAG] is True


def test_matrix_yearly_rolling_is_single_fetch():
    """롤링 모드는 버킷 루프 안 execute 가 아니라 1회 fetch 후 메모리 버킷팅."""
    src = inspect.getsource(paid.matrix_yearly)
    assert "버킷마다 원장 재조회" in src or "메모리 버킷팅" in src
    # 버킷 for-loop 앞에 한 번의 roll_sql / _paid_execute 만 두는 구조
    assert "roll_sql" in src
    assert src.index("roll_sql") < src.index("for bi,")


def test_free_v2_dual_maps_uses_shared_helper():
    src = inspect.getsource(free_v2._fetch_yearly_tx_dual_maps)
    assert "beopjungri_eq_or_in" in src
    assert "execute_expanding" in src
    assert "ANY(" not in src
    assert "FILTER" in src
