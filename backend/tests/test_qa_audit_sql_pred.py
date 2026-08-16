"""L1 지역 조건에 ANY 가 들어가지 않는지."""

import pytest

from app.qa_audit.sql_pred import code_eq_or_in, ledger_admin_predicate


def test_single_eup_uses_eq():
    sql, params = ledger_admin_predicate(["36110107"], region_level="eupmyeondong")
    assert "ANY" not in sql
    assert "eupmyeondong_code = :eup_code" in sql
    assert "LEFT(btrim(COALESCE(beopjungri_code::text, '')), 8) = :eup_code" in sql
    assert params["eup_code"] == "36110107"
    assert "_expand_keys" not in params


def test_multi_eup_uses_in():
    sql, params = ledger_admin_predicate(
        ["36110107", "36110108"], region_level="eupmyeondong"
    )
    assert "ANY" not in sql
    assert "eupmyeondong_code IN :eup_codes" in sql
    assert params["_expand_keys"] == ["eup_codes"]


def test_sigungu_prefix_5():
    sql, _ = ledger_admin_predicate(["36110"], region_level="sigungu")
    assert "LEFT(btrim(COALESCE(beopjungri_code::text, '')), 5)" in sql
    assert "ANY" not in sql


def test_empty_codes_rejected():
    with pytest.raises(ValueError):
        ledger_admin_predicate([], region_level="eupmyeondong")


def test_code_eq_or_in_single():
    sql, params = code_eq_or_in(["36110107"], column="eupmyeondong_code", eq_key="c", in_key="cs")
    assert sql == "eupmyeondong_code = :c"
    assert params == {"c": "36110107"}
