# -*- coding: utf-8 -*-
"""집합 2단계 C-2 — 같은 법정동 안 본번·건축년도 조각 배정(적재 규칙)과 월간 C-2형 경고 검사.

판정은 집합 DB 표 collective_building_key_c2_units(값은 Cursor 확인 뒤). 여기서는 규칙 코드만 고정한다.
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
    assert out["building_key"].iat[1] == out["building_key"].iat[2] == bk.c2_key(raw, "p2")   # 새 조각 = 최대 조각 + 1
    assert out["building_key"].iat[3] == key
    assert out.attrs["c2_review"] == [{"building_key": key, "beopjungri_code": BJD, "rows": 1}]
    assert out.attrs["c2_new_parts"] == [{"base_key": key, "asset_type": "rowhouse", "beopjungri_code": BJD, "main_lot": "80",
                                          "building_year": 2021, "part": 2, "decision": "split", "source": "auto_ingest"}]
    assert u[key][BJD] == [("10", 2010, 0), ("11", 2010, 0), ("50", 2015, 1)]   # 호출자의 판정 dict 는 바뀌지 않음


def test_new_part_is_registered_and_reused_next_month(units):
    """Codex 재현: 3건 → 새 조각. 다음 달 1건은 (등록된) 같은 조각으로 — 등록이 없으면 가장 가까운 조각으로 새던 문제."""
    key, u = units
    a = bk.apply_building_key_split_c2(_frame([_row("80", 2021)] * 3), "rowhouse", units=u, c01_units={})
    reg = a.attrs["c2_new_parts"]
    u2 = bk.units_from_rows([(key, BJD, f, y, pt, "split") for f, y, pt in (("10", 2010, 0), ("11", 2010, 0), ("50", 2015, 1))]
                            + [(r["base_key"], r["beopjungri_code"], r["main_lot"], r["building_year"], r["part"], "split")
                               for r in reg])
    b = bk.apply_building_key_split_c2(_frame([_row("80", 2021)]), "rowhouse", units=u2, c01_units={})
    assert a["building_key"].iat[0] == b["building_key"].iat[0] != key
    assert b.attrs["c2_new_parts"] == [] and b.attrs["c2_review"] == []
    # 등록 없이 다음 달 1건만 오면(옛 동작) 가장 가까운 조각(p1, 본번 50)에 붙어 키가 갈렸다
    c = bk.apply_building_key_split_c2(_frame([_row("80", 2021)]), "rowhouse", units=u, c01_units={})
    assert c["building_key"].iat[0] != a["building_key"].iat[0]


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


def test_units_from_rows_and_emergency_off(units, monkeypatch):
    key, u = units
    rows = [(key, BJD, "50", 2015, 1, "split"), (key, BJD, "0010", "2010", 0, "split"), ("k" * 64, BJD, "", None, None, "keep")]
    assert bk.units_from_rows(rows) == {key: {BJD: [("50", 2015, 1), ("10", 2010, 0)]}}
    monkeypatch.setenv(bk.C2_ENV_OFF, "0")
    assert bk.load_split_units_c2(object()) == {}                 # 해제면 DB 를 보지 않고 빈 판정
    df = _frame([_row("50", 2015)])
    assert bk.apply_building_key_split_c2(df, "rowhouse", units=None, c01_units={}).equals(df)   # 판정 없음 → 기존 키


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


# --- 판정 표·적재·월간 경고 검사(실제 PostgreSQL 임시 DB) -----------------------------

FX = "ch2_c2check_p2r"


@pytest.fixture(scope="module")
def pg():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from collective import migrate_p2_keys as mig

    try:
        base = make_url(mig.server_url_from_env()).set(drivername="postgresql+psycopg2")
        admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT",
                              connect_args={"connect_timeout": 3})
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {FX}"))
            c.execute(text(f"CREATE DATABASE {FX}"))
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"로컬 PostgreSQL 임시 DB 생성 불가: {type(ex).__name__}")
    eng = create_engine(base.set(database=FX))
    with eng.begin() as c:
        c.execute(text("CREATE TABLE collective_transactions (building_key text, asset_type text, "
                       "beopjungri_code text, lot_number text, building_year int, is_valid bool)"))
        rows = []
        rows += [("A", "rowhouse", BJD, "10", 2010)] * 3 + [("A", "rowhouse", BJD, "50", 2015)] * 3   # C-2형
        rows += [("B", "rowhouse", BJD, "10", 2010)] * 3 + [("B", "rowhouse", BJD, "12", 2010)] * 3   # 같은 해 → 아님
        rows += [("C", "presale", BJD, "10", 2010)] * 3 + [("C", "presale", BJD, "50", 2015)] * 3     # 분양권 → 아님
        rows += [("D", "rowhouse", BJD, "10", 2010)] * 3 + [("D", "rowhouse", BJD, "50", 2015)] * 2   # 2건 → 아님
        rows += [("E", "rowhouse", BJD, "10", 2010)] * 3 + [("E", "rowhouse", BJD, "70", 2018)] * 3   # 판정 표 안
        rows += [("E", "rowhouse", BJD, "71", 2018)]                                                 # 표에 없는 본번
        c.execute(text("INSERT INTO collective_transactions VALUES (:k, :a, :b, :l, :y, true)"),
                  [dict(zip("kably", r)) for r in rows])
    yield eng
    eng.dispose()
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {FX} WITH (FORCE)"))
    admin.dispose()


class _Rep:
    def __init__(self):
        self.w, self.o = [], []

    def section(self, t): pass
    def ok(self, m): self.o.append(m)
    def warn(self, m): self.w.append(m)
    def err(self, m): raise AssertionError(m)
    def info(self, m): self.o.append(m)


def _check(eng):
    from collective import integrity_p2 as ip

    r = _Rep()
    with eng.connect() as c:
        ip.check_c2_shape(r, c)
    return r


def test_monthly_check_warns_when_table_missing_or_empty(pg):
    from sqlalchemy import text

    with pg.begin() as c:
        c.execute(text(f"DROP TABLE IF EXISTS {bk.C2_TABLE}"))
    r = _check(pg)
    assert any("C-2 판정 표 없음" in w and "2곳" in w for w in r.w), r.w     # A·E (판정 전)
    with pg.connect() as c:
        assert bk.c2_table_state(c) == ("missing", 0) and bk.load_split_units_c2(c) == {} and bk.judged_keys_c2(c) == set()
    with pg.begin() as c:
        c.execute(text(bk.C2_DDL))
    r = _check(pg)
    assert any("C-2 판정 표 비어 있음" in w for w in r.w), r.w
    assert not any("presale" in m for m in r.o)                   # 분양권(C)은 C-2형으로 세지 않음


def test_monthly_check_and_ingest_read_the_table(pg):
    from sqlalchemy import text

    with pg.begin() as c:
        c.execute(text(bk.C2_DDL))
        c.execute(text(f"DELETE FROM {bk.C2_TABLE}"))
        c.execute(text(f"INSERT INTO {bk.C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, building_year, part, decision) "
                       "VALUES ('E', 'rowhouse', :b, '10', 2010, 0, 'split'), ('E', 'rowhouse', :b, '70', 2018, 1, 'split')"),
                  {"b": BJD})
    r = _check(pg)
    assert any("C-2형 판정 밖 1곳" in w for w in r.w), r.w                       # A 만 남음
    assert any("판정 표에 없는 본번 1개" in w for w in r.w), r.w                  # E 의 71
    with pg.connect() as c:
        assert bk.load_split_units_c2(c) == {"E": {BJD: [("10", 2010, 0), ("70", 2018, 1)]}}

    # 월간 적재: 판정 표를 읽어 키를 배정(실제 키 원문을 재현할 수 있는 행으로)
    key, raw = _key(_row("10", 2010))
    with pg.begin() as c:
        c.execute(text(f"INSERT INTO {bk.C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, building_year, part, decision) "
                       "VALUES (:k, 'rowhouse', :b, '10', 2010, 0, 'split'), (:k, 'rowhouse', :b, '50', 2015, 1, 'split')"),
                  {"k": key, "b": BJD})
        c.execute(text("INSERT INTO collective_transactions VALUES (:k, 'rowhouse', :b, '80', 2021, true)"), {"k": key, "b": BJD})
    df = _frame([_row("50", 2015), _row("80", 2021), _row("80", 2021), _row("10", 2010)])
    out = bk.apply_c2_split_from_db(pg, df, "rowhouse")   # import_refined._apply_c2_split 가 부르는 함수
    k80 = bk.c2_key(raw, "p2")
    assert list(out["building_key"]) == [bk.c2_key(raw, "p1"), k80, k80, key]
    with pg.connect() as c:                                # 새 조각이 판정 표에 자동 등록됨(출처 표시)
        reg = c.execute(text(f"SELECT main_lot, building_year, part, decision, source FROM {bk.C2_TABLE} "
                             "WHERE base_key = :k ORDER BY part, main_lot"), {"k": key}).all()
    assert ("80", 2021, 2, "split", "auto_ingest") in [tuple(r) for r in reg]

    # Codex 재현 시나리오: 그 3건이 원장에 들어간 뒤 다음 달 1건 → 같은 조각(표 기준)
    with pg.begin() as c:
        c.execute(text("DELETE FROM collective_transactions WHERE building_key = :k AND lot_number = '80'"), {"k": key})
        c.execute(text("INSERT INTO collective_transactions VALUES (:k, 'rowhouse', :b, '80', 2021, true)"),
                  [{"k": k80, "b": BJD}] * 3)
    nxt = bk.apply_c2_split_from_db(pg, _frame([_row("80", 2021)]), "rowhouse")
    assert nxt["building_key"].iat[0] == k80 and nxt.attrs["c2_new_parts"] == []

    # 기존 거래 수는 본 키 + 파생 조각 키를 모두 센다: 본번 90 의 2건이 p1 조각 키에 있고 이번 달 1건 → 3건 → 새 조각
    k1 = bk.c2_key(raw, "p1")
    with pg.begin() as c:
        c.execute(text("INSERT INTO collective_transactions VALUES (:k, 'rowhouse', :b, '90', 2019, true)"),
                  [{"k": k1, "b": BJD}] * 2)
    with pg.connect() as c:
        units = bk.load_split_units_c2(c)
        counts = bk.existing_main_lot_counts(c, {key: bk.c2_derived_keys(raw, units[key])})
    assert counts[(key, BJD, "90")] == 2 and counts[(key, BJD, "80")] == 3
    out = bk.apply_c2_split_from_db(pg, _frame([_row("90", 2019)]), "rowhouse")
    assert out["building_key"].iat[0] == bk.c2_key(raw, "p3") and out.attrs["c2_new_parts"][0]["part"] == 3


def test_import_refined_calls_db_reader():
    """적재 경로가 판정 표 읽기 함수를 부르는지(모듈 import 순서 문제로 import_refined 는 소스로 확인)."""
    src = (Path(__file__).resolve().parents[1] / "collective" / "import_refined.py").read_text(encoding="utf-8")
    assert "apply_c2_split_from_db(engine, df, asset_type)" in src
    assert "df = _apply_c2_split(engine, df, asset_type)" in src
    assert src.index("apply_building_key_split(df, asset_type)") < src.index("df = _apply_c2_split(engine, df, asset_type)")


def _seed_key(pg, name):
    """새 base_key(이름만 다르게) — p0 = 본번 10(2010), p1 = 본번 50(2015)."""
    from sqlalchemy import text

    key, raw = _key(_row("10", 2010, name=name))
    with pg.begin() as c:
        c.execute(text(bk.C2_DDL))
        c.execute(text(f"DELETE FROM {bk.C2_TABLE} WHERE base_key = :k"), {"k": key})
        c.execute(text(f"INSERT INTO {bk.C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, building_year, part, decision) "
                       "VALUES (:k, 'rowhouse', :b, '10', 2010, 0, 'split'), (:k, 'rowhouse', :b, '50', 2015, 1, 'split')"),
                  {"k": key, "b": BJD})
    return key, raw


def test_concurrent_ingests_get_distinct_part_numbers(pg, monkeypatch):
    """Codex 재현(동시 실행): 같은 키에 처음 보는 본번이 두 실행에서 동시에 새 조각이 되면, 잠금 없이는 둘 다
    「최대+1 = 2」를 배정해 서로 다른 본번이 같은 조각 키로 합쳐졌다. advisory lock 뒤 다시 읽으면 2·3 으로 갈린다."""
    import threading
    import time

    from sqlalchemy import text

    key, raw = _seed_key(pg, "동시빌라")
    real = bk.existing_main_lot_counts

    def slow(conn, groups):                      # 잠금 안에서 오래 머물게 해 겹침을 확실히 만든다
        time.sleep(0.6)
        return real(conn, groups)

    monkeypatch.setattr(bk, "existing_main_lot_counts", slow)
    barrier = threading.Barrier(2)
    out: dict[str, pd.DataFrame] = {}
    errs: list[BaseException] = []

    def run(lot, year):
        try:
            df = _frame([_row(lot, year, name="동시빌라")] * 3)
            barrier.wait()
            out[lot] = bk.apply_c2_split_from_db(pg, df, "rowhouse")
        except BaseException as ex:  # noqa: BLE001
            errs.append(ex)

    ts = [threading.Thread(target=run, args=a) for a in (("80", 2021), ("90", 2019))]
    for t in ts:
        t.start()
    for t in ts:
        t.join(30)
    assert not errs, errs
    k80, k90 = out["80"]["building_key"].iat[0], out["90"]["building_key"].iat[0]
    assert k80 != k90 and {k80, k90} == {bk.c2_key(raw, "p2"), bk.c2_key(raw, "p3")}
    with pg.connect() as c:
        rows = {r[0]: r[1] for r in c.execute(text(
            f"SELECT main_lot, part FROM {bk.C2_TABLE} WHERE base_key = :k AND source = 'auto_ingest'"), {"k": key})}
    assert sorted(rows.values()) == [2, 3] and len(rows) == 2


def test_same_new_lot_twice_concurrently_same_part(pg, monkeypatch):
    """같은 본번이 두 실행에서 동시에 새 조각이 되면 같은 조각·같은 키(두 번째는 잠금 뒤 다시 읽어 표의 값을 쓴다)."""
    import threading
    import time

    key, raw = _seed_key(pg, "동시빌라2")
    real = bk.existing_main_lot_counts

    def slow(conn, groups):
        time.sleep(0.4)
        return real(conn, groups)

    monkeypatch.setattr(bk, "existing_main_lot_counts", slow)
    barrier = threading.Barrier(2)
    keys: list[str] = []

    def run():
        df = _frame([_row("80", 2021, name="동시빌라2")] * 3)
        barrier.wait()
        keys.append(bk.apply_c2_split_from_db(pg, df, "rowhouse")["building_key"].iat[0])

    ts = [threading.Thread(target=run) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(30)
    assert keys == [bk.c2_key(raw, "p2")] * 2


def test_do_nothing_conflict_rereads_actual_part(pg, monkeypatch):
    """잠금 밖에서 누가 먼저 같은 본번을 다른 조각 번호(7)로 넣어 둔 경우 — 등록이 DO NOTHING 이면 표의 실제 값을 다시 읽어 쓴다."""
    from sqlalchemy import text

    key, raw = _seed_key(pg, "충돌빌라")
    with pg.begin() as c:
        c.execute(text(f"INSERT INTO {bk.C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, building_year, part, decision, source) "
                       "VALUES (:k, 'rowhouse', :b, '80', 2021, 7, 'split', 'manual')"), {"k": key, "b": BJD})
    real = bk.load_split_units_c2
    calls = {"n": 0}

    def stale(conn):                               # 처음 두 번(잠금 전·잠금 뒤)은 본번 80 을 모르는 낡은 판정
        calls["n"] += 1
        u = real(conn)
        if calls["n"] <= 2 and key in u:
            u = {**u, key: {b: [f for f in fr if f[0] != "80"] for b, fr in u[key].items()}}
        return u

    monkeypatch.setattr(bk, "load_split_units_c2", stale)
    out = bk.apply_c2_split_from_db(pg, _frame([_row("80", 2021, name="충돌빌라")] * 3), "rowhouse")
    assert out["building_key"].iat[0] == bk.c2_key(raw, "p7")          # 배정했던 p2 가 아니라 표의 실제 값
    assert calls["n"] == 3                                             # 충돌 뒤 다시 읽음
    with pg.connect() as c:
        parts = [r[0] for r in c.execute(text(f"SELECT part FROM {bk.C2_TABLE} WHERE base_key = :k AND main_lot = '80'"),
                                         {"k": key})]
    assert parts == [7]
