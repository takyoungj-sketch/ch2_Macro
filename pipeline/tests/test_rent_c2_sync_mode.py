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
