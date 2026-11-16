# -*- coding: utf-8 -*-
"""집합 2단계 — 운영 전용 표 합치기(scripts/ops/collective_p2_merge_prod_only.py) fixture 시험.

좌표 캐시: 1:1 재키 · C-01 분할 옛 키 버림 · C-2 옛 키(연결표 c2·판정 표 split base) 버림 · 로컬에 있는 키 유지 · 재키 겹침.
QA 기록: 시퀀스 먼저 올림 · 없는 id 그대로 · 같은 id 같은 내용 건너뜀 · 같은 id 다른 내용 새 id + 대응 CSV.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "pipeline", ROOT / "pipeline" / "collective"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from collective import building_keys as bk  # noqa: E402
from collective import migrate_p2_keys as mig  # noqa: E402

_spec = importlib.util.spec_from_file_location("mpo", ROOT / "scripts" / "ops" / "collective_p2_merge_prod_only.py")
mpo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mpo)

SRC, DST = "ch2mpo_src_p2r", "ch2mpo_dst_p2r"
SRC_R, DST_R = "ch2mpo_srcr_p2r", "ch2mpo_dstr_p2r"
K = {n: (n * 64)[:64] for n in "abcdefghij"}

GEO = """CREATE TABLE {t} ({k} text PRIMARY KEY, label text, longitude double precision, latitude double precision,
          status text DEFAULT 'pending', updated_at timestamp DEFAULT now())"""
QA_DDL = """CREATE TABLE qa_audit_run (id bigserial PRIMARY KEY, created_at timestamptz DEFAULT '2026-11-01 00:00+09', domain varchar,
             verdict varchar, l1_json jsonb, operator_note text)"""
MAP = """CREATE TABLE {t} (old_key varchar(64), new_key varchar(64), asset_type varchar(32), reason varchar(32),
          split_part int DEFAULT 0, n_tx int, PRIMARY KEY (old_key, new_key))"""


def test_key_rules_classify_map_reasons():
    rules = mpo.key_rules([("o1", "n1", "honam_sido"), ("o2", "n2a", "split"), ("o2", "n2b", "split"),
                           ("o3", "n3", "c2_split"), ("o4", "n4", "honam_sido+c2_split"), ("o5", "n5", "split+c2_split"),
                           ("o6", "n6", "honam_sido+split")], c2_bases={"b7"})
    assert rules["o1"] == (mpo.REKEY, "n1")
    assert rules["o2"][0] == rules["o6"][0] == mpo.DROP_C01
    assert rules["o3"][0] == rules["o4"][0] == rules["o5"][0] == rules["b7"][0] == mpo.DROP_C2


def test_plan_geocodes_counts():
    rules = {"o1": (mpo.REKEY, "n1"), "o2": (mpo.DROP_C01, None), "o3": (mpo.DROP_C2, None), "o9": (mpo.REKEY, "z")}
    rows = [{"k": "o1"}, {"k": "o2"}, {"k": "o3"}, {"k": "x"}, {"k": "y"}, {"k": "o9", "updated_at": 2}, {"k": "z", "updated_at": 1}]
    ins, cnt = mpo.plan_geocodes(rows, "k", rules, local_keys={"y"})
    assert cnt == {"src": 7, "unchanged": 3, "rekeyed": 2, "drop_c01": 1, "drop_c2": 1, "rekey_overlap": 1,
                   "exists_local": 1, "insert": 3}
    assert sorted(r["k"] for r in ins) == ["n1", "x", "z"]
    assert next(r for r in ins if r["k"] == "z")["updated_at"] == 2          # 겹치면 늦은 쪽


@pytest.fixture(scope="module")
def dbs():
    try:
        base = mig.server_url_from_env()
        admin = create_engine(make_url(base).set(database="postgres", drivername="postgresql+psycopg2"),
                              isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with admin.connect() as c:
            for d in (SRC, DST, SRC_R, DST_R):
                c.execute(text(f"DROP DATABASE IF EXISTS {d}"))
                c.execute(text(f"CREATE DATABASE {d}"))
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"로컬 PostgreSQL 임시 DB 생성 불가: {type(ex).__name__}")
    engs = {d: mig.engine_for(d, read_only=False, base_url=base) for d in (SRC, DST, SRC_R, DST_R)}
    yield {"base": base, **engs}
    for e in engs.values():
        e.dispose()
    with admin.connect() as c:
        for d in (SRC, DST, SRC_R, DST_R):
            c.execute(text(f"DROP DATABASE IF EXISTS {d} WITH (FORCE)"))
    admin.dispose()


def _seed(dbs):
    a, b, c, d, e, f, g, h, i, j = (K[x] for x in "abcdefghij")
    with dbs[SRC].begin() as s:      # 운영 덤프를 복원한 임시 DB(키 이전 전 키)
        s.execute(text(GEO.format(t="collective_building_geocodes", k="building_key")))
        s.execute(text(GEO.format(t="collective_commercial_map_geocodes", k="cluster_key")))
        s.execute(text(QA_DDL))
        s.execute(text("INSERT INTO collective_building_geocodes (building_key, label, longitude, latitude) VALUES "
                       "(:a,'1:1',127,37),(:b,'C-01',127,37),(:c,'C-2 map',127,37),(:d,'C-2 base',127,37),"
                       "(:e,'그대로',127,37),(:f,'로컬에 있음',1,1)"), dict(a=a, b=b, c=c, d=d, e=e, f=f))
        s.execute(text("INSERT INTO collective_commercial_map_geocodes (cluster_key, label) VALUES (:g,'1:1'),(:h,'그대로')"),
                  dict(g=g, h=h))
        s.execute(text("""INSERT INTO qa_audit_run (id, domain, verdict, l1_json) VALUES
            (1, 'collective', 'ok', '{"x": 1}'), (2, 'collective', 'ok', '{"x": 2}'), (5, 'rent', 'warn', '{"y": [1]}')"""))
        s.execute(text("SELECT setval('qa_audit_run_id_seq', 5)"))
    with dbs[DST].begin() as t:      # 키 이전이 끝난 로컬 반영본
        t.execute(text(GEO.format(t="collective_building_geocodes", k="building_key")))
        t.execute(text(GEO.format(t="collective_commercial_map_geocodes", k="cluster_key")))
        t.execute(text(MAP.format(t="collective_building_key_map")))
        t.execute(text(MAP.format(t="collective_cluster_key_map")))
        t.execute(text(QA_DDL))
        mig._exec_script(t, bk.C2_DDL)
        t.execute(text("INSERT INTO collective_building_key_map (old_key, new_key, asset_type, reason) VALUES "
                       "(:a,:i,'apartment','honam_sido'),(:b,:j,'rowhouse','split'),(:b,:e,'rowhouse','split'),"
                       "(:c,:j,'rowhouse','c2_split')"), dict(a=a, b=b, c=c, e=e, i=i, j=j))
        t.execute(text("INSERT INTO collective_cluster_key_map (old_key, new_key, asset_type, reason) VALUES "
                       "(:g,:j,'commercial','honam_sido')"), dict(g=g, j=j))
        t.execute(text(f"""INSERT INTO {bk.C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, part, decision, source)
            VALUES (:d,'rowhouse','1150010300','1',0,'split','c2_final'),(:d,'rowhouse','1150010300','2',1,'split','c2_final')"""),
                  dict(d=d))
        t.execute(text("INSERT INTO collective_building_geocodes (building_key, label, longitude) VALUES (:f,'로컬 값',9)"),
                  dict(f=f))
        t.execute(text("""INSERT INTO qa_audit_run (id, domain, verdict, l1_json) VALUES
            (1, 'collective', 'ok', '{"x": 1}'), (2, 'collective', 'fail', '{"x": 2}'), (3, 'land', 'ok', NULL)"""))
        t.execute(text("SELECT setval('qa_audit_run_id_seq', 3)"))
    with dbs[SRC_R].begin() as s:
        s.execute(text(GEO.format(t="rent_building_geocodes", k="building_key")))
        s.execute(text("INSERT INTO rent_building_geocodes (building_key, label) VALUES (:a,'1:1'),(:b,'C-01'),(:e,'그대로')"),
                  dict(a=a, b=b, e=e))
    with dbs[DST_R].begin() as t:
        t.execute(text(GEO.format(t="rent_building_geocodes", k="building_key")))
        t.execute(text(MAP.format(t="rent_building_key_map")))
        t.execute(text("INSERT INTO rent_building_key_map (old_key, new_key, asset_type, reason) VALUES "
                       "(:a,:i,'apartment','honam_sido'),(:b,:j,'rowhouse','split'),(:b,:e,'rowhouse','split')"),
                  dict(a=a, b=b, e=e, i=i, j=j))


def test_merge_dryrun_then_apply_counts_and_remap(dbs, tmp_path):
    _seed(dbs)
    remap, rep = tmp_path / "remap.csv", tmp_path / "rep.json"
    args = ["--src-collective", SRC, "--dst-collective", DST, "--src-rent", SRC_R, "--dst-rent", DST_R,
            "--base-url", dbs["base"], "--remap-out", str(remap), "--report-out", str(rep)]
    assert mpo.main(args) == 0                                                  # 드라이런 — 쓰지 않음
    with dbs[DST].connect() as c:
        assert c.execute(text("SELECT count(*) FROM collective_building_geocodes")).scalar() == 1
    assert mpo.main(args + ["--apply"]) == 0
    r = json.loads(rep.read_text(encoding="utf-8"))
    col = {t["table"]: t for t in r["sides"]["collective"]["tables"]}
    bg = col["collective_building_geocodes"]
    assert {k: bg[k] for k in ("src", "unchanged", "rekeyed", "drop_c01", "drop_c2", "exists_local", "insert")} == \
        {"src": 6, "unchanged": 2, "rekeyed": 1, "drop_c01": 1, "drop_c2": 2, "exists_local": 1, "insert": 2}
    assert bg["dst_after"] == 3
    cg = col["collective_commercial_map_geocodes"]
    assert (cg["rekeyed"], cg["unchanged"], cg["insert"], cg["dst_after"]) == (1, 1, 2, 2)
    qa = col["qa_audit_run"]
    assert {k: qa[k] for k in ("src", "dst_before", "insert_same_id", "skip_identical", "insert_new_id", "dst_after")} == \
        {"src": 3, "dst_before": 3, "insert_same_id": 1, "skip_identical": 1, "insert_new_id": 1, "dst_after": 5}
    rg = r["sides"]["rent"]["tables"][0]
    assert (rg["rekeyed"], rg["drop_c01"], rg["unchanged"], rg["insert"], rg["dst_after"]) == (1, 1, 1, 2, 2)
    with dbs[DST].connect() as c:
        keys = {x[0]: x[1] for x in c.execute(text("SELECT building_key, longitude FROM collective_building_geocodes"))}
        assert set(keys) == {K["i"], K["e"], K["f"]} and keys[K["f"]] == 9               # 로컬 값 유지
        rows = {x[0]: (x[1], x[2]) for x in c.execute(text("SELECT id, domain, verdict FROM qa_audit_run"))}
        assert rows[5] == ("rent", "warn")                                               # 없는 id 그대로
        assert rows[2] == ("collective", "fail")                                         # 로컬 기록 유지
        new_id = max(rows)
        assert new_id == 6 and rows[new_id] == ("collective", "ok")                      # 다른 내용 → 새 id(양쪽 max+1)
        assert c.execute(text("SELECT nextval('qa_audit_run_id_seq')")).scalar() == 7
    assert list(csv.reader(remap.open(encoding="utf-8"))) == [["prod_id", "new_id"], ["2", "6"]]
    assert mpo.main(args + ["--apply"]) == 0                                      # 두 번째: 넣을 것 없음(멱등)
    r2 = json.loads(rep.read_text(encoding="utf-8"))
    col2 = {t["table"]: t for t in r2["sides"]["collective"]["tables"]}
    assert col2["collective_building_geocodes"]["insert"] == 0
    q2 = col2["qa_audit_run"]
    assert (q2["insert_same_id"], q2["skip_identical"], q2["skip_already_merged"], q2["insert_new_id"], q2["dst_after"]) == \
        (0, 2, 1, 0, 5)


def test_merge_refuses_non_rehearsal_target_and_same_db(tmp_path):
    with pytest.raises(mig.GuardError):
        mpo.main(["--src-collective", "prod_only_tmp", "--dst-collective", "collective_stats", "--apply",
                  "--base-url", "postgresql://u@127.0.0.1/x"])
    with pytest.raises(mig.GuardError, match="같은 DB"):
        mpo.main(["--src-collective", DST, "--dst-collective", DST, "--base-url", "postgresql://u@127.0.0.1/x"])
    with pytest.raises(mig.GuardError, match="같이"):
        mpo.main(["--src-collective", SRC, "--dst-collective", DST, "--src-rent", SRC_R,
                  "--base-url", "postgresql://u@127.0.0.1/x"])
