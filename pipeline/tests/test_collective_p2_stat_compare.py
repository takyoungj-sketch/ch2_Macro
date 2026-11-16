# -*- coding: utf-8 -*-
"""집합 2단계 — 밤 「가벼운 비교」(prod_stat_compare) · 병합 표만 다시 해시(prod_hash_compare overlay).
시간 초과·누락·stats_reset 변화·표 빠짐을 통과로 세지 않는지(Codex 4차 재검수 2·3)."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "scripts" / "ops" / "collective_p2_verify"
if str(OPS) not in sys.path:
    sys.path.insert(0, str(OPS))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, OPS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


sc = _load("prod_stat_compare")
hc = _load("prod_hash_compare")


def _db(name, tables, reset="2026-08-01 00:00:00+00"):
    return {"db": name, "measured_at": "2026-11-17T01:00:00+00:00", "stats_reset": reset, "stats_reset_ok": True,
            "tables": tables}


def _snap(**over):
    dbs = {
        "collective_stats": _db("collective_stats", {"public.collective_transactions": [10, 2, 1],
                                                     "public.collective_building_geocodes": [5, 1, 0],
                                                     "public.qa_audit_run": [1, 0, 0]}),
        "rent_stats": _db("rent_stats", {"public.rent_transactions": [7, 0, 0], "public.rent_building_geocodes": [3, 0, 0]}),
        "built_stats": _db("built_stats", {"public.built_transactions": [4, 0, 0], "public.qa_audit_run": [0, 0, 0]}),
    }
    s = {"kind": sc.KIND, "measured_at": "2026-11-17T01:00:00+00:00", "deadline_s": 60, "dbs": dbs, "timed_out": False,
         "errors": [], "elapsed_s": 1.2}
    s.update(over)
    return s


def test_identical_passes_and_excluded_tables_may_change():
    night = _snap()
    night["dbs"]["collective_stats"]["tables"]["public.collective_building_geocodes"] = [9, 9, 9]   # 운영 전용 표
    night["dbs"]["built_stats"]["tables"]["public.qa_audit_run"] = [1, 0, 0]                        # built QA(따로 1a 확인)
    night["dbs"]["rent_stats"]["tables"]["public.rent_building_geocodes"] = [4, 0, 0]
    assert sc.compare_snaps(_snap(), night) == ("pass", [])


def _mut(f):
    n = _snap()
    f(n)
    return n


@pytest.mark.parametrize("night,needle", [
    (_mut(lambda n: n["dbs"]["collective_stats"]["tables"].__setitem__("public.collective_transactions", [11, 2, 1])), "쓰기 카운터 다름"),
    (_mut(lambda n: n["dbs"]["rent_stats"]["tables"].__setitem__("public.rent_transactions", [7, 1, 0])), "쓰기 카운터 다름"),
    (_mut(lambda n: n["dbs"]["built_stats"]["tables"].__setitem__("public.built_transactions", [4, 0, 1])), "쓰기 카운터 다름"),
    (_mut(lambda n: n["dbs"]["collective_stats"].__setitem__("stats_reset", "2026-11-17 00:30:00+00")), "stats_reset 바뀜"),
    (_mut(lambda n: n["dbs"]["collective_stats"].update(stats_reset=None, stats_reset_ok=False)), "stats_reset 을 읽지 못함"),
    (_mut(lambda n: n["dbs"]["rent_stats"]["tables"].pop("public.rent_transactions")), "표가 빠짐"),
    (_mut(lambda n: n["dbs"]["built_stats"]["tables"].__setitem__("public.new_t", [0, 0, 0])), "새 표"),
    (_mut(lambda n: n["dbs"].pop("built_stats")), "DB 기록 없음"),
    (_mut(lambda n: n["dbs"]["collective_stats"].__setitem__("tables", None)), "표 카운터를 읽지 못함"),
    (_mut(lambda n: n.update(timed_out=True)), "시간 안에 끝나지 않음"),                  # 시간 초과는 통과 아님
    (_mut(lambda n: n["errors"].append("RENT_DATABASE_URL: OperationalError")), "읽기 실패"),
    ({"dbs": {}}, "스냅샷이 아님"),
    (None, "스냅샷이 아님"),
])
def test_any_problem_fails(night, needle):
    status, prob = sc.compare_snaps(_snap(), night)
    assert status == "fail" and any(needle in p[1] for p in prob), prob


def test_timed_out_baseline_also_fails():
    status, prob = sc.compare_snaps(_snap(timed_out=True), _snap())
    assert status == "fail" and any("낮 기록이 시간 안에" in p[1] for p in prob)


def test_take_marks_timeout_and_skips_remaining_dbs():
    """전체 시간 제한을 넘기면 남은 DB 는 읽지 않고 timed_out — 비교는 실패."""
    t = {"now": 0.0}

    def clock():
        return t["now"]

    def reader(env, left):
        t["now"] += 40.0                       # DB 하나에 40초
        name = {"C": "collective_stats", "R": "rent_stats", "B": "built_stats"}[env]
        return _snap()["dbs"][name]

    snap = sc.take(["C", "R", "B"], None, deadline_s=60, clock=clock, reader=reader)
    assert snap["timed_out"] is True and "built_stats" not in snap["dbs"]
    assert sc.compare_snaps(_snap(), snap)[0] == "fail"


def test_take_records_reader_errors_as_failure():
    def reader(env, left):
        raise TimeoutError("statement timeout")

    snap = sc.take(["C"], None, deadline_s=60, reader=reader)
    assert snap["errors"] and sc.compare_snaps(_snap(), snap)[0] == "fail"


def test_cli_compare_unreadable_baseline_exits_1(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "take", lambda *a, **k: _snap())
    out = tmp_path / "res.json"
    assert sc.main(["compare", "--baseline", str(tmp_path / "none.json"), "--db-env", "X", "--result-out", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "fail"
    base = tmp_path / "day.json"
    base.write_text(json.dumps(_snap()), encoding="utf-8")
    assert sc.main(["compare", "--baseline", str(base), "--db-env", "X", "--result-out", str(out)]) == 0
    monkeypatch.setattr(sc, "take", lambda *a, **k: _snap(timed_out=True))
    assert sc.main(["compare", "--baseline", str(base), "--db-env", "X"]) == 1


def test_cli_snapshot_incomplete_exits_1(tmp_path, monkeypatch):
    s = _snap()
    s["dbs"].pop("rent_stats")
    monkeypatch.setattr(sc, "take", lambda *a, **k: s)
    assert sc.main(["snapshot", "--db-env", "X", "--out", str(tmp_path / "d.json")]) == 1


# --- overlay: 낮 전체 해시 + 밤 병합 표만(가벼운 비교 통과가 전제) -------------------------------------------------------

def _hash(db, tables, at="2026-11-16T10:00:00+00:00"):
    return {"db": db, "measured_at": at, "mode": "hash", "exclude": [], "requested": list(tables),
            "tables": {t: {"all": [1, "h-" + t]} for t in tables}, "_timings": [{"query": f"{t} all", "ok": True} for t in tables]}


MERGED_C = ["collective_building_geocodes", "collective_commercial_map_geocodes", "qa_audit_run"]


def _stat(status="pass", dbs=("collective_stats", "rent_stats", "built_stats"), at="2026-11-17T02:00:00+00:00"):
    return {"kind": "stat_compare_result", "status": status, "compared_at": at, "dbs": list(dbs)}


def test_overlay_replaces_only_merged_tables():
    base = _hash("collective_stats", ["collective_transactions", *MERGED_C])
    patch = _hash("collective_stats", MERGED_C, at="2026-11-17T02:10:00+00:00")
    for t in MERGED_C:
        patch["tables"][t] = {"all": [2, "night-" + t]}
    out = hc.overlay(base, patch, _stat())
    assert out["tables"]["collective_transactions"] == {"all": [1, "h-collective_transactions"]}       # 낮 그대로
    assert all(out["tables"][t] == {"all": [2, "night-" + t]} for t in MERGED_C)
    assert out["overlay"]["tables"] == MERGED_C and out["measured_at"] == base["measured_at"]


@pytest.mark.parametrize("make,needle", [
    (lambda b, p: (b, p, _stat(status="fail")), "통과가 아님"),
    (lambda b, p: (b, p, _stat(dbs=("rent_stats",))), "결과에 collective_stats 가 없음"),
    (lambda b, p: (b, p, _stat(at="2026-11-16T09:00:00+00:00")), "먼저 했거나"),
    (lambda b, p: (b, p, {"status": "pass"}), "결과 파일이 아님"),
    (lambda b, p: (b, {**p, "db": "rent_stats"}, _stat()), "DB 다름"),
    (lambda b, p: (b, {**p, "mode": "sums"}, _stat()), "mode 다름"),
    (lambda b, p: (b, {**p, "tables": {t: p["tables"][t] for t in MERGED_C[:2]}}, _stat()), "병합 표"),
    (lambda b, p: (b, {**p, "_timings": [{"query": "qa_audit_run all", "ok": False}]}, _stat()), "조각 쿼리 실패"),
    (lambda b, p: (b, {**p, "tables": {**p["tables"], "qa_audit_run": None}}, _stat()), "비었거나 없음"),
    (lambda b, p: ({**b, "requested": ["collective_transactions"]}, p, _stat()), "낮 해시 대상에 없는"),
])
def test_overlay_refused(make, needle):
    base = _hash("collective_stats", ["collective_transactions", *MERGED_C])
    patch = _hash("collective_stats", MERGED_C, at="2026-11-17T02:10:00+00:00")
    b, p, s = make(copy.deepcopy(base), copy.deepcopy(patch))
    with pytest.raises(hc.OverlayError, match=needle):
        hc.overlay(b, p, s)


def test_overlay_cli_refusal_exit_code(tmp_path):
    for n, obj in (("b", _hash("built_stats", ["built_transactions"])), ("p", _hash("built_stats", ["built_transactions"])),
                   ("s", _stat())):
        (tmp_path / f"{n}.json").write_text(json.dumps(obj), encoding="utf-8")
    rc = hc.main(["overlay", "--base", str(tmp_path / "b.json"), "--patch", str(tmp_path / "p.json"),
                  "--stat-result", str(tmp_path / "s.json"), "--out", str(tmp_path / "o.json")])
    assert rc == 2 and not (tmp_path / "o.json").exists()                 # built 는 병합 표가 없어 거절


def test_merged_tables_are_in_day_hash_targets_and_stat_excludes():
    """밤 병합 표는 ① 낮 전체 해시 기본 대상에 있어야 overlay 가 되고 ② 가벼운 비교에서 빠져야 한다."""
    for db, tables in hc.MERGED_TABLES.items():
        assert set(tables) <= set(hc.TARGETS[db])
        assert {f"public.{t}" for t in tables} <= set(sc.EXCLUDE[db])
    assert sc.EXCLUDE["built_stats"] == frozenset({"public.qa_audit_run"})          # built QA 는 1a 로 따로 본다
    assert sc.role("collective_stats_p2r") == "collective_stats" and sc.role("rent_stats") == "rent_stats"
