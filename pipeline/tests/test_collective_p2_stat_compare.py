# -*- coding: utf-8 -*-
"""집합 2단계 — 밤 「가벼운 비교」(prod_stat_compare) · 병합 표만 다시 해시(prod_hash_compare overlay).
시간 초과·누락·stats_reset 변화·표 빠짐을 통과로 세지 않는지(Codex 4차 재검수 2·3)."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import time
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
    return {"db": name, "measured_at": "2026-11-17T01:00:00+00:00", "measured_at_source": "local",
            "track_counts": "on", "stable": True, "stats_reset": reset, "stats_reset_ok": True, "tables": tables}


def _snap(**over):
    dbs = {
        "collective_stats": _db("collective_stats", {"public.collective_transactions": [10, 2, 1],
                                                     "public.collective_building_geocodes": [5, 1, 0],
                                                     "public.qa_audit_run": [1, 0, 0]}),
        "rent_stats": _db("rent_stats", {"public.rent_transactions": [7, 0, 0], "public.rent_building_geocodes": [3, 0, 0]}),
        "built_stats": _db("built_stats", {"public.built_transactions": [4, 0, 0], "public.qa_audit_run": [0, 0, 0]}),
    }
    s = {"kind": sc.KIND, "measured_at": "2026-11-17T01:00:00+00:00", "measured_at_source": "local",
         "deadline_s": 60, "dbs": dbs, "timed_out": False,
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


def test_track_counts_off_fails():
    night = _snap()
    night["dbs"]["rent_stats"]["track_counts"] = "off"
    status, prob = sc.compare_snaps(_snap(), night)
    assert status == "fail" and any("track_counts" in p[1] for p in prob)


def test_unstable_reread_fails_without_being_treated_as_equal():
    night = _snap()
    night["dbs"]["collective_stats"]["stable"] = False
    status, prob = sc.compare_snaps(_snap(), night)
    assert status == "fail" and any("두 번 읽기" in p[1] for p in prob)


def test_read_stable_sleeps_once_per_db(monkeypatch):
    calls = {"n": 0}

    def fake(conn, t, timeout_ms):
        calls["n"] += 1
        return _db("collective_stats", {"public.t": [1, 0, 0]})

    monkeypatch.setattr(sc, "read_db", fake)
    slept = []
    out = sc.read_stable(None, None, 1000, sleeper=lambda s: slept.append(s))
    assert calls["n"] == 2 and slept == [sc.SETTLE_S] and out["stable"] is True and out["track_counts_ok"] is True


def test_read_stable_mismatch(monkeypatch):
    n = {"n": 0}

    def fake(conn, t, timeout_ms):
        n["n"] += 1
        return _db("collective_stats", {"public.t": [n["n"], 0, 0]})

    monkeypatch.setattr(sc, "read_db", fake)
    out = sc.read_stable(None, None, 1000, sleeper=lambda s: None)
    assert out["stable"] is False


def test_take_deadline_cuts_a_hung_connect():
    """statement_timeout 밖에 있는 접속 정지도 deadline 에 끊긴다."""
    def hung(env, left):
        time.sleep(2)
        return _snap()["dbs"]["collective_stats"]

    t0 = time.monotonic()
    snap = sc.take(["C"], None, deadline_s=0.2, opener=hung, order_clock="defer")
    assert time.monotonic() - t0 < 1.5
    assert snap["timed_out"] is True and "collective_stats" not in snap["dbs"] and snap["measured_at_source"] is None


def _snapshot_exit(tmp_path, monkeypatch, snap) -> int:
    monkeypatch.setattr(sc, "take", lambda *a, **k: snap)
    return sc.main(["snapshot", "--db-env", "X", "--out", str(tmp_path / "d.json")])


def test_cli_snapshot_incomplete_exits_1(tmp_path, monkeypatch):
    s = _snap()
    s["dbs"].pop("rent_stats")
    assert _snapshot_exit(tmp_path, monkeypatch, s) == 1


def test_snapshot_exits_1_when_track_counts_off(tmp_path, monkeypatch):
    s = _snap()
    s["dbs"]["built_stats"]["track_counts"] = "off"
    assert _snapshot_exit(tmp_path, monkeypatch, s) == 1


def test_snapshot_exits_1_when_reread_is_not_stable(tmp_path, monkeypatch):
    s = _snap()
    s["dbs"]["collective_stats"]["stable"] = False
    assert _snapshot_exit(tmp_path, monkeypatch, s) == 1


def test_snapshot_exits_1_when_counter_read_failed(tmp_path, monkeypatch):
    s = _snap()
    s["dbs"]["rent_stats"]["tables"] = None
    assert _snapshot_exit(tmp_path, monkeypatch, s) == 1
    s = _snap()
    s["dbs"]["rent_stats"]["stats_reset_ok"] = False
    assert _snapshot_exit(tmp_path, monkeypatch, s) == 1


def test_snapshot_exits_0_when_counters_are_complete(tmp_path, monkeypatch):
    assert _snapshot_exit(tmp_path, monkeypatch, _snap()) == 0


def test_read_stable_sees_insert_between_reads():
    """같은 트랜잭션에 가두면 두 번째 읽기도 0이다. 행을 하나 넣은 뒤 새 스냅샷이면 stable 이 아니다."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    sys.path.insert(0, str(ROOT / "pipeline" / "collective"))
    try:
        from migrate_p2_keys import server_url_from_env
        base = make_url(server_url_from_env())
    except Exception as ex:  # noqa: BLE001
        pytest.fail(f"미실행: 임시 DB 접속 정보를 읽지 못함 ({type(ex).__name__})")
    fx = "ch2_statread_p2r"
    admin = create_engine(base.set(database="postgres").set(drivername="postgresql+psycopg2"),
                          isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
    try:
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {fx} WITH (FORCE)"))
            c.execute(text(f"CREATE DATABASE {fx}"))
    except Exception as ex:  # noqa: BLE001
        admin.dispose()
        pytest.fail(f"미실행: 임시 DB를 만들지 못함 ({type(ex).__name__})")
    url = base.set(database=fx).render_as_string(hide_password=False)
    writer = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
    try:
        with writer.connect() as w:
            w.execute(text("CREATE TABLE stat_probe (id int)"))
        with sc.ro_conn(url) as conn:
            def insert_one(_s):
                with writer.connect() as w:
                    w.execute(text("INSERT INTO stat_probe VALUES (1)"))
                    # PG18 은 넣는 세션이 통계를 내보내기 전에는 n_tup_ins 가 0이다.
                    # 스냅샷이 고정된 채로는, 이 호출 뒤에도 두 번째 읽기가 0으로 남는다.
                    w.execute(text("SELECT pg_stat_force_next_flush()"))

            out = sc.read_stable(conn, sc.Timed(), 10_000, sleeper=insert_one, settle_s=0)
        assert out["stable"] is False
        row = out["tables"]["public.stat_probe"]
        assert row[0] >= 1
    finally:
        writer.dispose()
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {fx} WITH (FORCE)"))
        admin.dispose()


# --- overlay: 낮 전체 해시 + 밤 병합 표만(가벼운 비교 통과가 전제) -------------------------------------------------------

def _hash(db, tables, at="2026-11-16T10:00:00+00:00"):
    return {"db": db, "measured_at": at, "measured_at_source": "local",
            "server_now": "2020-01-01T00:00:00+00:00", "server_now_source": "server",
            "mode": "hash", "exclude": [], "requested": list(tables),
            "tables": {t: {"all": [1, "h-" + t]} for t in tables}, "_timings": [{"query": f"{t} all", "ok": True} for t in tables]}


MERGED_C = ["collective_building_geocodes", "collective_commercial_map_geocodes", "qa_audit_run"]


MERGED_AT = "2026-11-17T02:05:00+00:00"
FREEZE_AT = "2026-11-17T01:00:00+00:00"


def _stat(status="pass", dbs=("collective_stats", "rent_stats", "built_stats"), at="2026-11-17T02:00:00+00:00",
          baseline="2026-11-16T09:00:00+00:00"):
    return {"kind": "stat_compare_result", "status": status, "compared_at": at, "compared_at_source": "local",
            "baseline_measured_at": baseline, "baseline_measured_at_source": "local", "dbs": list(dbs)}


def _overlay(base, patch, stat=None, merged_at=MERGED_AT, freeze_at=FREEZE_AT):
    return hc.overlay(base, patch, _stat() if stat is None else stat, merged_at=merged_at, freeze_at=freeze_at)


def test_overlay_replaces_only_merged_tables():
    base = _hash("collective_stats", ["collective_transactions", *MERGED_C])
    patch = _hash("collective_stats", MERGED_C, at="2026-11-17T02:10:00+00:00")
    for t in MERGED_C:
        patch["tables"][t] = {"all": [2, "night-" + t]}
    out = _overlay(base, patch)
    assert out["tables"]["collective_transactions"] == {"all": [1, "h-collective_transactions"]}       # 낮 그대로
    assert all(out["tables"][t] == {"all": [2, "night-" + t]} for t in MERGED_C)
    assert out["overlay"]["tables"] == MERGED_C and out["measured_at"] == base["measured_at"]


@pytest.mark.parametrize("make,needle", [
    (lambda b, p: (b, p, _stat(status="fail")), "통과가 아님"),
    (lambda b, p: (b, p, _stat(dbs=("rent_stats",))), "결과에 collective_stats 가 없음"),
    (lambda b, p: (b, p, _stat(at="2026-11-16T09:00:00+00:00")), "먼저거나 같음"),
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
        _overlay(b, p, s)


def test_overlay_cli_refusal_exit_code(tmp_path):
    for n, obj in (("b", _hash("built_stats", ["built_transactions"])), ("p", _hash("built_stats", ["built_transactions"])),
                   ("s", _stat())):
        (tmp_path / f"{n}.json").write_text(json.dumps(obj), encoding="utf-8")
    rc = hc.main(["overlay", "--base", str(tmp_path / "b.json"), "--patch", str(tmp_path / "p.json"),
                  "--stat-result", str(tmp_path / "s.json"), "--merged-at", MERGED_AT, "--freeze-at", FREEZE_AT,
                  "--out", str(tmp_path / "o.json")])
    assert rc == 2 and not (tmp_path / "o.json").exists()                 # built 는 병합 표가 없어 거절


def test_merged_tables_are_in_day_hash_targets_and_stat_excludes():
    """밤 병합 표는 ① 낮 전체 해시 기본 대상에 있어야 overlay 가 되고 ② 가벼운 비교에서 빠져야 한다."""
    for db, tables in hc.MERGED_TABLES.items():
        assert set(tables) <= set(hc.TARGETS[db])
        assert {f"public.{t}" for t in tables} <= set(sc.EXCLUDE[db])
    assert sc.EXCLUDE["built_stats"] == frozenset({"public.qa_audit_run"})          # built QA 는 1a 로 따로 본다
    assert sc.role("collective_stats_p2r") == "collective_stats" and sc.role("rent_stats") == "rent_stats"


def test_overlay_accepts_counter_baseline_in_the_same_second_and_ignores_server_now():
    base = _hash("collective_stats", ["collective_transactions", *MERGED_C])
    base["server_now"] = "2099-01-01T00:00:00+00:00"          # 서버 시계가 어긋나도 순서 판정에 안 쓴다
    patch = _hash("collective_stats", MERGED_C, at="2026-11-17T02:10:00+00:00")
    out = _overlay(base, patch, _stat(baseline=base["measured_at"]))
    assert out["measured_at"] == base["measured_at"]
    assert out["overlay"]["freeze_at_source"] == "local" and "server_now" not in out["overlay"]


def test_overlay_rejects_counter_baseline_recorded_after_the_hash():
    base = _hash("collective_stats", ["collective_transactions", *MERGED_C])
    patch = _hash("collective_stats", MERGED_C, at="2026-11-17T02:10:00+00:00")
    late = _stat(baseline="2026-11-16T11:00:00+00:00")       # 낮 해시 10:00 보다 늦음
    with pytest.raises(hc.OverlayError, match="늦게 기록됨"):
        _overlay(base, patch, late)


def test_overlay_rejects_previous_day_merged_hash():
    base = _hash("collective_stats", ["collective_transactions", *MERGED_C])
    patch = _hash("collective_stats", MERGED_C, at="2026-11-16T02:10:00+00:00")
    with pytest.raises(hc.OverlayError, match="병합보다 먼저"):
        _overlay(base, patch)


def test_overlay_rejects_merged_hash_not_after_maintenance_on():
    base = _hash("collective_stats", ["collective_transactions", *MERGED_C])
    patch = _hash("collective_stats", MERGED_C, at="2026-11-17T02:10:00+00:00")
    with pytest.raises(hc.OverlayError, match="점검 창"):
        _overlay(base, patch, freeze_at="2026-11-17T02:10:00+00:00")


def test_overlay_rejects_server_clock_used_as_order_time():
    base = _hash("collective_stats", ["collective_transactions", *MERGED_C])
    base["measured_at_source"] = "server"
    patch = _hash("collective_stats", MERGED_C, at="2026-11-17T02:10:00+00:00")
    with pytest.raises(hc.OverlayError, match="local 이 아님"):
        _overlay(base, patch)


def _stamp_file(tmp_path, server_now, source="server"):
    path = tmp_path / "a.json"
    path.write_text(json.dumps({"measured_at": None, "server_now": server_now, "server_now_source": source}),
                    encoding="utf-8")
    return path


@pytest.mark.parametrize("mod", [hc, sc])
def test_stamp_local_rejects_yesterdays_server_now(tmp_path, mod):
    import datetime as dt

    path = _stamp_file(tmp_path, (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat())
    before = path.read_text(encoding="utf-8")
    assert mod.main(["stamp-local", "--file", str(path), "--field", "measured_at"]) == 2
    assert path.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("mod", [hc, sc])
def test_stamp_local_accepts_a_few_seconds_and_keeps_server_now(tmp_path, mod):
    import datetime as dt

    fresh = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=3)).isoformat()
    path = _stamp_file(tmp_path, fresh)
    assert mod.main(["stamp-local", "--file", str(path), "--field", "measured_at"]) == 0
    obj = json.loads(path.read_text(encoding="utf-8"))
    assert obj["measured_at_source"] == "local" and obj["server_now"] == fresh
    stamped = dt.datetime.fromisoformat(obj["measured_at"])
    assert abs((dt.datetime.now(dt.timezone.utc) - stamped).total_seconds()) < 30


def test_stamp_local_rejects_missing_or_non_server_source(tmp_path):
    import datetime as dt

    fresh = dt.datetime.now(dt.timezone.utc).isoformat()
    path = _stamp_file(tmp_path, fresh, "local")
    before = path.read_text(encoding="utf-8")
    assert hc.main(["stamp-local", "--file", str(path), "--field", "measured_at"]) == 2
    assert path.read_text(encoding="utf-8") == before
    for key in ("server_now", "server_now_source"):
        path = _stamp_file(tmp_path, fresh)
        obj = json.loads(path.read_text(encoding="utf-8"))
        obj.pop(key)
        path.write_text(json.dumps(obj), encoding="utf-8")
        before = path.read_text(encoding="utf-8")
        assert hc.main(["stamp-local", "--file", str(path), "--field", "measured_at"]) == 2
        assert path.read_text(encoding="utf-8") == before
