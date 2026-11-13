# -*- coding: utf-8 -*-
"""집합 2단계 운영 확인 스크립트(scripts/ops/collective_p2_verify) — 읽기 전용·SQL 사본 일치·비교 동작.

실제 PostgreSQL 에 임시 DB(ch2_opsverify_p2r)를 만들어 쓰고 끝나면 지운다(진짜 DB 는 건드리지 않음).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "scripts" / "ops" / "collective_p2_verify"
for p in (ROOT / "pipeline", ROOT / "pipeline" / "collective", OPS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import sql_copies as S  # noqa: E402

FX = "ch2_opsverify_p2r"


def _load(path: Path, name: str):
    cwd = os.getcwd()
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        os.chdir(cwd)


def test_sql_copies_match_pipeline_sources():
    """운영 서버엔 pipeline 이 없어 SQL 을 복사했다 → 원본이 바뀌면 이 테스트가 실패해 사본 갱신을 알린다."""
    from collective import integrity_p2 as ip
    from rent.stats_pack import BUILDING_KEY_SQL

    sys.path.insert(0, str(ROOT / "scripts" / "lab" / "collective_p2"))
    c5 = _load(ROOT / "scripts" / "lab" / "collective_p2" / "c5_verify.py", "c5v")
    assert S.MULTI_LEAF_SQL == ip.MULTI_LEAF_SQL
    assert S.ANNUAL_VS_LEDGER_SQL == ip.ANNUAL_VS_LEDGER_SQL
    assert S.SYNTH_SQL == ip.SYNTH_SQL
    assert S.C2_SHAPE_SQL == ip.C2_SHAPE_SQL
    assert S.RENT_BUILDING_KEY_SQL == BUILDING_KEY_SQL
    assert S.RENT_SYNTH_SQL == c5.rent_synth_sql()
    assert sorted(S.LEGACY_SIDO) == ip.LEGACY


def test_ops_scripts_do_not_import_pipeline():
    import re

    pat = re.compile(r"^\s*(from|import)\s+(collective|rent|built|parcel_master|app)\b", re.M)
    for f in OPS.glob("*.py"):
        assert not pat.search(f.read_text(encoding="utf-8")), f.name


def test_c22_snapshot_parser_reads_public_numbers():
    c22 = _load(ROOT / "scripts" / "lab" / "collective_p2" / "c22_insight_recompute.py", "c22")
    assert c22.ts_snapshot("08")["eligible"] == 6958
    assert c22.ts_snapshot("14")["nHeadline"] == 104
    assert c22.ts_snapshot("03")["eligible"] == 1086
    assert c22.ts_snapshot("12")["rows"] == 818
    h = c22.headline("03", {"summary": {"n_buildings_scanned": 5, "n_eligible": 4}, "phase3": {"n_known": 3, "n_yes": 1, "n_no": 2}})
    assert h == {"scanned": 5, "eligible": 4, "known": 3, "nYes": 1, "nNo": 2}
    assert all(c22.REHEARSAL_RE.match(v) for v in c22.SIDES["after"].values())
    assert not any(c22.REHEARSAL_RE.match(v) for v in c22.SIDES["before"].values())


@pytest.fixture(scope="module")
def fx():
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
    url = base.set(database=FX)
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("""CREATE TABLE collective_transactions (id bigserial PRIMARY KEY, building_key text, building_name text,
                          asset_type text, addr1 text, addr3 text, addr4 text, addr5 text, beopjungri_code text,
                          lot_number text, road_name text, building_year int, contract_date date, contract_year int,
                          unit_price float8, is_valid bool)"""))
        c.execute(text("CREATE TABLE collective_commercial_transactions (id bigserial PRIMARY KEY, addr1 text)"))
        c.execute(text("CREATE TABLE built_transactions (id bigserial PRIMARY KEY, addr1 text, contract_date date)"))
        c.execute(text("CREATE TABLE rent_transactions (id bigserial PRIMARY KEY, addr1 text)"))
        c.execute(text("CREATE TABLE built_scope_stats (as_of_month date, addr1 text)"))
        c.execute(text("""CREATE TABLE collective_building_stats (as_of_month date, window_years int, asset_type text,
                          building_key text, period_start date, period_end date, addr3 text, addr4 text, addr5 text,
                          beopjungri_code text, lot_number text, road_name text)"""))
        for t in ("collective_building_attributes", "collective_building_assessed_land_price", "collective_building_geocodes"):
            c.execute(text(f"CREATE TABLE {t} (building_key text)"))
        c.execute(text("""INSERT INTO collective_transactions (building_key, building_name, asset_type, addr1, beopjungri_code,
                          lot_number, building_year, contract_date, contract_year, unit_price, is_valid) VALUES
                          ('a1', 'x', 'apartment', '서울특별시', '1111010100', '10', 2010, '2026-09-03', 2026, 100, true),
                          ('b2', 'y', 'apartment', '전라남도', '4611010100', '20', 2011, '2026-10-03', 2026, 100, true),
                          ('c3', 'z', 'rowhouse', '서울특별시', '1111010100', '30', 2012, '2026-10-05', 2026, 100, true)"""))
        c.execute(text("INSERT INTO collective_building_stats (as_of_month, window_years, asset_type, building_key) VALUES "
                       "('2026-10-01', 5, 'apartment', 'a1'), ('2026-10-01', 5, 'apartment', 'b2')"))
        c.execute(text("INSERT INTO collective_building_attributes VALUES ('a1')"))
        c.execute(text("INSERT INTO built_scope_stats VALUES ('2026-10-01', '광주광역시')"))
    yield url.render_as_string(hide_password=False), eng
    eng.dispose()
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {FX} WITH (FORCE)"))
    admin.dispose()


def test_sessions_are_read_only(fx):
    from sqlalchemy import text

    import _common as C

    url, _ = fx
    with C.ro_conn(url) as c:
        assert c.execute(text("SHOW transaction_read_only")).scalar() == "on"
        with pytest.raises(Exception, match="read-only"):
            c.execute(text("INSERT INTO rent_transactions (addr1) VALUES ('x')"))


def test_timeout_is_recorded_not_raised(fx):
    import _common as C

    url, _ = fx
    t = C.Timed()
    with C.ro_conn(url) as c:
        assert t.run(c, "sleep", "SELECT pg_sleep(2)", timeout_ms=200) is None
        assert t.run(c, "after", "SELECT 1", fetch="scalar") == 1     # 시간 초과 뒤에도 세션은 쓸 수 있음
    assert t.log[0]["ok"] is False and t.log[0]["error"] == "시간 초과" and t.log[1]["ok"]


def test_hash_compare_detects_one_changed_row(fx, tmp_path):
    from sqlalchemy import text

    import _common as C

    hc = _load(OPS / "prod_hash_compare.py", "hc")
    url, eng = fx
    tables = ["collective_transactions", "built_scope_stats", "rent_transactions"]
    with C.ro_conn(url) as c:
        s1 = hc.snapshot(c, tables, exclude=[])
    assert hc.compare(s1, s1) == []
    assert "bk=a" in s1["tables"]["collective_transactions"] and s1["tables"]["built_scope_stats"].keys() == {"all"}
    with eng.begin() as c:
        c.execute(text("UPDATE collective_transactions SET unit_price = 101 WHERE building_key = 'b2'"))
    try:
        with C.ro_conn(url) as c:
            s2 = hc.snapshot(c, tables, exclude=[])
        d = hc.compare(s1, s2)
        assert [(x[0], x[1]) for x in d] == [("collective_transactions", "bk=b")]   # 바뀐 조각만
        with C.ro_conn(url) as c:
            s3 = hc.snapshot(c, tables, exclude=["unit_price"])
            s4 = hc.snapshot(c, tables, exclude=["unit_price"])
        assert hc.compare(s3, s4) == []
    finally:
        with eng.begin() as c:
            c.execute(text("UPDATE collective_transactions SET unit_price = 100 WHERE building_key = 'b2'"))


def test_sync_check_marks_heavy_tables_until_approved(fx):
    import _common as C

    sc = _load(OPS / "prod_sync_check.py", "sc")
    url, _ = fx
    with C.ro_conn(url) as c:
        light = sc.snapshot(c, allow_heavy=False, heavy_rows=-1)          # 모든 표를 「큰 표」로 → 승인 필요
        heavy = sc.snapshot(c, allow_heavy=True, heavy_rows=-1)
    assert all("승인 필요" in v["status"] for v in light["tables"].values())
    ct = heavy["tables"]["collective_transactions"]
    assert ct["rows"] == 3 and ct["recent_months"] == {"2026-09": 1, "2026-10": 2}
    assert heavy["tables"]["built_scope_stats"]["max_as_of_month"] == "2026-10-01"
    assert "max_as_of_month" not in heavy["tables"]["rent_transactions"]         # as_of_month 열 없는 표는 안 셈
    d, pending = sc.compare(heavy, {**heavy, "tables": {**heavy["tables"],
                                                        "collective_transactions": {**ct, "rows": 4}}})
    assert d == [("collective_transactions", "rows", 3, 4)] and pending == []
    d, pending = sc.compare(light, heavy)
    assert d == [] and "collective_transactions" in pending


def test_c5_core_light_metrics_and_violations(fx):
    import _common as C

    c5 = _load(OPS / "prod_c5_core.py", "pc5")
    url, _ = fx
    with C.ro_conn(url) as c, C.ro_conn(url) as r, C.ro_conn(url) as b:
        m = c5.collect(c, r, b, heavy_ms=60_000, skip_heavy=True, split_units=None)
    assert m["as_of"] == "2026-10-01"
    assert m["legacy_sido.collective_transactions"] == 1 and m["legacy_sido.built_scope_stats(as_of)"] == 1
    assert m["coverage.attributes"] == 0.5 and m["coverage.attributes.n"] == [1, 2]
    bad = {k for k, _, _ in c5.violations(m)}
    assert {"legacy_sido.collective_transactions", "legacy_sido.built_scope_stats(as_of)"} <= bad
    expect = {k: v for k, v in m.items() if not k.startswith("_")}
    expect["coverage.attributes"] = 1.0
    assert ("coverage.attributes", 0.5, 1.0) in c5.violations(m, expect)
    assert not any("쿼리 실패" in k for k in bad)


def test_local_scope_dryrun_guard_accepts_only_real_local_names():
    sd = _load(ROOT / "scripts" / "ops" / "collective_p2_local" / "scope_dryrun.py", "sd")
    sd.guard_url("postgresql+psycopg2://u:p@localhost:5432/collective_stats", "collective_stats")
    sd.guard_url("postgresql+psycopg2://u:p@127.0.0.1/parcel_master", "parcel_master")
    for url, want in (("postgresql+psycopg2://u:p@localhost/collective_stats_p2r", "collective_stats"),   # 리허설
                      ("postgresql+psycopg2://u:p@13.209.203.178/collective_stats", "collective_stats"),  # 원격
                      ("postgresql+psycopg2://u:p@localhost/rent_stats", "collective_stats"),            # 다른 DB
                      ("postgresql+psycopg2://u:p@localhost/parcel_master_p2r", "parcel_master")):
        with pytest.raises(SystemExit):
            sd.guard_url(url, want)
    assert sd.outside({"a", "b"}, {"a"}) == {"b"} and sd.outside({"a"}, {"a", "c"}) == set()


def test_sums_mode_and_pg_verdict(fx):
    from sqlalchemy import text

    import _common as C

    hc = _load(OPS / "prod_hash_compare.py", "hc2")
    url, eng = fx
    tables = ["collective_transactions", "built_scope_stats"]
    with C.ro_conn(url) as c:
        s1 = hc.snapshot(c, tables, exclude=["id"], mode="sums")
        h1 = hc.snapshot(c, tables, exclude=[], mode="hash")
    assert s1["mode"] == "sums" and hc.compare(s1, s1) == []
    part = s1["tables"]["collective_transactions"]["bk=b"]
    assert part["rows"] == "1" and part["unit_price.sum"] == "100" and part["addr1.len"] == "4"
    assert hc.compare(s1, h1)[0][1] == "방식 다름"
    with eng.begin() as c:
        c.execute(text("UPDATE collective_transactions SET unit_price = 101 WHERE building_key = 'b2'"))
    try:
        with C.ro_conn(url) as c:
            s2 = hc.snapshot(c, tables, exclude=["id"], mode="sums")
        assert [(x[0], x[1]) for x in hc.compare(s1, s2)] == [("collective_transactions", "bk=b")]
    finally:
        with eng.begin() as c:
            c.execute(text("UPDATE collective_transactions SET unit_price = 100 WHERE building_key = 'b2'"))
    # 판정: hash 같음 / hash 만 다름 / sums 도 다름
    same = {"hash": h1, "sums": s1}
    other_hash = {"hash": {**h1, "tables": {**h1["tables"], "built_scope_stats": {"all": [1, "x"]}}}, "sums": s1}
    assert hc.pg_verdict(same, same).startswith("hash 같음")
    assert hc.pg_verdict(same, other_hash).startswith("hash 만 다름")
    assert hc.pg_verdict(same, {"hash": other_hash["hash"], "sums": s2}).startswith("sums 도 다름")
