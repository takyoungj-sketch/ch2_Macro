"""집합 1단계 Phase 1 — C-01 B안: expand_beopjungri_codes 공식 읍면동명 거르기.

단위 테스트(가짜 연결) + 로컬 DB 고정 사례(COLLECTIVE_DATABASE_URL 없으면 skip).
DB 사례는 기준월 2026-10-01 스냅샷(0단계 측정 시점)에 고정한다.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import bindparam, text

from app import region_scope
from app.region_scope import (
    _selected_emd_names,
    apply_region_scope,
    expand_beopjungri_codes,
    filter_codes_by_official_emd_name,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """region_codes 조회만 흉내 낸다."""

    def __init__(self, names: dict[str, list[str]], gu: set[str] | None = None):
        self.names = names
        self.gu = gu or set()

    def execute(self, stmt, params=None):
        sql = str(stmt)
        params = params or {}
        if "eupmyeondong_name" in sql:
            rows = [
                SimpleNamespace(c8=c8, nm=nm, sgg="")
                for c8 in params["c8"]
                for nm in self.names.get(c8, [])
            ]
            return _FakeResult(rows)
        if "sigungu_name" in sql:
            return _FakeResult([SimpleNamespace(x=1)] if params.get("sgg") in self.gu else [])
        raise AssertionError(sql)


def test_filter_keeps_matching_name_and_drops_other_emd():
    conn = _FakeConn({"43114101": ["우암동"], "43114250": ["내수읍"]})
    out = filter_codes_by_official_emd_name(conn, ["4311410100", "4311425036"], ["우암동"])
    assert out == ["4311410100"]


def test_filter_keeps_blank_or_unknown_official_name():
    # 세종 동 지역: region_codes 이름 공란 → 근거 없음 → 유지
    conn = _FakeConn({"36110101": [""], "43114250": ["내수읍"]})
    out = filter_codes_by_official_emd_name(conn, ["3611010100", "9999999900", "4311425036"], ["보람동"])
    assert out == ["3611010100", "9999999900"]


def test_filter_old_name_and_eup_myeon_variant():
    # 화성 옛 코드(비활성) 봉담읍, 음성 대소면↔대소읍
    conn = _FakeConn({"41590253": ["봉담읍"], "43770310": ["대소면", "대소읍"]})
    assert filter_codes_by_official_emd_name(conn, ["4159025321"], ["봉담읍"]) == ["4159025321"]
    assert filter_codes_by_official_emd_name(conn, ["4377031021"], ["대소읍"]) == ["4377031021"]
    conn2 = _FakeConn({"43770310": ["대소면"]})
    assert filter_codes_by_official_emd_name(conn2, ["4377031021"], ["대소읍"]) == ["4377031021"]


def test_filter_sejong_shifted_columns_use_sigungu_tail():
    """세종 읍·면: region_codes sigungu_name=읍면명, eupmyeondong_name=리명(열 밀림)."""

    class _Shifted(_FakeConn):
        def execute(self, stmt, params=None):
            if "eupmyeondong_name" in str(stmt):
                return _FakeResult([SimpleNamespace(c8="36110250", nm="평리", sgg="조치원읍")])
            return super().execute(stmt, params)

    assert filter_codes_by_official_emd_name(_Shifted({}), ["3611025021"], ["조치원읍"]) == ["3611025021"]
    assert filter_codes_by_official_emd_name(_Shifted({}), ["3611025021"], ["금남면"]) == []


def test_selected_names_ri_and_gu_paths_unchanged():
    conn = _FakeConn({}, gu={"부천시 원미구"})
    # 리 선택 → 거르지 않음
    assert (
        _selected_emd_names(conn, addr2="음성군", addr3="대소읍", addr3_list=None, addr4_list=None,
                            ri_list=[{"eup": "대소읍", "ri": "태생리"}])
        is None
    )
    # 일반구 전체 선택 → 거르지 않음
    assert _selected_emd_names(conn, addr2="부천시", addr3="원미구", addr3_list=None, addr4_list=None, ri_list=None) is None
    # 시군구 전체 → 거르지 않음
    assert _selected_emd_names(conn, addr2="음성군", addr3=None, addr3_list=None, addr4_list=None, ri_list=None) is None
    # 동 선택
    assert _selected_emd_names(conn, addr2="부천시", addr3="원미구", addr3_list=None, addr4_list=["춘의동"], ri_list=None) == ["춘의동"]
    # 시군구 직속 읍면
    assert _selected_emd_names(conn, addr2="음성군", addr3="대소읍", addr3_list=None, addr4_list=None, ri_list=None) == ["대소읍"]


# ---------------- 로컬 DB 고정 사례 ----------------

AS_OF = date(2026, 10, 1)


@pytest.fixture(scope="module")
def ceng():
    from app.collective.db import get_collective_engine

    eng = get_collective_engine()
    if eng is None:
        pytest.skip("COLLECTIVE_DATABASE_URL not configured")
    with eng.connect() as c:
        ok = c.execute(
            text("SELECT 1 FROM collective_building_stats WHERE as_of_month = :m LIMIT 1"), {"m": AS_OF}
        ).first()
    if ok is None:
        pytest.skip("기준월 2026-10-01 스냅샷 없음")
    return eng


def _no_filter(monkeypatch):
    """수정 전 동작(거르기 없음)."""
    monkeypatch.setattr(region_scope, "filter_codes_by_official_emd_name", lambda conn, codes, names: codes)


def _stats_count(conn, **kw):
    clauses = ["window_years = 5", "as_of_month = :as_of"]
    params = {"as_of": AS_OF}
    apply_region_scope(clauses, params, conn=conn, table="collective_building_stats", valid_sql=None, **kw)
    r = conn.execute(
        text(
            f"SELECT count(*) k, COALESCE(sum(count),0) n FROM collective_building_stats WHERE {' AND '.join(clauses)}"
        ),
        params,
    ).first()
    return int(r.k), int(r.n)


def _tx_count(conn, table="collective_transactions", **kw):
    clauses = ["is_valid = true", "contract_date >= date '2021-11-01'", "contract_date < date '2026-11-01'"]
    params: dict = {}
    apply_region_scope(clauses, params, conn=conn, table=table, **kw)
    r = conn.execute(text(f"SELECT count(*) n FROM {table} WHERE {' AND '.join(clauses)}"), params).first()
    return int(r.n)


def _emd_names_of(conn, codes):
    if not codes:
        return set()
    rows = conn.execute(
        text(
            "SELECT DISTINCT eupmyeondong_name nm FROM region_codes WHERE btrim(eupmyeondong_code::text) IN :c"
        ).bindparams(bindparam("c", expanding=True)),
        {"c": sorted({c[:8] for c in codes})},
    ).fetchall()
    return {r.nm for r in rows}


def test_db_cheongju_uam_dong_has_no_naesu_codes(ceng):
    kw = dict(addr1="충청북도", addr2="청주시", addr3="청원구", addr4_list=["우암동"])
    with ceng.connect() as c:
        codes = expand_beopjungri_codes(c, table="collective_building_stats", valid_sql=None, **kw)
        assert codes
        assert "내수읍" not in _emd_names_of(c, codes)
        clauses = ["window_years = 5", "as_of_month = :as_of"]
        params = {"as_of": AS_OF}
        apply_region_scope(clauses, params, conn=c, table="collective_building_stats", valid_sql=None, **kw)
        naesu = c.execute(
            text(
                f"SELECT count(*) FROM collective_building_stats WHERE {' AND '.join(clauses)}"
                " AND (addr4 = '내수읍' OR addr3 = '내수읍')"
            ),
            params,
        ).scalar()
        assert naesu == 0


def test_db_bucheon_chunui_matches_phase0_b(ceng):
    kw = dict(addr1="경기도", addr2="부천시", addr3="원미구", addr4_list=["춘의동"])
    with ceng.connect() as c:
        assert _stats_count(c, **kw) == (166, 804)


@pytest.mark.parametrize(
    "kw",
    [
        dict(addr1="경기도", addr2="화성시", addr3="효행구", addr4_list=["봉담읍"]),
        dict(addr1="세종특별자치시", addr2="__FLAT_SIDO__", addr3="보람동"),
        dict(addr1="세종특별자치시", addr2="__FLAT_SIDO__", addr3="조치원읍"),
        dict(addr1="충청북도", addr2="음성군", addr3="대소읍"),
        dict(addr1="충청북도", addr2="음성군", addr3="대소읍", ri_list=[{"eup": "대소읍", "ri": "태생리"}]),
    ],
    ids=["hwaseong-bongdam", "sejong-boram", "sejong-jochiwon", "eumseong-daeso", "eumseong-daeso-ri"],
)
def test_db_ledger_unchanged(ceng, monkeypatch, kw):
    with ceng.connect() as c:
        after = _tx_count(c, **kw)
        with monkeypatch.context() as m:
            _no_filter(m)
            before = _tx_count(c, **kw)
    assert after > 0
    assert after == before
