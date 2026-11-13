# -*- coding: utf-8 -*-
"""집합 2단계 C-2 — 같은 법정동 안 본번·건축년도 조각 배정(적재 규칙)과 월간 C-2형 경고 검사.

판정 파일 값은 Cursor 확인 뒤 채운다. 여기서는 규칙 코드만 고정한다.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "pipeline", ROOT / "pipeline" / "collective"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from collective import building_keys as bk  # noqa: E402

BJD = "1111010100"
OTHER_BJD = "1111010200"


def _row(lot, year, *, name="한빛빌라", bjd=BJD, addr3="종로구", addr4="청운동"):
    return {"addr1": "서울특별시", "addr2": "종로구", "addr3": addr3, "addr4": addr4, "building_name": name,
            "lot_number": lot, "road_name": "", "beopjungri_code": bjd, "building_year": year}


def _key(df_row: dict, asset="rowhouse") -> tuple[str, str]:
    raw = bk.building_key_raw_series(pd.DataFrame([df_row]), asset).iat[0]
    return hashlib.sha256(raw.encode("utf-8")).hexdigest(), raw


def _frame(rows, asset="rowhouse"):
    df = pd.DataFrame(rows)
    df["building_key"] = bk._sha256_series(bk.building_key_raw_series(df, asset))
    return df


@pytest.fixture
def units():
    key, _ = _key(_row("10", 2010))
    # 본 조각 p0 = 본번 10·11(2010년), 조각 p1 = 본번 50(2015년)
    return key, {key: {BJD: [("10", 2010, 0), ("11", 2010, 0), ("50", 2015, 1)]}}


def test_known_lots_go_to_their_part_and_main_part_keeps_key(units):
    key, u = units
    df = _frame([_row("10-1", 2010), _row("11", 2010), _row("50-3", 2015)])
    out = bk.apply_building_key_split_c2(df, "rowhouse", units=u, c01_units={})
    _, raw = _key(_row("10", 2010))
    assert list(out["building_key"]) == [key, key, bk.c2_key(raw, "p1")]
    assert out.attrs["c2_review"] == []


def test_new_month_lots_existing_new_and_small(units):
    """새 월 거래: 같은 해 조각 / 3건+ 새 조각 / 3건 미만 → 가장 가까운 조각 + 확인 필요."""
    key, u = units
    _, raw = _key(_row("10", 2010))
    rows = [_row("52", 2015)]                                   # 처음 보는 본번, 2015년 → p1
    rows += [_row("80", 2021)] * 2                              # 처음 보는 본번, 같은 해 없음, 배치 2건 + 기존 1건 = 3 → 새 조각
    rows += [_row("12", 2019)]                                  # 처음 보는 본번, 같은 해 없음, 1건 → 가장 가까운 10·11(p0)
    out = bk.apply_building_key_split_c2(_frame(rows), "rowhouse", units=u, c01_units={},
                                         existing_counts={(key, BJD, "80"): 1})
    assert out["building_key"].iat[0] == bk.c2_key(raw, "p1")
    assert out["building_key"].iat[1] == out["building_key"].iat[2] == bk.c2_key(raw, "m80")
    assert out["building_key"].iat[3] == key
    assert out.attrs["c2_review"] == [{"building_key": key, "beopjungri_code": BJD, "rows": 1}]


def test_new_part_key_is_stable_across_months(units):
    """3건+ 새 본번은 달이 바뀌어도 같은 키(라벨 m<본번>)."""
    key, u = units
    a = bk.apply_building_key_split_c2(_frame([_row("80", 2021)] * 3), "rowhouse", units=u, c01_units={})
    b = bk.apply_building_key_split_c2(_frame([_row("80", 2021)]), "rowhouse", units=u, c01_units={},
                                       existing_counts={(key, BJD, "80"): 3})
    assert a["building_key"].iat[0] == b["building_key"].iat[0] != key


def test_unlisted_keys_other_dong_and_presale_unchanged(units):
    key, u = units
    rows = [_row("50", 2015, name="다른빌라"), _row("50", 2015, bjd=OTHER_BJD)]
    df = _frame(rows)
    before = list(df["building_key"])
    out = bk.apply_building_key_split_c2(df, "rowhouse", units=u, c01_units={})
    assert list(out["building_key"]) == before                 # 목록 밖 키·목록 키의 다른 법정동 → 해시 그대로
    pre = _frame([_row("50", 2015)], asset="presale")
    assert bk.apply_building_key_split_c2(pre, "presale", units={pre["building_key"].iat[0]: u[key]},
                                          c01_units={}).equals(pre)


def test_emergency_off_and_missing_file_return_original(units, monkeypatch, tmp_path):
    key, u = units
    f = tmp_path / "c2.csv"
    pd.DataFrame([{"base_key": key, "asset_type": "rowhouse", "beopjungri_code": BJD, "main_lot": "50",
                   "building_year": 2015, "part": 1, "decision": "split"},
                  {"base_key": "k" * 64, "asset_type": "rowhouse", "beopjungri_code": BJD, "main_lot": "",
                   "building_year": "", "part": "", "decision": "keep"}]).to_csv(f, index=False)
    assert bk.load_split_units_c2(f) == {key: {BJD: [("50", 2015, 1)]}}
    assert bk.judged_keys_c2(f) == {key, "k" * 64}
    monkeypatch.setenv(bk.C2_ENV_OFF, "0")
    assert bk.load_split_units_c2(f) == {}
    df = _frame([_row("50", 2015)])
    assert bk.apply_building_key_split_c2(df, "rowhouse", c01_units={}).equals(df)   # 해제 → 기존 키
    monkeypatch.delenv(bk.C2_ENV_OFF)
    assert bk.load_split_units_c2(tmp_path / "none.csv") == {}


def test_c2_on_top_of_c01_split_key(units):
    """C-01 로 동 단위가 된 키(원문 + '|emd:')도 원문을 재현해 C-2 조각 키를 만든다."""
    base, raw = _key(_row("10", 2010))
    unit = BJD[:8]
    c01 = {base: ({unit: unit}, unit)}
    k01 = bk.split_key_from_raw(raw, unit)
    df = _frame([_row("50", 2015)])
    df["building_key"] = k01
    out = bk.apply_building_key_split_c2(df, "rowhouse", units={k01: {BJD: [("10", 2010, 0), ("50", 2015, 1)]}},
                                         c01_units=c01)
    assert out["building_key"].iat[0] == bk.c2_key(raw + bk.SPLIT_SUFFIX + unit, "p1")


def test_main_lot_parsing():
    assert bk.main_lot_of("0123-4") == "123"
    assert bk.main_lot_of(" 45 ") == "45"
    assert bk.main_lot_of(None) == ""
    assert bk.main_lot_of("BL-3") == "BL"


# --- 월간 경고 검사(실제 PostgreSQL 임시 DB) ---------------------------------

def test_monthly_check_flags_c2_shape(tmp_path):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from collective import integrity_p2 as ip
    from collective import migrate_p2_keys as mig

    fx = "ch2_c2check_p2r"
    try:
        base = make_url(mig.server_url_from_env())
        admin = create_engine(base.set(database="postgres", drivername="postgresql+psycopg2"),
                              isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {fx}"))
            c.execute(text(f"CREATE DATABASE {fx}"))
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"로컬 PostgreSQL 임시 DB 생성 불가: {type(ex).__name__}")
    eng = create_engine(base.set(database=fx, drivername="postgresql+psycopg2"))
    try:
        with eng.begin() as c:
            c.execute(text("CREATE TABLE collective_transactions (building_key text, asset_type text, "
                           "beopjungri_code text, lot_number text, building_year int, is_valid bool)"))
            rows = []
            rows += [("A", "rowhouse", BJD, "10", 2010)] * 3 + [("A", "rowhouse", BJD, "50", 2015)] * 3   # C-2형
            rows += [("B", "rowhouse", BJD, "10", 2010)] * 3 + [("B", "rowhouse", BJD, "12", 2010)] * 3   # 같은 해 → 아님
            rows += [("C", "presale", BJD, "10", 2010)] * 3 + [("C", "presale", BJD, "50", 2015)] * 3     # 분양권 → 아님
            rows += [("D", "rowhouse", BJD, "10", 2010)] * 3 + [("D", "rowhouse", BJD, "50", 2015)] * 2   # 2건 → 아님
            rows += [("E", "rowhouse", BJD, "10", 2010)] * 3 + [("E", "rowhouse", BJD, "70", 2018)] * 3   # 판정 파일 안
            rows += [("E", "rowhouse", BJD, "71", 2018)]                                                 # 파일에 없는 본번
            c.execute(text("INSERT INTO collective_transactions VALUES (:k, :a, :b, :l, :y, true)"),
                      [dict(zip("kably", r)) for r in rows])

        f = tmp_path / "c2.csv"
        pd.DataFrame([{"base_key": "E", "asset_type": "rowhouse", "beopjungri_code": BJD, "main_lot": m,
                       "building_year": y, "part": p, "decision": "split"} for m, y, p in (("10", 2010, 0), ("70", 2018, 1))]
                     ).to_csv(f, index=False)

        class R:
            def __init__(self):
                self.w, self.o = [], []

            def section(self, t): pass
            def ok(self, m): self.o.append(m)
            def warn(self, m): self.w.append(m)
            def err(self, m): raise AssertionError(m)
            def info(self, m): self.o.append(m)

        r = R()
        with eng.connect() as c:
            ip.check_c2_shape(r, c, units_path=f)
        assert any("판정 밖 1곳" in w for w in r.w), r.w          # A 만
        assert any("판정 파일에 없는 본번 1개" in w for w in r.w), r.w   # E 의 71
        assert not any("presale" in m for m in r.o)                   # 분양권(C)은 C-2형으로 세지 않음
    finally:
        eng.dispose()
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {fx} WITH (FORCE)"))
        admin.dispose()
