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
    r = sc.compare(heavy, {**heavy, "tables": {**heavy["tables"], "collective_transactions": {**ct, "rows": 4}}})
    assert r["status"] == "diff" and r["diff"] == [("collective_transactions", "rows", 3, 4)] and r["unverified"] == []
    r = sc.compare(light, heavy)                                    # 큰 표를 건너뜀 → 차이 없어도 검증 못 함
    assert r["status"] == "unverified" and r["diff"] == [] and ("collective_transactions" in {t for t, _ in r["unverified"]})
    assert sc.compare(heavy, heavy)["status"] == "pass"


def test_sync_check_required_tables_prod_written_tables_and_exit_codes(fx, tmp_path):
    import json

    import _common as C

    sc = _load(OPS / "prod_sync_check.py", "sc3")
    url, _ = fx
    with C.ro_conn(url) as c:
        snap = sc.snapshot(c, allow_heavy=True, heavy_rows=-1)
    # 필수 표가 양쪽 모두 없으면 검증 못 함(DB 이름이 collective_stats 인 척)
    a = {**snap, "db": "collective_stats"}
    r = sc.compare(a, a)
    assert r["status"] == "unverified" and ("market_stats", "필수 표 없음") in r["unverified"]
    # 운영 API 가 쓰는 표의 차이는 허용 목록(멈춤 사유 아님)
    geo = {**snap, "tables": {**snap["tables"], "collective_building_geocodes": {"rows": 5, "est_rows": 5, "heavy": False}}}
    r = sc.compare(snap, geo)
    assert r["status"] == "pass" and r["allowed_diff"] and r["diff"] == []
    # CLI 종료 코드 0/1/2 와 결과 파일
    f1, f2 = tmp_path / "l.json", tmp_path / "r.json"
    C.write_json(f1, snap)
    C.write_json(f2, snap)
    out = tmp_path / "res.json"
    assert sc.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 0
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["kind"] == "prod_sync_check" and res["status"] == "pass" and res["left_db"] == snap["db"] and res["created_at"]
    C.write_json(f2, {**snap, "tables": {**snap["tables"], "collective_transactions": {**snap["tables"]["collective_transactions"], "rows": 9}}})
    assert sc.main(["compare", str(f1), str(f2)]) == 1
    C.write_json(f2, {**snap, "tables": {**snap["tables"], "collective_transactions": {"est_rows": 3, "heavy": True, "status": "승인 필요"}}})
    assert sc.main(["compare", str(f1), str(f2)]) == 2


def test_c5_core_light_metrics_and_violations(fx):
    import _common as C

    c5 = _load(OPS / "prod_c5_core.py", "pc5")
    url, _ = fx
    with C.ro_conn(url) as c, C.ro_conn(url) as r, C.ro_conn(url) as b:
        m = c5.collect(c, r, b, heavy_ms=60_000, skip_heavy=True, split_units=None)
        full = c5.collect(c, r, b, heavy_ms=60_000, skip_heavy=False, split_units=None)
    assert m["as_of"] == "2026-10-01"
    # --skip-heavy: 무거운 검사는 실행하지 않고 「건너뜀」, 가벼운 검사는 10초 제한으로 실행
    assert m["legacy_sido.collective_transactions"] == c5.SKIPPED and m["annual_vs_ledger_mismatch"] == c5.SKIPPED
    assert m["c2_shape_pending"] == c5.SKIPPED and m["synthetic.building_stats"] == c5.SKIPPED
    assert not any(x["query"].startswith("옛 시도명 collective") for x in m["_timings"])
    assert all(x["timeout_ms"] == C.LIGHT_MS for x in m["_timings"])
    assert m["legacy_sido.built_scope_stats(as_of)"] == 1
    assert m["coverage.attributes"] == 0.5 and m["coverage.attributes.n"] == [1, 2]
    assert c5.status_of(m) == "diff"                                      # 가벼운 검사에서 이미 위반(scope 옛 시도명)
    assert full["legacy_sido.collective_transactions"] == 1
    bad = {k for k, _, _ in c5.violations(full)}
    assert {"legacy_sido.collective_transactions", "legacy_sido.built_scope_stats(as_of)"} <= bad
    expect = {k: v for k, v in full.items() if not k.startswith("_")}
    expect["coverage.attributes"] = 1.0
    assert ("coverage.attributes", 0.5, 1.0) in c5.violations(full, expect)
    # 위반 없이 건너뜀만 있으면 「검증 못 함」
    clean = {"db": {}, "as_of": "x", "legacy_sido.a": 0, "annual_vs_ledger_mismatch": c5.SKIPPED, "_timings": []}
    assert c5.status_of(clean) == "unverified" and c5.EXIT["unverified"] == 2
    assert c5.status_of({**clean, "annual_vs_ledger_mismatch": 0}) == "pass"
    assert c5.status_of({**clean, "c2_shape_pending": 3}) == "diff"         # c2_shape_pending 은 0 이어야 함


def test_c5_old_key_check_uses_exact_c01_reasons():
    src = (OPS / "prod_c5_core.py").read_text(encoding="utf-8")
    c5 = _load(OPS / "prod_c5_core.py", "pc5r")
    assert c5.C01_SPLIT_REASONS == ("split", "honam_sido+split") and "c2_split" not in c5.C01_SPLIT_REASONS
    assert "reason IN :r" in src and "LIKE '%split%')\"" not in src
    assert "c2_shape_pending" in c5.ZERO


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


def test_scope_dryrun_host_guard_blocks_bypass():
    """호스트는 SQLAlchemy 실제 접속 인자로 판정 — URL 쿼리·환경변수 우회를 막는다."""
    sd = _load(ROOT / "scripts" / "ops" / "collective_p2_local" / "scope_dryrun.py", "sd2")
    ok = "postgresql+psycopg2://u:p@localhost:5432/collective_stats"
    sd.guard_url(ok, "collective_stats", environ={})
    sd.guard_url("postgresql+psycopg2://u:p@/collective_stats", "collective_stats", environ={})            # 소켓(환경변수 없음)
    sd.guard_url("postgresql+psycopg2://u:p@/collective_stats", "collective_stats", environ={"PGHOST": "127.0.0.1"})
    assert sd.connect_params(ok)["host"] == "localhost"
    for url, env in (
        ("postgresql+psycopg2://u:p@localhost/collective_stats?host=13.209.203.178", {}),   # URL 은 localhost, 실제는 원격
        ("postgresql+psycopg2://u:p@localhost/collective_stats?hostaddr=10.0.0.5", {}),
        ("postgresql+psycopg2://u:p@localhost/collective_stats?HOST=10.0.0.5", {}),
        ("postgresql+psycopg2://u:p@localhost/collective_stats?service=prod", {}),
        ("postgresql+psycopg2://u:p@/collective_stats", {"PGHOST": "13.209.203.178"}),      # 호스트 비고 환경변수가 원격
        ("postgresql+psycopg2://u:p@/collective_stats", {"PGHOSTADDR": "10.0.0.5"}),
        ("postgresql+psycopg2://u:p@/collective_stats", {"PGSERVICE": "prod"}),
        ("postgresql+psycopg2://u:p@localhost,13.209.203.178/collective_stats", {}),        # 여러 호스트 중 원격
    ):
        with pytest.raises(SystemExit):
            sd.guard_url(url, "collective_stats", environ=env)


def test_scope_dryrun_deadline_and_timeouts_wired():
    sd = _load(ROOT / "scripts" / "ops" / "collective_p2_local" / "scope_dryrun.py", "sd3")
    d = sd.Deadline(0, start_timer=False)
    with pytest.raises(SystemExit) as e:
        d.check("x")
    assert e.value.code == sd.TIMEOUT_EXIT
    # 실제 타이머: 시간이 되면(쿼리 도중이라도) 끝내는 함수가 불린다 — 테스트에서는 os._exit 대신 이벤트
    import threading

    ev = threading.Event()
    t = sd.Deadline(0.002, on_expire=ev.set)        # 0.12초
    assert ev.wait(5), "타이머가 울리지 않음"
    t.cancel()
    t2 = sd.Deadline(0.05, on_expire=ev.clear)     # 취소하면 울리지 않음
    t2.cancel()
    assert ev.is_set()
    src = (ROOT / "scripts" / "ops" / "collective_p2_local" / "scope_dryrun.py").read_text(encoding="utf-8")
    assert "statement_timeout=" in src and "SHOW statement_timeout" in src and src.count("dl.check(") >= 5


def test_hash_compare_three_states_and_default_targets(fx, tmp_path):
    import json

    from sqlalchemy import text

    import _common as C

    hc = _load(OPS / "prod_hash_compare.py", "hc3")
    url, eng = fx
    assert "collective_building_key_c2_units" in hc.TARGETS["collective_stats"]
    with eng.begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS rent_transactions_p2_before (id int)"))
    with C.ro_conn(url) as c:
        tabs = hc.default_tables(c, "collective_stats")
        assert "rent_transactions_p2_before" in tabs and tabs[0] == "collective_transactions"   # 보존 표 자동 포함
        s1 = hc.snapshot(c, ["collective_transactions", "built_scope_stats", "rent_transactions_p2_before"], exclude=[])
    assert hc.evaluate(s1, s1)["status"] == "pass"
    broken = json.loads(json.dumps(s1))
    broken["tables"]["collective_transactions"]["bk=a"] = None                       # 조각 쿼리 실패(시간 초과 등)
    r = hc.evaluate(s1, broken)
    assert r["status"] == "unverified" and r["diff"] == []
    diff = json.loads(json.dumps(s1))
    diff["tables"]["built_scope_stats"]["all"] = [9, "x"]
    assert hc.evaluate(s1, diff)["status"] == "diff"
    req = {**s1, "db": "collective_stats", "tables": {**s1["tables"], "market_stats": None}}
    r = hc.evaluate(req, req)                                                        # 필수 표가 양쪽 모두 없음
    assert r["status"] == "unverified" and ("market_stats", "필수 표 없음(양쪽)") in r["unverified"]
    f1, f2, out = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "r.json"
    C.write_json(f1, s1)
    C.write_json(f2, s1)
    assert hc.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["kind"] == "prod_hash_compare"
    C.write_json(f2, diff)
    assert hc.main(["compare", str(f1), str(f2)]) == 1
    C.write_json(f2, broken)
    assert hc.main(["compare", str(f1), str(f2)]) == 2


# --- 공통 가드(ops_guards) ---------------------------------------------------------------------

def test_ops_guards_assert_local_target():
    import ops_guards as og

    assert og.assert_local_target("postgresql+psycopg2://u:p@localhost:5432/x", environ={}) == ["localhost"]
    assert og.assert_local_target("postgresql+psycopg2://u:p@127.0.0.2/x", environ={}) == ["127.0.0.2"]
    assert og.assert_local_target("postgresql+psycopg2://u:p@[::1]/x", environ={})
    assert og.assert_local_target("postgresql+psycopg2://u:p@/x", environ={}) == ["(기본 유닉스 소켓)"]
    for url, env in (
        ("postgresql+psycopg2://u:p@localhost/x", {"PGHOSTADDR": "13.209.203.178"}),   # 항목 4: localhost + 원격 PGHOSTADDR
        ("postgresql+psycopg2://u:p@localhost/x?hostaddr=10.0.0.5", {}),
        ("postgresql+psycopg2://u:p@localhost/x?host=10.0.0.5", {}),
        ("postgresql+psycopg2://u:p@/x", {"PGHOST": "db.example.com"}),
        ("postgresql+psycopg2://u:p@localhost/x", {"PGSERVICE": "prod"}),
        ("postgresql+psycopg2://u:p@localhost/x", {"PGSERVICEFILE": "/etc/pg_service.conf"}),
        ("postgresql+psycopg2://u:p@localhost/x?service=prod", {}),
        ("postgresql+psycopg2://u:p@localhost,10.0.0.5/x", {}),
        ("postgresql+psycopg2://u:p@localhost.evil.com/x", {}),
    ):
        with pytest.raises(og.TargetError):
            og.assert_local_target(url, environ=env)


def test_scope_dryrun_localhost_with_remote_pghostaddr_refused():
    """항목 4: URL 은 localhost 인데 환경변수 PGHOSTADDR 가 원격 — libpq 는 hostaddr 로 접속하므로 거부."""
    sd = _load(ROOT / "scripts" / "ops" / "collective_p2_local" / "scope_dryrun.py", "sd4")
    with pytest.raises(SystemExit, match="루프백"):
        sd.guard_url("postgresql+psycopg2://u:p@localhost:5432/collective_stats", "collective_stats",
                     environ={"PGHOSTADDR": "13.209.203.178"})
    src = (ROOT / "scripts" / "ops" / "collective_p2_local" / "scope_dryrun.py").read_text(encoding="utf-8")
    assert "ops_guards.assert_local_target" in src


def test_ops_guards_validate_result():
    import datetime as dt

    import _common as C
    import ops_guards as og

    now = dt.datetime.now(dt.timezone.utc)
    good = C.make_result(kind="prod_sync_check", status="pass", left_db="collective_stats", right_db="collective_stats",
                         diff=0, unverified=[], failures=[])
    assert og.validate_result(good, ["collective_stats"]) == ("pass", [])
    cases = {
        "future": {**good, "created_at": (now + dt.timedelta(hours=1)).isoformat()},
        "old": {**good, "created_at": (now - dt.timedelta(hours=49)).isoformat()},
        "naive": {**good, "created_at": now.replace(tzinfo=None).isoformat()},
        "targets": {**good, "targets": ["collective_stats", "rent_stats"]},
        "failures": {**good, "failures": ["x"]},
        "unverified": {**good, "unverified": ["t"]},
        "bad_status": {**good, "status": "ok"},
        "status_unv": {**good, "status": "unverified"},
        "dbs": {**good, "right_db": "rent_stats"},
        "kind": {**good, "kind": "other"},
        "diff_type": {**good, "diff": "0"},
    }
    for name, obj in cases.items():
        st, why = og.validate_result(obj, ["collective_stats"])
        assert st == "unverified" and why, name
    st, _ = og.validate_result({**good, "diff": 2, "status": "diff"}, ["collective_stats"])
    assert st == "diff"
    for f in og.REQUIRED_FIELDS:
        assert og.validate_result({k: v for k, v in good.items() if k != f}, ["collective_stats"])[0] == "unverified", f
    assert og.validate_result(["x"], ["collective_stats"])[0] == "unverified"
    assert og.validate_result(good, ["rent_stats"])[0] == "unverified"


def test_false_success_cases_now_unverified(fx, tmp_path):
    """거짓 성공 재현(Codex 재검토 — 이 저장소에서 재구성한 3건 + 1): 예전에는 종료 코드 0 이었다.
    ① 동기화: 스냅샷의 표 목록 쿼리가 시간 초과 → 표 0개 → 「차이 없음」 통과
    ② 해시: 대상 표가 양쪽 다 0개 → 「다른 조각 0」 통과
    ③ PG 확인: 작은 표(region_codes 등)가 양쪽 모두 없음 → 「hash 같음」 통과(+ 종료 코드 0 고정)
    ④ 동기화: 서로 다른 DB 스냅샷을 비교"""
    import json

    import _common as C

    sc = _load(OPS / "prod_sync_check.py", "sc_fs")
    hc = _load(OPS / "prod_hash_compare.py", "hc_fs")
    url, _ = fx
    with C.ro_conn(url) as c:
        snap = sc.snapshot(c, allow_heavy=True, heavy_rows=-1)
        pg = {"db": snap["db"], "pgcheck": True, "server_version": "18",
              "hash": hc.snapshot(c, ["region_codes", "region_code_history"], exclude=[], mode="hash"),
              "sums": hc.snapshot(c, ["region_codes", "region_code_history"], exclude=[], mode="sums")}
    f1, f2, out = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "r.json"

    # ①
    empty = {"db": snap["db"], "tables": {}, "_timings": [{"query": "표 목록·추정 행 수", "sec": 10, "timeout_ms": 10000,
                                                          "ok": False, "error": "시간 초과"}]}
    C.write_json(f1, empty)
    C.write_json(f2, empty)
    assert sc.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 2
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["status"] == "unverified" and res["failures"] and res["validation"]
    # ②
    hempty = {"db": snap["db"], "mode": "hash", "exclude": [], "tables": {}, "_timings": []}
    C.write_json(f1, hempty)
    C.write_json(f2, hempty)
    assert hc.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 2
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "unverified"
    # ③ (fixture DB 에는 region_codes 가 없다)
    assert pg["hash"]["tables"]["region_codes"] is None
    C.write_json(f1, pg)
    C.write_json(f2, pg)
    assert hc.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 2
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["kind"] == "prod_hash_pgcheck" and res["status"] == "unverified" and res["use_mode"] is None
    # ④
    C.write_json(f1, snap)
    C.write_json(f2, {**snap, "db": "rent_stats"})
    assert sc.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 2
    assert "비교한 두 DB 이름" in "; ".join(json.loads(out.read_text(encoding="utf-8"))["validation"])
    # 정상 스냅샷은 그대로 통과
    C.write_json(f2, snap)
    assert sc.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 0
    from collective import migrate_p2_keys  # noqa: F401  (결과 파일이 실제 적용 모드가 받는 형식인지)
    import ops_guards as og

    assert og.validate_result(json.loads(out.read_text(encoding="utf-8")), [snap["db"]], kind="prod_sync_check")[0] == "pass"


def test_pgcheck_result_states(fx, tmp_path):
    import json

    from sqlalchemy import text

    import _common as C

    hc = _load(OPS / "prod_hash_compare.py", "hc_pg")
    url, eng = fx
    with eng.begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS region_codes (code text, name text)"))
        c.execute(text("CREATE TABLE IF NOT EXISTS region_code_history (code text, n int)"))
        c.execute(text("DELETE FROM region_codes"))
        c.execute(text("INSERT INTO region_codes VALUES ('11', '서울')"))
    with C.ro_conn(url) as c:
        pg = {"db": "x", "pgcheck": True, "server_version": "18",
              "hash": hc.snapshot(c, hc.PG_CHECK_TABLES, exclude=[], mode="hash"),
              "sums": hc.snapshot(c, hc.PG_CHECK_TABLES, exclude=[], mode="sums")}
    pg["db"] = pg["hash"]["db"]
    r = hc.pg_result(pg, pg)
    assert r["status"] == "pass" and r["use_mode"] == "hash"
    other = json.loads(json.dumps(pg))
    other["hash"]["tables"]["region_codes"]["all"] = [1, "다른 해시"]            # PG 버전 차이 흉내
    r = hc.pg_result(pg, other)
    assert r["status"] == "pass" and r["use_mode"] == "sums"
    other["sums"]["tables"]["region_codes"]["all"]["rows"] = "9"
    assert hc.pg_result(pg, other)["status"] == "diff"
    f1, f2, out = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "r.json"
    C.write_json(f1, pg)
    C.write_json(f2, other)
    assert hc.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "diff"


# --- 3차 검토(C-2 리허설 전 필수 4건) -----------------------------------------------------------

def test_guard_query_allowlist_and_dsn_bypass():
    """URL 쿼리는 sslmode·connect_timeout·application_name 만. Codex 재현 `?dsn=host%3D192.0.2.1` 은 거부."""
    import ops_guards as og

    ok = "postgresql+psycopg2://u:p@localhost:5432/x?sslmode=require&connect_timeout=5&application_name=ch2"
    assert og.assert_local_target(ok, environ={}) == ["localhost"]
    for url in (
        "postgresql+psycopg2://u:p@localhost:5432/x?dsn=host%3D192.0.2.1",       # Codex 재현
        "postgresql+psycopg2://u:p@/x?dsn=host%3D192.0.2.1",                      # 호스트 없이 dsn 만
        "postgresql+psycopg2://u:p@localhost/x?options=-c%20foo%3Dbar",
        "postgresql+psycopg2://u:p@localhost/x?target_session_attrs=any",
        "postgresql+psycopg2://u:p@localhost/x?SSLMODE=require",                  # 대소문자 바꾼 키도 허용 밖
        "postgresql+psycopg2://u:p@localhost/x?passfile=/tmp/p",
    ):
        with pytest.raises(og.TargetError, match="허용되지 않은"):
            og.assert_local_target(url, environ={})


def test_guard_reads_hosts_from_final_driver_dsn():
    """허용 목록을 통과한 뒤에도 판정은 psycopg2 최종 DSN(parse_dsn) 기준 — dsn 문자열 안 호스트가 드러나는지."""
    import ops_guards as og

    kw = og.libpq_params("postgresql+psycopg2://u:p@localhost:5432/x")
    assert kw["host"] == "localhost" and kw["dbname"] == "x"
    from psycopg2.extensions import make_dsn, parse_dsn

    hidden = dict(parse_dsn(make_dsn("host=192.0.2.1", dbname="x")))          # 쿼리 검사가 없었다면 이 값이 쓰였다
    hosts = og.final_hosts(hidden, {})
    assert hosts == ["192.0.2.1"] and not og._is_loopback(hosts[0])


def test_hash_compare_iterates_required_tables_built_scope_missing(tmp_path):
    """Codex 재현: 결과 JSON 에서 built_scope_stats 가 빠져 있으면 예전에는 비교할 게 없어 통과. 필수 표 목록을 순회해 검증 못 함(2)."""
    import json

    import _common as C

    hc = _load(OPS / "prod_hash_compare.py", "hc_req")
    t = C.now_iso()
    base = {"db": "built_stats", "measured_at": t, "mode": "hash", "exclude": [], "requested": ["built_transactions", "built_scope_stats"],
            "tables": {"built_transactions": {"id1": [3, "h"]}, "built_scope_stats": {"all": [2, "h2"]}}, "_timings": []}
    assert hc.evaluate(base, base)["status"] == "pass"
    for broken in (
        {**base, "tables": {"built_transactions": {"id1": [3, "h"]}}},                       # 키 자체가 빠짐
        {**base, "tables": {"built_transactions": {"id1": [3, "h"]}}, "requested": ["built_transactions"]},  # 요청 목록도 조작
    ):
        r = hc.evaluate(base, broken)
        assert r["status"] == "unverified" and ("built_scope_stats", "필수 표 없음(오른쪽)") in r["unverified"], r
    f1, f2, out = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "r.json"
    C.write_json(f1, base)
    C.write_json(f2, {**base, "tables": {"built_transactions": {"id1": [3, "h"]}}})
    assert hc.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 2
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "unverified"


def test_result_time_is_oldest_snapshot_measured_at(fx, tmp_path):
    """Codex 재현: 72시간 된 스냅샷을 지금 다시 compare 하면 예전에는 결과 시각이 「지금」이라 48시간 검사를 통과했다.
    결과 시각 = 입력 스냅샷 중 가장 오래된 measured_at → 검증 못 함(2)."""
    import datetime as dt
    import json

    import _common as C
    import ops_guards as og

    sc = _load(OPS / "prod_sync_check.py", "sc_t")
    hc = _load(OPS / "prod_hash_compare.py", "hc_t")
    url, _ = fx
    with C.ro_conn(url) as c:
        snap = sc.snapshot(c, allow_heavy=True, heavy_rows=-1)
        hs = hc.snapshot(c, ["collective_transactions"], exclude=[])
    assert snap["measured_at"] and hs["measured_at"] and hs["requested"] == ["collective_transactions"]
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=72)).isoformat()
    f1, f2, out = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "r.json"
    for mod, good, kind in ((sc, snap, "prod_sync_check"), (hc, hs, "prod_hash_compare")):
        C.write_json(f1, good)
        C.write_json(f2, good)
        assert mod.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 0
        res = json.loads(out.read_text(encoding="utf-8"))
        assert res["created_at"] == good["measured_at"] and res["compared_at"]           # 결과 시각 = 측정 시각
        C.write_json(f2, {**good, "measured_at": old})                                   # 한쪽이 72시간 전
        assert mod.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 2
        res = json.loads(out.read_text(encoding="utf-8"))
        assert res["created_at"] == old and any("오래됨" in w for w in res.get("validation", [])), res
        assert og.validate_result(res, [good["db"]], kind=kind)[0] == "unverified"
        C.write_json(f2, {k: v for k, v in good.items() if k != "measured_at"})          # 측정 시각 없음
        assert mod.main(["compare", str(f1), str(f2), "--result-out", str(out)]) == 2
