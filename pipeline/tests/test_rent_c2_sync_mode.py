# -*- coding: utf-8 -*-
"""RENT-001 반영본 동기 검사. 기존 prod_sync_check 통과 조건은 바꾸지 않는다."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "pipeline", ROOT / "pipeline" / "collective", ROOT / "scripts" / "ops" / "collective_p2_verify"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import rent_c2_sync as c2  # noqa: E402
from collective import migrate_p2_keys as mig  # noqa: E402

LEDGER = {"count": 10, "id_max": 20, "id_sum": 30}


def _table(rows, as_of="2026-10-01", months=None):
    rec = {"rows": rows, "est_rows": rows, "heavy": False}
    if as_of is not None:
        rec["max_as_of_month"] = as_of
    if months is not None:
        rec["recent_months"] = months
    return rec


def _common():
    months = {"2026-10": 10}
    return {
        "rent_transactions": _table(10, as_of=None, months=months),
        "rent_building_stats": _table(100),
        "rent_building_rolling_stats": _table(200),
        "rent_sale_building_map": _table(50),
        "rent_building_key_map": _table(2976),
        "rent_building_geocodes": _table(1038, as_of=None),
    }


def _snap(db, tables):
    return {"db": db, "measured_at": "2026-11-20T13:00:00+00:00", "tables": tables}


def _case():
    backup = _snap(c2.BACKUP_DB, _common())
    ops_tables = _common()
    ops_tables["rent_building_geocodes"] = _table(1072, as_of=None)
    ops = _snap("rent_stats", ops_tables)
    local_tables = _common()
    local_tables["rent_building_geocodes"] = _table(1037, as_of=None)
    local_tables["rent_building_key_map"] = _table(5325)
    local_tables["rent_building_stats"] = _table(110)
    local_tables["rent_building_rolling_stats"] = _table(220)
    local_tables["rent_sale_building_map"] = _table(60)
    for name in c2.NEW_TABLES:
        local_tables[name] = _table(1, as_of=None)
    local = _snap("rent_stats", local_tables)
    return backup, ops, local


def _judge(backup, ops, local, ledger_local=None, units=6054, present=True):
    return c2.judge(
        backup=backup, ops=ops, local=local,
        ledger_local=dict(ledger_local or LEDGER), ledger_backup=dict(LEDGER),
        units_rows=units, hash_present=present,
    )


def test_matching_c2_shape_passes():
    report = _judge(*_case())
    assert report["status"] == "pass" and report["failures"] == []
    assert report["sync_mode"] == "c2-applied"
    assert report["backup_vs_ops"]["geocode_backup"] == 1038
    assert report["backup_vs_ops"]["geocode_ops"] == 1072
    c2.accept_report(report, ["rent_stats"], ["rent_stats"])


def test_diff_outside_allow_list_fails():
    backup, ops, local = _case()
    local["tables"]["rent_sangkwon"] = _table(9)
    report = _judge(backup, ops, local)
    assert report["status"] == "diff"
    assert any("rent_sangkwon" in x for x in report["failures"])


def test_ops_diff_other_than_geocode_fails():
    backup, ops, local = _case()
    ops["tables"]["rent_transactions"] = _table(11, as_of=None, months={"2026-10": 11})
    report = _judge(backup, ops, local)
    assert report["status"] == "diff"
    assert any("좌표 행 수 밖" in x for x in report["failures"])


def test_ledger_id_sum_mismatch_fails():
    backup, ops, local = _case()
    report = _judge(backup, ops, local, ledger_local={**LEDGER, "id_sum": 31})
    assert report["status"] == "diff"
    assert any("id_sum" in x for x in report["failures"])


def test_fewer_ops_geocodes_fail():
    backup, ops, local = _case()
    ops["tables"]["rent_building_geocodes"] = _table(1000, as_of=None)
    report = _judge(backup, ops, local)
    assert report["status"] == "diff"
    assert any("적음" in x for x in report["failures"])


def test_as_of_mismatch_on_allowed_table_fails():
    backup, ops, local = _case()
    local["tables"]["rent_building_stats"]["max_as_of_month"] = "2026-09-01"
    report = _judge(backup, ops, local)
    assert report["status"] == "diff"
    assert any("max_as_of_month" in x for x in report["failures"])


def test_hand_written_pass_without_numbers_is_rejected():
    with pytest.raises(ValueError):
        c2.accept_report(
            {"kind": "rent_c2_sync", "sync_mode": "c2-applied", "status": "pass", "failures": []},
            ["rent_stats"], ["rent_stats"],
        )


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Engine:
    def connect(self):
        return _Conn()

    def begin(self):
        return _Conn()

    def dispose(self):
        return None


def test_key_migration_cli_rejects_c2_before_connect(monkeypatch):
    def connected(*args, **kwargs):
        raise AssertionError("connected")

    monkeypatch.setattr(mig, "engine_for", connected)
    monkeypatch.setattr(mig, "server_url_from_env", connected)
    with pytest.raises(mig.GuardError, match="임대 좌표 병합 전용"):
        mig.main(["--collective-db", "collective_stats", "--rent-db", "rent_stats",
                  "--real-apply", "--sync-mode", "c2-applied",
                  "--confirm-db", "rent_stats", "--c2-approved-sha256", "a" * 64, "--c2-approved-rows", "6054"])


def test_rent_only_c2_uses_rent_engines_only(monkeypatch, tmp_path):
    ops = ROOT / "scripts" / "ops"
    if str(ops) not in sys.path:
        sys.path.insert(0, str(ops))
    import collective_p2_merge_prod_only as merge

    opened = []
    checked = []

    def engine(name, **kwargs):
        opened.append(name)
        return _Engine()

    def checked_write(names, args, base_url=None):
        checked.append(list(names))
        mig.enable_c2_applied(names, args.confirm_db, _judge(*_case()))

    monkeypatch.setattr(merge, "engine_for", engine)
    monkeypatch.setattr(merge, "check_write_targets", checked_write)
    monkeypatch.setattr(merge, "source_counts", lambda *args, **kwargs: {"rent_building_geocodes": 1})
    monkeypatch.setattr(merge, "preflight", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(merge, "assert_rehearsal_db", lambda conn, name: name)
    monkeypatch.setattr(merge, "merge_geocode", lambda *args, **kwargs: {"insert": 0})
    code = merge.main([
        "--rent-only", "--src-rent", "rent_src_p2r", "--dst-rent", "rent_stats",
        "--real-apply", "--sync-mode", "c2-applied", "--confirm-db", "rent_stats",
        "--manifest", "m.json", "--freeze-at", "2026-11-20T00:00",
        "--c2-result-out", str(tmp_path / "out.json"),
        "--base-url", "postgresql://u:p@127.0.0.1:5432/postgres",
    ])
    assert code == 0
    assert checked == [["rent_stats"]]
    assert opened
    assert set(opened) <= {"rent_src_p2r", "rent_stats"}


def test_collective_args_with_c2_are_rejected(monkeypatch):
    ops = ROOT / "scripts" / "ops"
    if str(ops) not in sys.path:
        sys.path.insert(0, str(ops))
    import collective_p2_merge_prod_only as merge

    def connected(*args, **kwargs):
        raise AssertionError("connected")

    monkeypatch.setattr(merge, "engine_for", connected)
    with pytest.raises(merge.GuardError, match="집합 인자"):
        merge.main(["--rent-only", "--src-rent", "rent_src_p2r", "--dst-rent", "rent_stats",
                    "--src-collective", "collective_stats", "--sync-mode", "c2-applied",
                    "--real-apply", "--confirm-db", "rent_stats"])
    with pytest.raises(merge.GuardError, match="임대 좌표 병합 전용"):
        merge.main(["--src-collective", "src", "--dst-collective", "collective_stats",
                    "--src-rent", "rent_src_p2r", "--dst-rent", "rent_stats",
                    "--sync-mode", "c2-applied", "--real-apply", "--confirm-db", "rent_stats"])


def test_existing_mode_still_reaches_the_database_layer(monkeypatch):
    seen = []

    def engine(name, **kwargs):
        seen.append(name)
        raise mig.GuardError("stop-after-engine")

    monkeypatch.setattr(mig, "engine_for", engine)
    with pytest.raises(mig.GuardError, match="stop-after-engine"):
        mig.main(["--collective-db", "collective_stats_p2r"])
    assert seen == ["collective_stats_p2r"]


def test_direct_read_rejects_a_remote_host_before_its_own_engine(monkeypatch):
    from sqlalchemy import create_engine as real_create
    from ops_guards import TargetError

    opened = []

    def wrapped(*args, **kwargs):
        if kwargs.get("connect_args"):
            opened.append(kwargs["connect_args"])
            raise AssertionError("opened")
        return real_create(*args, **kwargs)

    monkeypatch.setattr("sqlalchemy.create_engine", wrapped)
    with pytest.raises(TargetError, match="로컬"):
        c2.open_local_read("postgresql://u:p@13.209.203.178:5432/postgres", "rent_stats")
    assert opened == []


def test_direct_read_sets_a_ten_minute_timeout(monkeypatch):
    from sqlalchemy import create_engine as real_create

    opened = []

    def wrapped(*args, **kwargs):
        if kwargs.get("connect_args"):
            opened.append(kwargs["connect_args"]["options"])
            raise RuntimeError("stop-before-connect")
        return real_create(*args, **kwargs)

    monkeypatch.setattr("sqlalchemy.create_engine", wrapped)
    with pytest.raises(RuntimeError, match="stop-before-connect"):
        c2.open_local_read("postgresql://u:p@127.0.0.1:5432/postgres", "rent_stats")
    assert opened == [f"-c statement_timeout={c2.STATEMENT_TIMEOUT_MS} -c default_transaction_read_only=on"]


def test_measure_sets_statement_timeout():
    class Result:
        def one(self):
            return (4, 5, 6)

    class Conn:
        def __init__(self):
            self.sql = []

        def execute(self, statement, params=None):
            self.sql.append(str(statement))
            return Result()

    conn = Conn()
    got = c2.measure(conn, units=False)
    assert f"statement_timeout = {c2.STATEMENT_TIMEOUT_MS}" in conn.sql[0]
    assert got == {"count": 4, "id_max": 5, "id_sum": 6}


def test_c2_real_apply_requires_a_result_path_before_connect(monkeypatch):
    import argparse

    def connected(*args, **kwargs):
        raise AssertionError("connected")

    monkeypatch.setattr(mig, "engine_for", connected)
    monkeypatch.setattr(mig, "server_url_from_env", connected)
    args = argparse.Namespace(
        real_apply=True, sync_mode="c2-applied", c2_result_out="", confirm_db=["rent_stats"], sync_result=[],
        c2_backup_snapshot="", c2_ops_snapshot="", c2_local_snapshot="",
    )
    with pytest.raises(mig.GuardError, match="c2-result-out"):
        mig.check_write_targets(["rent_stats"], args, base_url="postgresql://u:p@127.0.0.1:5432/postgres")
    ops = ROOT / "scripts" / "ops"
    if str(ops) not in sys.path:
        sys.path.insert(0, str(ops))
    import collective_p2_merge_prod_only as merge

    monkeypatch.setattr(merge, "engine_for", connected)
    with pytest.raises(merge.GuardError, match="c2-result-out"):
        merge.main(["--rent-only", "--src-rent", "rent_src_p2r", "--dst-rent", "rent_stats",
                    "--real-apply", "--sync-mode", "c2-applied", "--confirm-db", "rent_stats",
                    "--manifest", "m.json", "--freeze-at", "2026-11-20T00:00"])


def test_existing_mode_still_rejects_a_diff_result(tmp_path):
    ops = ROOT / "scripts" / "ops" / "collective_p2_verify"
    if str(ops) not in sys.path:
        sys.path.insert(0, str(ops))
    import _common as common

    path = tmp_path / "res.json"
    common.write_result(path, kind="prod_sync_check", status="diff", left_db="rent_stats", right_db="rent_stats",
                        detail={"diff": 1})
    with pytest.raises(mig.GuardError):
        mig.enable_real_apply(["rent_stats"], ["rent_stats"], [path])
