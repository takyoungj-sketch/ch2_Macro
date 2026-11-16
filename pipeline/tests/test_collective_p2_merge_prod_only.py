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
    ins, upd, cnt = mpo.plan_geocodes(rows, "k", rules, local_keys={"y"})
    assert upd == []
    assert cnt == {"src": 7, "unchanged": 3, "rekeyed": 2, "drop_c01": 1, "drop_c2": 1, "drop_not_in_ledger": 0, "rekey_overlap": 1,
                   "exists_local": 1, "identical": 0, "same_value_other_time": 0, "conflict": 0,
                   "conflict_coords": 0, **{f"rule_{r}": 0 for r in mpo.CONFLICT_RULES},
                   "update": 0, "kept_local": 0, "insert": 3}
    assert sorted(r["k"] for r in ins) == ["n1", "x", "z"]
    assert next(r for r in ins if r["k"] == "z")["updated_at"] == 2          # 겹치면 늦은 쪽


def test_plan_geocodes_counts_same_key_conflicts_and_keeps_local():
    """같은 키에 값이 다르면 충돌로 센다(status 없음 = 둘 다 실패 → 로컬 유지). 시각 열만 다르면 충돌 아님."""
    src = [{"k": "a", "longitude": 1.0, "latitude": 2.0, "label": "x", "updated_at": 5},
           {"k": "b", "longitude": 1.0, "latitude": 2.0, "label": "x", "updated_at": 5},
           {"k": "c", "longitude": 1.0, "latitude": 2.0, "label": "y", "updated_at": 5},
           {"k": "d", "longitude": 1.0, "latitude": 2.0, "label": "x", "updated_at": 5},
           {"k": "e", "longitude": 1.0, "latitude": 2.0, "label": "x", "updated_at": 5}]
    local = {"a": {"k": "a", "longitude": 1.0, "latitude": 2.0, "label": "x", "updated_at": 5},     # 같음
             "b": {"k": "b", "longitude": 1.0, "latitude": 2.0, "label": "x", "updated_at": 9},     # 시각만 다름
             "c": {"k": "c", "longitude": 1.0, "latitude": 2.0, "label": "x", "updated_at": 5},     # 이름 다름
             "d": {"k": "d", "longitude": 1.5, "latitude": 2.0, "label": "x", "updated_at": 5}}     # 좌표 다름
    ins, upd, cnt = mpo.plan_geocodes(src, "k", {}, local)
    assert [r["k"] for r in ins] == ["e"] and upd == []
    assert (cnt["exists_local"], cnt["identical"], cnt["same_value_other_time"], cnt["conflict"],
            cnt["conflict_coords"], cnt["rule_both_failed"], cnt["kept_local"]) == (4, 1, 1, 2, 1, 2, 2)


# --- 충돌 규칙(T 결정 2026-11-16): 한쪽만 ok → ok 쪽 · 둘 다 ok → geocoded_at 최근(같으면 로컬) · 둘 다 실패 → 로컬 ---------

def _g(status, at, lon=127.0):
    return {"k": "a", "status": status, "geocoded_at": at, "longitude": None if status != "ok" else lon, "latitude": 37.0}


@pytest.mark.parametrize("prod,local,win,rule", [
    (_g("ok", 5), _g("not_found", None), "prod", "only_prod_ok"),                    # 한쪽만 ok — 운영
    (_g("not_found", None), _g("ok", 5), "local", "only_local_ok"),                  # 한쪽만 ok — 로컬(이번 리허설 1건)
    (_g("ok", 9, 127.1), _g("ok", 5), "prod", "both_ok_prod_newer"),                 # 둘 다 ok — 운영이 최근
    (_g("ok", 5, 127.1), _g("ok", 9), "local", "both_ok_local_newer_or_same"),       # 둘 다 ok — 로컬이 최근
    (_g("ok", 5, 127.1), _g("ok", 5), "local", "both_ok_local_newer_or_same"),       # 둘 다 ok — 같으면 로컬
    (_g("ok", None, 127.1), _g("ok", 5), "local", "both_ok_local_newer_or_same"),    # 운영 시각 없음 — 로컬
    (_g("not_found", None), _g("error", None), "local", "both_failed"),             # 둘 다 실패 — 로컬
    (_g("pending", None), _g("not_found", None), "local", "both_failed"),
])
def test_resolve_conflict_rules(prod, local, win, rule):
    assert mpo.resolve_conflict(prod, local) == (win, rule)


def test_plan_geocodes_applies_rule_and_counts_per_rule():
    src = [{**_g("ok", 5), "k": "p1"}, {**_g("not_found", None), "k": "l1"}, {**_g("ok", 9, 127.2), "k": "p2"},
           {**_g("error", None), "k": "f1"}]
    local = {"p1": {**_g("not_found", None), "k": "p1"}, "l1": {**_g("ok", 3), "k": "l1"},
             "p2": {**_g("ok", 4), "k": "p2"}, "f1": {**_g("not_found", None), "k": "f1", "label": "x"}}
    src[3]["label"] = "y"
    ins, upd, cnt = mpo.plan_geocodes(src, "k", {}, local)
    assert ins == [] and sorted(r["k"] for r in upd) == ["p1", "p2"]
    assert (cnt["conflict"], cnt["rule_only_prod_ok"], cnt["rule_only_local_ok"], cnt["rule_both_ok_prod_newer"],
            cnt["rule_both_failed"], cnt["update"], cnt["kept_local"]) == (4, 1, 1, 1, 1, 2, 2)


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
        # 대상 원장(키 이전 뒤 키) — 원장에 없는 키의 행은 병합이 버린다
        t.execute(text("CREATE TABLE collective_transactions (building_key text)"))
        t.execute(text("CREATE TABLE collective_commercial_transactions (cluster_key text)"))
        t.execute(text("INSERT INTO collective_transactions VALUES (:i), (:e), (:f), (:j)"), dict(i=i, e=e, f=f, j=j))
        t.execute(text("INSERT INTO collective_commercial_transactions VALUES (:j), (:h)"), dict(j=j, h=h))
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
        t.execute(text("CREATE TABLE rent_transactions (building_key text)"))
        t.execute(text("INSERT INTO rent_transactions VALUES (:i), (:e)"), dict(i=i, e=e))


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


# --- 동결 뒤 새 덤프 사전 확인(런북 6.1) · manifest 엄격 검사(Codex 재검수 2) ------------------------

GOOD_ROWS = {"collective_stats": {"collective_building_geocodes": 3, "collective_commercial_map_geocodes": 2, "qa_audit_run": 1},
             "rent_stats": {"rent_building_geocodes": 4}}
GOOD_COUNTS = {"collective": GOOD_ROWS["collective_stats"], "rent": GOOD_ROWS["rent_stats"]}


def _manifest(tmp_path, created="20261117_031000", ro=True, tamper=False, edit=None):
    """두 DB 덤프(가짜 바이트)와 manifest. edit(archives) 로 구조를 바꿔 거절 경우를 만든다."""
    import hashlib

    arcs = []
    for db, rows in GOOD_ROWS.items():
        dump = tmp_path / f"prod_only_{db}_x.dump"
        dump.write_bytes(b"PGDMP-fixture-" + db.encode())
        sha = hashlib.sha256(dump.read_bytes()).hexdigest()
        arcs.append({"db": db, "file": "C:\other\machine\\" + dump.name, "bytes": dump.stat().st_size,
                     "sha256": ("0" * 64) if tamper and db == "collective_stats" else sha, "archive_rows": dict(rows)})
    if edit:
        arcs = edit(arcs)
    m = {"production_read_only": ro, "created_kst": created, "archives": arcs}
    f = tmp_path / "manifest.json"
    f.write_text(json.dumps(m), encoding="utf-8")
    return f


def test_preflight_accepts_fresh_matching_dump(tmp_path):
    f = _manifest(tmp_path)
    out = mpo.preflight(f, "2026-11-17T03:00", GOOD_COUNTS)
    assert [a["db"] for a in out["archives"]] == ["collective_stats", "rent_stats"]
    assert all(a["sha256_ok"] for a in out["archives"]) and out["created_kst"] == "2026-11-17 03:10:00"
    mpo.preflight(f, "20261117_031000")                                     # 동결 시각과 같으면 통과


@pytest.mark.parametrize("kw,freeze,counts,needle", [
    ({}, "2026-11-17T03:20", None, "동결 시각보다 오래됨"),
    ({"tamper": True}, "2026-11-17T03:00", None, "SHA-256"),
    ({"ro": False}, "2026-11-17T03:00", None, "읽기 전용"),
    ({}, "2026-11-17T03:00", {**GOOD_COUNTS, "collective": {**GOOD_ROWS["collective_stats"], "qa_audit_run": 2}},
     "행 수가 manifest 와 다름"),
    ({}, "2026-11-17T03:00", {"collective": GOOD_COUNTS["collective"]}, "원본 임시 DB 가 실행 인자에 없음"),
    ({}, "어제", None, "시각 형식"),
])
def test_preflight_refuses(tmp_path, kw, freeze, counts, needle):
    with pytest.raises(mpo.MergeError, match=needle):
        mpo.preflight(_manifest(tmp_path, **kw), freeze, counts)


def _drop_table(db, t):
    def f(arcs):
        for a in arcs:
            if a["db"] == db:
                a["archive_rows"].pop(t)
        return arcs
    return f


def _set(db, key, val):
    def f(arcs):
        for a in arcs:
            if a["db"] == db:
                a[key] = val
        return arcs
    return f


def _set_rows(db, t, val):
    def f(arcs):
        for a in arcs:
            if a["db"] == db:
                a["archive_rows"][t] = val
        return arcs
    return f


@pytest.mark.parametrize("edit,needle", [
    (lambda arcs: [a for a in arcs if a["db"] != "rent_stats"], "필요한 DB 가 없음"),                    # DB 누락
    (lambda arcs: arcs + [dict(arcs[0])], "같은 DB 가 두 번"),                                             # DB 중복
    (lambda arcs: arcs + [{**arcs[1], "db": "built_stats"}], "알 수 없는 DB"),                             # 모르는 DB
    (lambda arcs: [], "덤프 항목"),                                                                        # 빈 목록
    (_drop_table("collective_stats", "qa_audit_run"), "필요한 표가 없음"),                                # 표 누락
    (_set_rows("rent_stats", "rent_transactions", 5), "알 수 없는 표"),                                   # 모르는 표
    (_set_rows("collective_stats", "collective_building_geocodes", None), "행 수가 없거나"),             # 행 수 누락
    (_set_rows("collective_stats", "collective_building_geocodes", "3"), "행 수가 없거나"),              # 행 수 문자열
    (_set_rows("rent_stats", "rent_building_geocodes", -1), "행 수가 없거나"),
    (_set("rent_stats", "archive_rows", None), "archive_rows"),                                           # 행 수 묶음 없음
    (_set("collective_stats", "sha256", ""), "sha256"),
    (_set("collective_stats", "bytes", None), "bytes"),
    (_set("collective_stats", "file", ""), "file"),
])
def test_manifest_shape_refused_before_files(tmp_path, edit, needle):
    with pytest.raises(mpo.MergeError, match=needle):
        mpo.preflight(_manifest(tmp_path, edit=edit), "2026-11-17T03:00", GOOD_COUNTS)


def test_manifest_refusal_exits_2_before_any_db(tmp_path, monkeypatch):
    """CLI: manifest 가 틀리면 종료 코드 2 — 대상 DB 에 쓰지 않는다(드라이런 경로에서도 병합 전에 멈춤)."""
    f = _manifest(tmp_path, edit=lambda arcs: [a for a in arcs if a["db"] != "rent_stats"])
    monkeypatch.setattr(mpo, "source_counts", lambda eng, side: GOOD_COUNTS[side])
    monkeypatch.setattr(mpo, "engine_for", lambda *a, **k: type("E", (), {"dispose": lambda self: None})())
    touched = []
    monkeypatch.setattr(mpo, "merge_side", lambda *a, **k: touched.append(1) or [])
    rc = mpo.cli(["--src-collective", SRC, "--dst-collective", DST, "--src-rent", SRC_R, "--dst-rent", DST_R,
                  "--manifest", str(f), "--freeze-at", "2026-11-17T03:00", "--report-out", str(tmp_path / "r.json")])
    assert rc == 2 and touched == []


def test_preflight_refuses_missing_dump_file(tmp_path):
    f = _manifest(tmp_path)
    next(tmp_path.glob("prod_only_rent_stats_*.dump")).unlink()
    with pytest.raises(mpo.MergeError, match="덤프 파일 없음"):
        mpo.preflight(f, "2026-11-17T03:00")


def test_real_apply_requires_manifest_freeze_time_and_rent_side():
    base = ["--src-collective", SRC, "--dst-collective", "collective_stats", "--base-url", "postgresql://u@127.0.0.1/x"]
    with pytest.raises(mig.GuardError, match="manifest"):
        mpo.main(base + ["--real-apply", "--confirm-db", "collective_stats"])
    with pytest.raises(mig.GuardError, match="네 표"):
        mpo.main(base + ["--real-apply", "--confirm-db", "collective_stats", "--manifest", "m.json", "--freeze-at", "2026-11-17T03:00"])
    with pytest.raises(mig.GuardError, match="같이"):
        mpo.main(base + ["--manifest", "m.json"])
    assert mpo.cli(base + ["--manifest", "m.json"]) == 2


def test_merge_updates_row_when_prod_wins_and_is_idempotent(dbs):
    """DB: 운영 쪽이 이기면(로컬 실패 · 운영 ok) 그 행 값으로 UPDATE, 다시 돌리면 identical. 로컬 ok 는 그대로."""
    _seed_fresh = """DROP TABLE IF EXISTS {t}; CREATE TABLE {t} (building_key text PRIMARY KEY, label text,
        longitude double precision, latitude double precision, status text, geocoded_at timestamp, updated_at timestamp)"""
    kp, kl = K["a"], K["b"]
    for e in (dbs[SRC], dbs[DST]):
        with e.begin() as c:
            for stmt in _seed_fresh.format(t="geo_rule_t").split(";"):
                c.execute(text(stmt))
    with dbs[DST].begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS geo_rule_map (old_key text, new_key text, reason text)"))
        c.execute(text("""INSERT INTO geo_rule_t VALUES (:p, 'x', NULL, NULL, 'not_found', NULL, '2026-10-01'),
                          (:l, 'x', 127.0, 37.0, 'ok', '2026-11-05', '2026-11-05')"""), dict(p=kp, l=kl))
    with dbs[SRC].begin() as c:
        c.execute(text("""INSERT INTO geo_rule_t VALUES (:p, 'x', 127.5, 37.5, 'ok', '2026-11-10', '2026-11-10'),
                          (:l, 'x', NULL, NULL, 'not_found', NULL, '2026-10-24')"""), dict(p=kp, l=kl))
    with dbs[SRC].connect() as s, dbs[DST].begin() as d:
        out = mpo.merge_geocode(s, d, "geo_rule_t", "building_key", "geo_rule_map", False, apply=True)
    assert (out["conflict"], out["rule_only_prod_ok"], out["rule_only_local_ok"], out["update"], out["kept_local"],
            out["insert"], out["dst_after"]) == (2, 1, 1, 1, 1, 0, 2)
    with dbs[DST].connect() as c:
        rows = {r[0]: (r[1], r[2]) for r in c.execute(text("SELECT building_key, longitude, status FROM geo_rule_t"))}
    assert rows[kp] == (127.5, "ok") and rows[kl] == (127.0, "ok")
    with dbs[SRC].connect() as s, dbs[DST].begin() as d:
        again = mpo.merge_geocode(s, d, "geo_rule_t", "building_key", "geo_rule_map", False, apply=True)
    assert (again["update"], again["identical"], again["rule_only_local_ok"]) == (0, 1, 1)


# --- 되돌리기 방향(런북 6.2 마지막 줄): 반영 뒤 운영(새 키) 행 → 되돌린 옛 DB --------------------------------------
OLD_C, OLD_R, NEW_C, NEW_R = "ch2mpo_oldc_p2r", "ch2mpo_oldr_p2r", "ch2mpo_newc_p2r", "ch2mpo_newr_p2r"


@pytest.fixture
def rev_dbs():
    base = mig.server_url_from_env()
    try:
        admin = create_engine(make_url(base).set(database="postgres", drivername="postgresql+psycopg2"),
                              isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with admin.connect() as c:
            for d in (OLD_C, OLD_R, NEW_C, NEW_R):
                c.execute(text(f"DROP DATABASE IF EXISTS {d}"))
                c.execute(text(f"CREATE DATABASE {d}"))
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"로컬 PostgreSQL 임시 DB 생성 불가: {type(ex).__name__}")
    engs = {d: mig.engine_for(d, read_only=False, base_url=base) for d in (OLD_C, OLD_R, NEW_C, NEW_R)}
    yield {"base": base, **engs}
    for e in engs.values():
        e.dispose()
    with admin.connect() as c:
        for d in (OLD_C, OLD_R, NEW_C, NEW_R):
            c.execute(text(f"DROP DATABASE IF EXISTS {d} WITH (FORCE)"))
    admin.dispose()


GEO2 = """CREATE TABLE {t} ({k} text PRIMARY KEY, label text, longitude double precision, latitude double precision,
          status text, geocoded_at timestamp, updated_at timestamp)"""


def _c29():
    import os

    lab = ROOT / "scripts" / "lab" / "collective_p2"
    if str(lab) not in sys.path:
        sys.path.insert(0, str(lab))
    cwd = os.getcwd()
    try:
        spec = importlib.util.spec_from_file_location("c29r", lab / "c29_merge_prod_only_check.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        os.chdir(cwd)


def test_reverse_direction_new_to_old_drops_keys_not_in_old_ledger(rev_dbs, tmp_path):
    """새 DB(반영 뒤 운영) → 옛 DB(되돌린 반영 전 덤프): 옛 DB 에 연결표가 없어 재키 없이, 옛 원장에 없는 새 키(조각·호남 새 키)
    행은 버리고 drop_not_in_ledger 로 센다. 같은 키는 충돌 규칙. forward 는 연결표가 없어 거절. 다시 돌리면 변경 0."""
    nk, k2, k3, c1, r1, r2 = K["a"], K["b"], K["c"], K["d"], K["e"], K["f"]
    with rev_dbs[NEW_C].begin() as c:        # 반영 뒤 운영에서 쌓인 행(새 키 포함)
        c.execute(text(GEO2.format(t="collective_building_geocodes", k="building_key")))
        c.execute(text(GEO2.format(t="collective_commercial_map_geocodes", k="cluster_key")))
        c.execute(text(QA_DDL))
        c.execute(text("""INSERT INTO collective_building_geocodes VALUES
            (:nk, 'new fragment', 127.1, 37.1, 'ok', '2026-11-21', '2026-11-21'),
            (:k2, 'shared', 127.2, 37.2, 'ok', '2026-11-21', '2026-11-21'),
            (:k3, 'same', 127.3, 37.3, 'ok', '2026-11-01', '2026-11-01')"""), dict(nk=nk, k2=k2, k3=k3))
        c.execute(text("INSERT INTO collective_commercial_map_geocodes VALUES (:c1, 'road', 127.0, 37.0, 'ok', NULL, NULL)"),
                  dict(c1=c1))
        c.execute(text("INSERT INTO qa_audit_run (id, domain, verdict) VALUES (1, 'collective', 'ok')"))
    with rev_dbs[OLD_C].begin() as c:        # 되돌린 옛 DB — 연결표·판정 표 없음, 원장은 옛 키
        c.execute(text(GEO2.format(t="collective_building_geocodes", k="building_key")))
        c.execute(text(GEO2.format(t="collective_commercial_map_geocodes", k="cluster_key")))
        c.execute(text(QA_DDL))
        c.execute(text("""INSERT INTO collective_building_geocodes VALUES
            (:k2, 'shared', NULL, NULL, 'not_found', NULL, '2026-11-10'),
            (:k3, 'same', 127.3, 37.3, 'ok', '2026-11-01', '2026-11-01')"""), dict(k2=k2, k3=k3))
        c.execute(text("INSERT INTO qa_audit_run (id, domain, verdict) VALUES (1, 'collective', 'ok')"))
        c.execute(text("SELECT setval('qa_audit_run_id_seq', 1)"))
        c.execute(text("CREATE TABLE collective_transactions (building_key text)"))
        c.execute(text("CREATE TABLE collective_commercial_transactions (cluster_key text)"))
        c.execute(text("INSERT INTO collective_transactions VALUES (:k2), (:k3)"), dict(k2=k2, k3=k3))
        c.execute(text("INSERT INTO collective_commercial_transactions VALUES (:c1)"), dict(c1=c1))
    with rev_dbs[NEW_R].begin() as c:
        c.execute(text(GEO2.format(t="rent_building_geocodes", k="building_key")))
        c.execute(text("""INSERT INTO rent_building_geocodes VALUES (:r1, 'new', 1, 1, 'ok', NULL, NULL),
                          (:r2, 'shared', 2, 2, 'ok', NULL, NULL)"""), dict(r1=r1, r2=r2))
    with rev_dbs[OLD_R].begin() as c:
        c.execute(text(GEO2.format(t="rent_building_geocodes", k="building_key")))
        c.execute(text("CREATE TABLE rent_transactions (building_key text)"))
        c.execute(text("INSERT INTO rent_transactions VALUES (:r2)"), dict(r2=r2))
    rep = tmp_path / "rev.json"
    args = ["--src-collective", NEW_C, "--dst-collective", OLD_C, "--src-rent", NEW_R, "--dst-rent", OLD_R,
            "--base-url", rev_dbs["base"], "--remap-out", str(tmp_path / "remap.csv"), "--report-out", str(rep)]
    assert mpo.cli(args + ["--apply"]) == 2                                   # forward: 옛 DB 에 연결표가 없어 거절(쓰기 0)
    with rev_dbs[OLD_C].connect() as c:
        assert c.execute(text("SELECT count(*) FROM collective_building_geocodes")).scalar() == 2
    assert mpo.cli(args + ["--apply", "--direction", "reverse"]) == 0
    r = json.loads(rep.read_text(encoding="utf-8"))
    assert r["applied"] is True and r["direction"] == "reverse"
    t = {x["table"]: x for s_ in r["sides"].values() for x in s_["tables"]}
    bg = t["collective_building_geocodes"]
    assert (bg["src"], bg["drop_not_in_ledger"], bg["identical"], bg["rule_only_prod_ok"], bg["update"], bg["insert"],
            bg["keymap_rows"], bg["dst_after"]) == (3, 1, 1, 1, 1, 0, 0, 2)
    cg = t["collective_commercial_map_geocodes"]
    assert (cg["drop_not_in_ledger"], cg["insert"], cg["dst_after"]) == (0, 1, 1)
    rg = t["rent_building_geocodes"]
    assert (rg["drop_not_in_ledger"], rg["insert"], rg["dst_after"]) == (1, 1, 1)
    assert t["qa_audit_run"]["skip_identical"] == 1
    with rev_dbs[OLD_C].connect() as c:
        keys = {x[0]: (x[1], x[2]) for x in c.execute(text("SELECT building_key, status, longitude FROM collective_building_geocodes"))}
    assert nk not in keys and keys[k2] == ("ok", 127.2)                       # 새 키 행 없음 · 공유 키는 「운영만 ok」로 운영 값
    c29 = _c29()
    assert c29.validate_report(r, {"collective": OLD_C, "rent": OLD_R}, {"collective": NEW_C, "rent": NEW_R}) == []
    assert mpo.cli(args + ["--apply", "--direction", "reverse"]) == 0       # 다시 돌리면 변경 0(멱등)
    r2 = json.loads(rep.read_text(encoding="utf-8"))
    t2 = {x["table"]: x for s_ in r2["sides"].values() for x in s_["tables"]}
    assert all(t2[k]["insert"] == 0 and t2[k]["update"] == 0 for k in t2 if k != "qa_audit_run")
    assert t2["qa_audit_run"]["insert_new_id"] == 0 and t2["qa_audit_run"]["insert_same_id"] == 0


def test_forward_drops_rows_whose_key_is_not_in_target_ledger():
    """forward 도 같은 규칙: 재키 뒤 대상 원장에 없는 키는 버리고 센다(넣지 않음)."""
    rows = [{"k": "o1"}, {"k": "x"}, {"k": "gone"}]
    ins, upd, cnt = mpo.plan_geocodes(rows, "k", {"o1": (mpo.REKEY, "n1")}, {}, ledger={"n1", "x"})
    assert sorted(r["k"] for r in ins) == ["n1", "x"] and cnt["drop_not_in_ledger"] == 1 and cnt["insert"] == 2
