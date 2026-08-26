"""집합 교차 시군구 분석 scope — region_addrs OR 코드."""

from app.region_scope import apply_analysis_region_scope, parse_region_addr_keys


def test_parse_region_addr_keys():
    assert parse_region_addr_keys(["충청북도|음성군|대소읍"]) == [
        ("충청북도", "음성군", "대소읍")
    ]
    assert parse_region_addr_keys(["bad"]) == []


def test_analysis_scope_emd_without_emd_column():
    clauses: list[str] = []
    params: dict = {}
    used = apply_analysis_region_scope(
        clauses,
        params,
        codes=["43770350"],
        code_level="eupmyeondong",
        addr_keys=["충청북도|음성군|대소읍"],
        col_prefix="m",
        conn=None,
        emd_code_col=None,
    )
    assert used
    sql = clauses[0]
    assert "beopjungri_code" in sql
    assert "eupmyeondong_code" not in sql
    assert "addr1 = :ru_a1_0" in sql
    assert params["admin_region_codes"] == ["43770350"]
