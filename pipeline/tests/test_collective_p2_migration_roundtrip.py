# -*- coding: utf-8 -*-
"""집합 2단계 Phase B — 소형 fixture DB 왕복: 이전 → 검증 → 재실행(멱등) → 되돌리기 → 원상태.

로컬 PostgreSQL 서버에 임시 DB `ch2_p2r_fixture`를 만들고 끝나면 지운다(실제 DB는 건드리지 않음).
서버에 붙지 못하거나 DB를 만들 권한이 없으면 skip.
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
from collective import fix_p2_deal_types as fdt  # noqa: E402
from collective import migrate_p2_keys as mig  # noqa: E402
from collective.mart_replace import delete_as_of, prune_annual, stale_annual_report  # noqa: E402
from collective.rep_address_sql import rep_address_query  # noqa: E402
from collective_commercial.cluster_keys import make_road_cluster_key  # noqa: E402

FX = "ch2_p2r_fixture"
N = "전남광주통합특별시"


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _key(asset, a1, a2, a3, name):
    return _sha(f"{asset}|{a1}|{a2}|{a3}|name:{name}")


A_OLD = _key("apartment", "광주광역시", "광산구", "수완동", "자이")
A_NEW = _key("apartment", N, "광산구", "수완동", "자이")
B_OLD = _key("apartment", "전라남도", "순천시", "조례동", "한양")
B_NEW = _key("apartment", N, "순천시", "조례동", "한양")
S = _key("apartment", "충청북도", "청주시", "청원구", "삼일")
S1 = _sha("apartment|충청북도|청주시|청원구|name:삼일|emd:43114111")
S2 = _sha("apartment|충청북도|청주시|청원구|name:삼일|emd:43114250")
U = _key("apartment", "서울특별시", "강남구", "역삼동", "래미안")

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
CREATE TABLE new_apartment_complex_year (id serial PRIMARY KEY, building_key text, calendar_year int);
CREATE TABLE collective_commercial_map_geocodes (cluster_key text PRIMARY KEY, label text);
CREATE TABLE built_transactions (id serial PRIMARY KEY, asset_type text, addr1 text, addr2 text, contract_year int);
CREATE TABLE rent_transactions (id serial PRIMARY KEY, transaction_hash text, asset_type text, building_key text,
  display_name text, building_name text, addr1 text, addr2 text, addr3 text, addr4 text, addr5 text,
  lot_number text, road_name text, beopjungri_code text, contract_date date);
CREATE TABLE rent_building_geocodes (building_key text PRIMARY KEY, label text);
CREATE TABLE rent_sale_building_map (sale_building_key text, rent_building_key text, asset_type text, tier text,
  built_on date, PRIMARY KEY (sale_building_key, asset_type));
"""

ORIGINAL_TABLES = {
    "collective_transactions": "id", "commercial_clusters": "id", "collective_commercial_transactions": "id",
    "collective_building_attributes": "id", "collective_building_geocodes": "building_key",
    "collective_building_assessed_land_price": "building_key, asset_type", "new_apartment_complex_year": "id",
    "collective_commercial_map_geocodes": "cluster_key", "built_transactions": "id", "rent_transactions": "id",
    "rent_building_geocodes": "building_key", "rent_sale_building_map": "sale_building_key, asset_type",
}


def _tx(addr1, addr2, addr3, addr4, name, key, code, d, price=100.0, lot="1", road="로"):
    return dict(h=_sha(f"{key}{d}{price}{code}"), a="apartment", k=key, dn=name, bn=name, a1=addr1, a2=addr2, a3=addr3,
                a4=addr4, lot=lot, road=road, code=code, y=d.year, d=d, p=price)


def _seed(c):
    rows = [
        _tx("광주광역시", "광산구", "수완동", None, "자이", A_OLD, "1233010100", date(2019, 5, 1)),
        _tx("광주광역시", "광산구", "수완동", None, "자이", A_OLD, "1233010100", date(2020, 5, 1)),
        _tx(N, "광산구", "수완동", None, "자이", A_NEW, "1233010100", date(2022, 5, 1)),
        _tx(N, "광산구", "수완동", None, "자이", A_NEW, "1233010100", date(2023, 5, 1)),
        _tx("전라남도", "순천시", "조례동", None, "한양", B_OLD, "1215010100", date(2019, 7, 1)),
        _tx("충청북도", "청주시", "청원구", "우암동", "삼일", S, "4311411100", date(2022, 1, 1), lot="10"),
        _tx("충청북도", "청주시", "청원구", "우암동", "삼일", S, "4311411100", date(2023, 1, 1), lot="10"),
        _tx("충청북도", "청주시", "청원구", "우암동", "삼일", S, "4311411100", date(2024, 1, 1), lot="10"),
        _tx("충청북도", "청주시", "청원구", "내수읍", "삼일", S, "4311425036", date(2022, 2, 1), lot="99"),
        _tx("충청북도", "청주시", "청원구", "내수읍", "삼일", S, "4311425036", date(2024, 2, 1), lot="99"),
        _tx("충청북도", "청주시", "청원구", "우암동", "삼일", S, None, date(2025, 1, 1), lot="10"),
        _tx("서울특별시", "강남구", "역삼동", None, "래미안", U, "1168010100", date(2024, 3, 1)),
        _tx("서울특별시", "강남구", "역삼동", None, "래미안", U, "1168010100", date(2024, 4, 1)),
    ]
    c.execute(text("""INSERT INTO collective_transactions (transaction_hash, asset_type, building_key, display_name,
        building_name, addr1, addr2, addr3, addr4, lot_number, road_name, beopjungri_code, contract_year, contract_date,
        unit_price) VALUES (:h,:a,:k,:dn,:bn,:a1,:a2,:a3,:a4,:lot,:road,:code,:y,:d,:p)"""), rows)
    c.execute(text("""INSERT INTO collective_building_attributes (snapshot_ym, asset_type, building_key, danji_code) VALUES
        ('202610','apartment',:a,'K1'), ('202610','apartment',:an,'K1'), ('202610','apartment',:b,'K2'),
        ('202610','apartment',:s,'K3'), ('202610','apartment',:u,'K4')"""), {"a": A_OLD, "an": A_NEW, "b": B_OLD, "s": S, "u": U})
    c.execute(text("INSERT INTO collective_building_geocodes VALUES (:a,'a'), (:s,'s'), (:u,'u')"), {"a": A_OLD, "s": S, "u": U})
    c.execute(text("""INSERT INTO collective_building_assessed_land_price VALUES (:a,'apartment',1), (:an,'apartment',2),
        (:b,'apartment',3), (:s,'apartment',4)"""), {"a": A_OLD, "an": A_NEW, "b": B_OLD, "s": S})
    c.execute(text("INSERT INTO new_apartment_complex_year (building_key, calendar_year) VALUES (:s, 2024)"), {"s": S})
    # 비주거: C1 옛 이름 → 새 이름 cluster 이미 있음(병합) / C2 옛 이름만(재키)
    c1o = make_road_cluster_key(asset_type="collective_shop", addr1="광주광역시", addr2="서구", addr3="치평동", addr4=None, road_name="상무대로")
    c1n = make_road_cluster_key(asset_type="collective_shop", addr1=N, addr2="서구", addr3="치평동", addr4=None, road_name="상무대로")
    c2o = make_road_cluster_key(asset_type="collective_shop", addr1="전라남도", addr2="무안군", addr3="삼향읍", addr4="남악리", road_name="남악로")
    c.execute(text("""INSERT INTO commercial_clusters (cluster_key, asset_type, addr1, addr2, addr3, addr4, road_name) VALUES
        (:c1o,'collective_shop','광주광역시','서구','치평동',NULL,'상무대로'),
        (:c1n,'collective_shop',:n,'서구','치평동',NULL,'상무대로'),
        (:c2o,'collective_shop','전라남도','무안군','삼향읍','남악리','남악로')"""), {"c1o": c1o, "c1n": c1n, "c2o": c2o, "n": N})
    # C2 거래는 리를 addr5 로 옮긴 뒤(키는 옛 addr4 규칙)를 재현
    c.execute(text("""INSERT INTO collective_commercial_transactions (transaction_hash, cluster_id, asset_type, cluster_key,
        addr1, addr2, addr3, addr4, addr5, road_name, contract_year, contract_date, price, gross_area) VALUES
        ('h1',1,'collective_shop',:c1o,'광주광역시','서구','치평동',NULL,NULL,'상무대로',2019,'2019-03-01',1,1),
        ('h2',1,'collective_shop',:c1o,'광주광역시','서구','치평동',NULL,NULL,'상무대로',2020,'2020-03-01',1,1),
        ('h3',2,'collective_shop',:c1n,:n,'서구','치평동',NULL,NULL,'상무대로',2023,'2023-03-01',1,1),
        ('h4',3,'collective_shop',:c2o,'전라남도','무안군','삼향읍',NULL,'남악리','남악로',2020,'2020-03-01',1,1)"""),
              {"c1o": c1o, "c1n": c1n, "c2o": c2o, "n": N})
    c.execute(text("INSERT INTO built_transactions (asset_type, addr1, addr2, contract_year) VALUES "
                   "('commercial','광주광역시','서구',2019), ('factory','전라남도','무안군',2020), ('commercial',:n,'서구',2022)"), {"n": N})
    c.execute(text("""INSERT INTO rent_transactions (transaction_hash, asset_type, building_key, display_name, building_name,
        addr1, addr2, addr3, addr4, lot_number, road_name, beopjungri_code, contract_date) VALUES
        ('r1','apartment',:s,'삼일','삼일','충청북도','청주시','청원구','우암동','10','로','4311411100','2024-01-01'),
        ('r2','apartment',:s,'삼일','삼일','충청북도','청주시','청원구','내수읍','99','로','4311425036','2024-01-01'),
        ('r3','apartment',:u,'래미안','래미안','서울특별시','강남구','역삼동',NULL,'1','로','1168010100','2024-01-01')"""),
              {"s": S, "u": U})
    c.execute(text("INSERT INTO rent_building_geocodes VALUES (:s,'s')"), {"s": S})
    c.execute(text("INSERT INTO rent_sale_building_map VALUES (:s,:s,'apartment','exact','2026-11-01'), (:u,:u,'apartment','exact','2026-11-01')"),
              {"s": S, "u": U})


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
    split = tmp_path_factory.mktemp("p2") / "split.csv"
    split.write_text("base_key,asset_type,emd8,unit_emd8,part,decision,reason\n"
                     f"{S},apartment,43114111,43114111,1,split,a_evidence\n"
                     f"{S},apartment,43114250,43114250,2,split,a_evidence\n", encoding="utf-8")
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
        for t, order in ORIGINAL_TABLES.items():
            out[t] = [tuple(r) for r in c.execute(text(f"SELECT * FROM {t} ORDER BY {order}"))]
    return out


def _args(fx, *extra):
    return ["--collective-db", FX, "--built-db", FX, "--rent-db", FX, "--split-units", fx["split"],
            "--base-url", fx["base"], *extra]


def test_roundtrip(fx):
    eng = fx["eng"]
    snap0 = _snap(eng)
    assert mig.main(_args(fx)) == 0                       # 드라이런: 바뀌지 않음
    assert _snap(eng) == snap0
    mig._COLS_CACHE.clear()
    assert mig.main(_args(fx, "--apply")) == 0
    assert mig.main(_args(fx, "--verify")) == 0           # 검증 지표 전부 통과
    with eng.connect() as c:
        keys = dict(c.execute(text("SELECT building_key, count(*) FROM collective_transactions GROUP BY 1")).all())
        assert keys == {A_NEW: 4, B_NEW: 1, S1: 4, S2: 2, U: 2}            # 행 수 합 보존, 코드 없는 행은 1조각
        assert c.execute(text("SELECT count(*) FROM collective_transactions WHERE addr1 IN ('광주광역시','전라남도')")).scalar() == 0
        km = {(o, n): (r, p) for o, n, r, p in c.execute(text(
            "SELECT old_key, new_key, reason, split_part FROM collective_building_key_map"))}
        assert km == {(A_OLD, A_NEW): ("honam_sido", 0), (B_OLD, B_NEW): ("honam_sido", 0),
                      (S, S1): ("split", 1), (S, S2): ("split", 2)}
        # 부속 표: A 옛 행은 새 키 행이 있어 제거, B 는 재키, 분할 키는 제거(재생성 대상)
        attr = sorted(r[0] for r in c.execute(text("SELECT building_key FROM collective_building_attributes")))
        assert attr == sorted([A_NEW, B_NEW, U])
        geo = sorted(r[0] for r in c.execute(text("SELECT building_key FROM collective_building_geocodes")))
        assert geo == sorted([A_NEW, U])                                    # A 옛 지오코드는 새 키로 재키
        assert c.execute(text("SELECT count(*) FROM new_apartment_complex_year")).scalar() == 0
        # 비주거: C1 은 기존 새 cluster(id 2)로 병합, C2 는 재키
        cl = c.execute(text("SELECT id, addr1 FROM commercial_clusters ORDER BY id")).all()
        assert [r[0] for r in cl] == [2, 3] and all(r[1] == N for r in cl)
        assert c.execute(text("SELECT count(*) FROM collective_commercial_transactions WHERE cluster_id = 2")).scalar() == 3
        assert c.execute(text("SELECT count(*) FROM built_transactions WHERE addr1 = :n"), {"n": N}).scalar() == 3
        rk = sorted(r[0] for r in c.execute(text("SELECT building_key FROM rent_transactions")))
        assert rk == sorted([S1, S2, U])                                    # 임대도 같은 새 키(매매와 일치)
        assert c.execute(text("SELECT count(*) FROM rent_building_geocodes")).scalar() == 0
    snap1 = _snap(eng)
    mig._COLS_CACHE.clear()
    assert mig.main(_args(fx, "--apply")) == 0            # 멱등
    assert _snap(eng) == snap1
    mig._COLS_CACHE.clear()
    assert mig.main(_args(fx, "--rollback")) == 0
    assert _snap(eng) == snap0                            # 원상태(행 단위 동일)


def test_rep_address_and_mart_replace(fx):
    eng = fx["eng"]
    sql = rep_address_query(
        base_sql="SELECT building_key, asset_type, addr1, addr2, addr3, addr4, addr5, beopjungri_code, sigungu_code, "
                 "lot_number, road_name, unit_price, contract_date FROM collective_transactions WHERE building_key = :k",
        group_cols=["building_key", "asset_type"], aggregates="count(*) AS n")
    with eng.connect() as c:
        r = c.execute(text(sql), {"k": U}).mappings().one()
        assert r["n"] == 2 and r["beopjungri_code"] == "1168010100"
    with eng.begin() as c:
        c.execute(text("""INSERT INTO collective_transactions (asset_type, building_key, addr3, addr4, beopjungri_code,
            lot_number, contract_year, contract_date, unit_price, building_name) VALUES
            ('apartment','TIE','구','갑동','1111111111','1',2024,'2024-01-01',1,'x'),
            ('apartment','TIE','구','을동','2222222222','2',2025,'2025-01-01',1,'x'),
            ('apartment','TIE','구','병동','3333333333','3',2023,'2023-01-01',1,'x'),
            ('apartment','TIE','구','병동','3333333333','3',2023,'2023-02-01',1,'x')"""))
    with eng.connect() as c:
        r = c.execute(text(sql), {"k": "TIE"}).mappings().one()
        assert r["addr4"] == "병동" and r["n"] == 4                          # 최다 거래 세트
    with eng.begin() as c:
        c.execute(text("DELETE FROM collective_transactions WHERE building_key='TIE' AND addr4='병동'"))
    with eng.connect() as c:
        assert c.execute(text(sql), {"k": "TIE"}).mappings().one()["addr4"] == "을동"   # 동률 → 최신 계약일
    with eng.begin() as c:
        c.execute(text("DELETE FROM collective_transactions WHERE building_key='TIE'"))
        c.execute(text("CREATE TABLE t_stats (as_of_month date, window_years int, asset_type text, building_key text)"))
        c.execute(text("INSERT INTO t_stats VALUES ('2026-10-01',5,'apartment','x'), ('2026-10-01',7,'apartment','y'), "
                       "('2026-09-01',5,'apartment','z')"))
        c.execute(text("CREATE TABLE t_annual (building_key text, asset_type text, contract_year int, addr1 text, "
                       "batch_id text, count int, computed_at timestamptz DEFAULT now())"))
        c.execute(text("""INSERT INTO t_annual VALUES
            ('cur','apartment',2024,'서울특별시','NOW',1), ('gone','apartment',2024,'서울특별시','OLD',1),
            ('hon','apartment',2019,'광주광역시','OLD',1), ('hon2','apartment',2020,:n,'NOW',1),
            ('stale','apartment',2020,'경기도','OLD',1), ('old','apartment',2015,'광주광역시','LT',1)"""), {"n": N})
    assert delete_as_of(eng, "t_stats", as_of=date(2026, 10, 1), windows=[5]) == 1
    res = prune_annual(eng, "t_annual", batch_id="NOW")
    assert res == {"deleted_2021_plus": 1, "deleted_2019_2020_legacy_sido": 1, "deleted_2010_2018": 0}
    with eng.connect() as c:
        left = sorted(r[0] for r in c.execute(text("SELECT building_key FROM t_annual")))
        assert left == ["cur", "hon2", "old", "stale"]          # 2019~2020 묵은 행(stale)·2010~2018 은 남김
        rep = stale_annual_report(c, "t_annual", "collective_transactions", "building_key", batch_id="NOW")
        assert [(r[1], r[2], r[3]) for r in rep] == [(2020, "경기도", "원장 빌더")]


_REP_BASE = ("SELECT building_key, asset_type, addr1, addr2, addr3, addr4, addr5, beopjungri_code, sigungu_code, "
             "lot_number, road_name, unit_price, contract_date, contract_year FROM {src} WHERE true {addr1_clause}")


def _legacy_join(sql: str, group_cols: list[str]) -> str:
    """옛(IS NOT DISTINCT FROM) 조인 SQL — 새 SQL 에서 조인만 되돌리고 NULL 검사를 뺀다."""
    from collective.rep_address_sql import _null_guard_sql

    old = sql.replace(f"WHERE {_null_guard_sql(group_cols)} = 0\n", "")
    for c in group_cols:
        old = old.replace(f"b.{c} = r.{c}", f"b.{c} IS NOT DISTINCT FROM r.{c}")
    assert "IS NOT DISTINCT FROM" in old and "count(*) = 0" not in old
    return old


def test_rep_address_eq_join_matches_legacy_join(fx):
    """`=` 조인 결과 = 옛 IS NOT DISTINCT FROM 결과(그룹 열 NULL 없을 때) — rolling·annual 모양 둘 다."""
    eng = fx["eng"]
    with eng.begin() as c:
        c.execute(text("""INSERT INTO collective_transactions (asset_type, building_key, addr1, addr3, addr4, beopjungri_code,
            lot_number, contract_year, contract_date, unit_price, building_name) VALUES
            ('apartment','EQ1','서울특별시','구','갑동','1111111111','1',2024,'2024-01-01',10,'x'),
            ('apartment','EQ1','서울특별시','구','을동','2222222222','2',2024,'2024-03-01',20,'x'),
            ('apartment','EQ1','서울특별시','구','을동','2222222222','2',2025,'2025-01-01',30,'x'),
            ('officetel','EQ1','서울특별시','구',NULL,NULL,NULL,2025,NULL,40,'x'),
            ('apartment','EQ2','서울특별시','구','병동','3333333333','3',2023,'2023-01-01',50,'x')"""))
    try:
        for group_cols in (["building_key", "asset_type"], ["building_key", "asset_type", "contract_year"]):
            new = rep_address_query(base_sql=_REP_BASE.format(src="collective_transactions", addr1_clause="{addr1_clause}"),
                                    group_cols=group_cols,
                                    aggregates="count(*) AS n, array_agg(b.unit_price ORDER BY b.unit_price) AS prices",
                                    ).format(addr1_clause="")
            old = _legacy_join(new, group_cols)
            order = ", ".join(str(i + 1) for i in range(len(group_cols)))
            with eng.connect() as c:
                a = [tuple(r) for r in c.execute(text(f"SELECT * FROM ({new}) q ORDER BY {order}"))]
                b = [tuple(r) for r in c.execute(text(f"SELECT * FROM ({old}) q ORDER BY {order}"))]
            assert a == b and len(a) >= 4
            assert any(r[0] == "EQ1" and r[1] == "officetel" for r in a)   # 주소 칸이 NULL 인 그룹도 남는다
    finally:
        with eng.begin() as c:
            c.execute(text("DELETE FROM collective_transactions WHERE building_key IN ('EQ1','EQ2')"))


def test_rep_address_null_group_col_raises(fx):
    """그룹 열 NULL 이 있으면 `=` 조인이 조용히 빠뜨리지 않고 쿼리가 오류로 끝난다(전부 NULL 이어도)."""
    from sqlalchemy.exc import DataError

    from collective.rep_address_sql import NULL_GUARD_TAG

    eng = fx["eng"]
    with eng.begin() as c:
        c.execute(text("CREATE TABLE t_rep_null AS SELECT * FROM collective_transactions WHERE false"))
        c.execute(text("""INSERT INTO t_rep_null (asset_type, building_key, addr3, contract_year, contract_date, unit_price,
            building_name) VALUES ('apartment','OK','구',2024,'2024-01-01',1,'x'), ('apartment',NULL,'구',2024,'2024-01-01',1,'x')"""))
    try:
        sql = rep_address_query(base_sql=_REP_BASE.format(src="t_rep_null", addr1_clause=""),
                                group_cols=["building_key", "asset_type"], aggregates="count(*) AS n")
        for keep in ("building_key IS NULL OR building_key = 'OK'", "building_key IS NULL"):
            with eng.connect() as c, pytest.raises(DataError) as ei:
                c.execute(text(sql.replace("WHERE true", f"WHERE ({keep})", 1))).all()
            assert NULL_GUARD_TAG in str(ei.value) and "rows=1" in str(ei.value)
        with eng.connect() as c:   # NULL 없으면 그대로 동작
            rows = c.execute(text(sql.replace("WHERE true", "WHERE building_key = 'OK'", 1))).mappings().all()
            assert [(r["building_key"], r["n"]) for r in rows] == [("OK", 1)]
    finally:
        with eng.begin() as c:
            c.execute(text("DROP TABLE IF EXISTS t_rep_null"))


def test_deal_type_apply_and_rollback(fx):
    eng = fx["eng"]
    with eng.begin() as c:
        mig.assert_rehearsal_db(c, FX)
        ids = [r[0] for r in c.execute(text("SELECT id FROM collective_transactions ORDER BY id LIMIT 2"))]
        c.execute(text("UPDATE collective_transactions SET deal_type = '경남 김해시' WHERE id = :i"), {"i": ids[0]})
    import pandas as pd

    upd = pd.DataFrame({"id": ids, "deal_type": ["경남 김해시", None], "new_deal_type": ["중개거래", "직거래"]})
    cupd = pd.DataFrame({"id": [1], "deal_type": [None], "new_deal_type": ["직거래"]})
    with eng.begin() as c:  # 실제 실행처럼 한 트랜잭션에서 두 표
        assert fdt.apply_updates(c, "collective_transactions", upd) == 2
        assert fdt.apply_updates(c, "collective_commercial_transactions", cupd) == 1
        assert fdt.rollback_table(c, "collective_commercial_transactions") == 1
    with eng.connect() as c:
        assert [r[0] for r in c.execute(text("SELECT deal_type FROM collective_transactions WHERE id = ANY(:i) ORDER BY id"),
                                        {"i": ids})] == ["중개거래", "직거래"]
    with eng.begin() as c:
        assert fdt.rollback_table(c, "collective_transactions") == 2
    with eng.connect() as c:
        assert [r[0] for r in c.execute(text("SELECT deal_type FROM collective_transactions WHERE id = ANY(:i) ORDER BY id"),
                                        {"i": ids})] == ["경남 김해시", None]
