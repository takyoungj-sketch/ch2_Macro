# -*- coding: utf-8 -*-
"""집합 2단계 P1·P2 — C-2 판정 표를 키 이전(migrate_p2_keys)에 연결: 소형 fixture DB 왕복.

- 판정 표 본번 → 조각(본 조각 p0 은 옛 키 유지), 같은 건축년도 3건 미만 본번은 그 조각, 표에 없는 3건+ 본번은 새 조각(등록)
- 호남 옛 이름 키가 C-2 키로 가는 경우: 옛 키 → 조각(honam_sido+c2_split) · 2단계 키 → 조각(c2_chain) · 옛 키 → 2단계 키(n 0)
- 부속 표: 속성·공시지가는 본 조각(옛 키)이 그대로, 좌표는 C-2 분할 키 행을 지운다(P2)
- 검증 통과 → 재실행 멱등 → 되돌리기 → 원상태(판정 표의 자동 등록 행까지)

로컬 PostgreSQL 에 임시 DB `ch2c2_p2r_fixture` 를 만들고 끝나면 지운다. 서버에 붙지 못하면 skip.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parents[1]
for p in (PIPE, PIPE / "collective"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from collective import building_keys as bk  # noqa: E402
from collective import migrate_p2_keys as mig  # noqa: E402

FX = "ch2c2_p2r_fixture"
N = "전남광주통합특별시"


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _raw(a1, a2, a3, name, asset="apartment"):
    return f"{asset}|{a1}|{a2}|{a3}|name:{name}"


RK = _raw("서울특별시", "종로구", "청운동", "힐")
K = _sha(RK)
K1, K2 = bk.c2_key(RK, "p1"), bk.c2_key(RK, "p2")
RH0, RH1 = _raw("광주광역시", "광산구", "수완동", "자이"), _raw(N, "광산구", "수완동", "자이")
H0, H1 = _sha(RH0), _sha(RH1)
H1p1 = bk.c2_key(RH1, "p1")
U = _sha(_raw("서울특별시", "강남구", "역삼동", "래미안"))

SCHEMA = """
CREATE TABLE collective_transactions (id serial PRIMARY KEY, transaction_hash text, asset_type text, building_key text,
  display_name text, building_name text, addr1 text, addr2 text, addr3 text, addr4 text, addr5 text, lot_number text,
  road_name text, sigungu_code text, beopjungri_code text, contract_year int, contract_date date, building_year int,
  unit_price float, is_valid bool DEFAULT true, deal_type text);
CREATE TABLE commercial_clusters (id serial PRIMARY KEY, cluster_key text, asset_type text, addr1 text, addr2 text,
  addr3 text, addr4 text, road_name text, n_total int);
CREATE TABLE collective_commercial_transactions (id serial PRIMARY KEY, transaction_hash text,
  cluster_id int REFERENCES commercial_clusters(id), asset_type text, cluster_key text, addr1 text, addr2 text,
  addr3 text, addr4 text, addr5 text, road_name text, contract_year int, contract_date date, price float,
  gross_area float, deal_type text);
CREATE TABLE collective_building_attributes (id serial PRIMARY KEY, snapshot_ym text, asset_type text, building_key text, danji_code text);
CREATE TABLE collective_building_geocodes (building_key text PRIMARY KEY, label text);
CREATE TABLE collective_building_assessed_land_price (building_key text, asset_type text, assessed_land_price float,
  PRIMARY KEY (building_key, asset_type));
"""

ORIGINAL = {
    "collective_transactions": "id", "collective_building_attributes": "id",
    "collective_building_geocodes": "building_key", "collective_building_assessed_land_price": "building_key, asset_type",
    "collective_building_key_c2_units": "base_key, beopjungri_code, main_lot",
}
SNAP_COLS = {"collective_building_key_c2_units": "base_key, asset_type, beopjungri_code, main_lot, building_year, part, decision, source"}


def _tx(a1, a2, a3, name, key, code, lot, year, d):
    return dict(h=_sha(f"{key}{lot}{d}"), k=key, n=name, a1=a1, a2=a2, a3=a3, lot=lot, code=code, by=year, y=d.year, d=d)


def _seed(c):
    rows = []
    k = ("서울특별시", "종로구", "청운동", "힐", K, "1111010100")
    for i in range(5):                                     # 본번 10: 본 조각(옛 키 유지)
        rows.append(_tx(*k, f"10-{i}", 2010, date(2020, 1 + i, 1)))
    for i in range(3):                                     # 본번 20: 조각 1
        rows.append(_tx(*k, "20", 2015, date(2021, 1 + i, 1)))
    rows.append(_tx(*k, "21", 2015, date(2022, 1, 1)))     # 본번 21(1건): 같은 건축년도 조각 1
    for i in range(3):                                     # 본번 30(3건, 표에 없음): 새 조각 2 등록
        rows.append(_tx(*k, "30", 2020, date(2023, 1 + i, 1)))
    for i in range(3):                                     # 호남 옛 이름 → 2단계 키 H1 → 본번 7 은 조각 1
        rows.append(_tx("광주광역시", "광산구", "수완동", "자이", H0, "2920010100", "7", 2012, date(2019, 1 + i, 1)))
    for i in range(3):                                     # 이미 새 이름인 H1 본번 5: 본 조각
        rows.append(_tx(N, "광산구", "수완동", "자이", H1, "2920010100", "5", 2008, date(2023, 1 + i, 1)))
    rows.append(_tx("서울특별시", "강남구", "역삼동", "래미안", U, "1168010100", "1", 2000, date(2024, 1, 1)))
    c.execute(text("""INSERT INTO collective_transactions (transaction_hash, asset_type, building_key, display_name,
        building_name, addr1, addr2, addr3, lot_number, road_name, beopjungri_code, contract_year, contract_date,
        building_year, unit_price) VALUES (:h,'apartment',:k,:n,:n,:a1,:a2,:a3,:lot,'로',:code,:y,:d,:by,100)"""), rows)
    mig._exec_script(c, bk.C2_DDL)
    c.execute(text(f"""INSERT INTO {bk.C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, building_year, part,
        decision, source) VALUES
        (:k,'apartment','1111010100','10',2010,0,'split','c2_final'),
        (:k,'apartment','1111010100','20',2015,1,'split','c2_final'),
        (:h,'apartment','2920010100','5',2008,0,'split','c2_final'),
        (:h,'apartment','2920010100','7',2012,1,'split','c2_final'),
        (:u,'apartment','1168010100','1',NULL,NULL,'keep','c2_final')"""), {"k": K, "h": H1, "u": U})
    c.execute(text("""INSERT INTO collective_building_attributes (snapshot_ym, asset_type, building_key, danji_code) VALUES
        ('202610','apartment',:k,'K1'), ('202610','apartment',:h0,'K2'), ('202610','apartment',:u,'K3')"""),
              {"k": K, "h0": H0, "u": U})
    c.execute(text("INSERT INTO collective_building_geocodes VALUES (:k,'k'), (:h0,'h0'), (:u,'u')"), {"k": K, "h0": H0, "u": U})
    c.execute(text("INSERT INTO collective_building_assessed_land_price VALUES (:k,'apartment',1), (:u,'apartment',2)"),
              {"k": K, "u": U})


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    try:
        base = mig.server_url_from_env()
        admin = create_engine(make_url(base).set(database="postgres", drivername="postgresql+psycopg2"),
                              isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {FX}"))
            c.execute(text(f"CREATE DATABASE {FX}"))
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"로컬 PostgreSQL fixture DB 생성 불가: {type(ex).__name__}")
    eng = mig.engine_for(FX, read_only=False, base_url=base)
    with eng.begin() as c:
        mig._exec_script(c, SCHEMA)
        _seed(c)
    split = tmp_path_factory.mktemp("p2c2") / "split.csv"
    split.write_text("base_key,asset_type,emd8,unit_emd8,part,decision,reason\n", encoding="utf-8")
    bk.load_split_units.cache_clear()
    yield {"base": base, "eng": eng, "split": str(split)}
    eng.dispose()
    mig._COLS_CACHE.clear()
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {FX} WITH (FORCE)"))
    admin.dispose()


def _snap(eng):
    out = {}
    with eng.connect() as c:
        for t, order in ORIGINAL.items():
            out[t] = [tuple(r) for r in c.execute(text(f"SELECT {SNAP_COLS.get(t, '*')} FROM {t} ORDER BY {order}"))]
    return out


def _args(fx, *extra):
    return ["--collective-db", FX, "--split-units", fx["split"], "--base-url", fx["base"], *extra]


def test_c2_migration_roundtrip(fx):
    eng = fx["eng"]
    snap0 = _snap(eng)
    assert mig.main(_args(fx)) == 0                                      # 드라이런
    assert _snap(eng) == snap0
    mig._COLS_CACHE.clear()
    assert mig.main(_args(fx, "--apply")) == 0
    assert mig.main(_args(fx, "--verify")) == 0
    with eng.connect() as c:
        keys = dict(c.execute(text("SELECT building_key, count(*) FROM collective_transactions GROUP BY 1")).all())
        assert keys == {K: 5, K1: 4, K2: 3, H1: 3, H1p1: 3, U: 1}
        km = {(o, n): (r, p, t) for o, n, r, p, t in c.execute(text(
            "SELECT old_key, new_key, reason, split_part, n_tx FROM collective_building_key_map"))}
        assert km == {
            (K, K1): ("c2_split", 1, 4), (K, K2): ("c2_split", 2, 3),
            (H0, H1p1): ("honam_sido+c2_split", 1, 3),
            (H1, H1p1): ("c2_chain", 1, 3),                              # 2단계 키 → 조각(옛 주소가 H1 로 옮겨진 뒤 안내)
            (H0, H1): ("honam_sido", 0, 0),                              # 옛 키 → 2단계 키 경로(남은 거래 없음)
        }
        reg = c.execute(text(f"""SELECT main_lot, building_year, part, source FROM {bk.C2_TABLE}
                                 WHERE base_key = :k ORDER BY main_lot"""), {"k": K}).all()
        assert [tuple(r) for r in reg] == [("10", 2010, 0, "c2_final"), ("20", 2015, 1, "c2_final"),
                                           ("30", 2020, 2, mig.C2_MIGRATE_SOURCE)]
        # 부속 표: 속성·공시지가는 본 조각(옛 키)이 그대로, 호남 옛 키 속성은 2단계 키로 재키
        attr = sorted(r[0] for r in c.execute(text("SELECT building_key FROM collective_building_attributes")))
        assert attr == sorted([K, H1, U])
        lp = sorted(r[0] for r in c.execute(text("SELECT building_key FROM collective_building_assessed_land_price")))
        assert lp == sorted([K, U])
        # 좌표(P2): C-2 분할 키 K 행 폐기, 호남 옛 키 H0 는 재키하면 C-2 키 H1 이 되므로 폐기, 판정 유지 키 U 는 그대로
        geo = sorted(r[0] for r in c.execute(text("SELECT building_key FROM collective_building_geocodes")))
        assert geo == [U]
        acts = dict(c.execute(text("SELECT building_key, p2_action FROM collective_building_geocodes_p2_before")).all())
        assert acts == {K: mig.DISCARD, H0: mig.DISCARD}
    snap1 = _snap(eng)
    mig._COLS_CACHE.clear()
    assert mig.main(_args(fx, "--apply")) == 0                           # 멱등
    assert _snap(eng) == snap1
    mig._COLS_CACHE.clear()
    assert mig.main(_args(fx, "--rollback")) == 0
    assert _snap(eng) == snap0                                           # 원상태(자동 등록 조각도 지움)


def test_c2_off_switch_keeps_c01_only(fx, monkeypatch):
    """비상 해제(CH2_COLLECTIVE_KEY_SPLIT_C2=0)면 C-2 를 하지 않는다 — 호남만."""
    monkeypatch.setenv(bk.C2_ENV_OFF, "0")
    ce = mig.engine_for(FX, read_only=True, base_url=fx["base"])
    try:
        plan = mig.build_plan(ce, None, None, {}, Path(fx["split"]))
    finally:
        ce.dispose()
    c = plan.counts["collective"]
    assert c["c2_base_keys"] == 0 and c["c2_rows_moved"] == 0
    assert set(plan.keymap["reason"]) == {"honam_sido"}


def test_build_keymap_without_c2_columns_matches_old_shape():
    import pandas as pd

    ch = pd.DataFrame({"id": [1, 2], "building_key": ["a", "a"], "new_key": ["b", "b"], "asset_type": ["apartment"] * 2,
                       "reason": ["honam_sido"] * 2, "split_part": [0, 0]})
    km, pre = mig.build_keymap(ch)
    assert km.to_dict("records") == [{"old_key": "a", "new_key": "b", "asset_type": "apartment", "reason": "honam_sido",
                                      "split_part": 0, "n": 2}]
    assert pre.to_dict("records") == km.to_dict("records")
