# -*- coding: utf-8 -*-
"""집합 2단계 — 병합 검사 c29 엄격 판정(Codex 재검수 3)·멱등 판정(재검수 4). DB 없이 보고서·스냅샷만."""
from __future__ import annotations

import copy
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "scripts" / "lab" / "collective_p2"


@pytest.fixture(scope="module")
def c29():
    if str(LAB) not in sys.path:
        sys.path.insert(0, str(LAB))         # c29 는 같은 폴더의 _db 를 import(_db 는 cwd 를 backend 로 바꾼다)
    cwd = os.getcwd()
    try:
        spec = importlib.util.spec_from_file_location("c29", LAB / "c29_merge_prod_only_check.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        os.chdir(cwd)


DST = {"collective": "collective_stats_p2r", "rent": "rent_stats_p2r"}
SRC = {"collective": "prodonly_collective_p2r_src", "rent": "prodonly_rent_p2r_src"}


def _geo(c29, table, **over):
    return {"table": table, **{k: 0 for k in c29.GEO_COUNTERS}, **over}


def _good(c29):
    qa = {"table": "qa_audit_run", **{k: 0 for k in c29.QA_COUNTERS}}
    return {"apply": True, "real_apply": False, "applied": True, "sides": {
        "collective": {"src": SRC["collective"], "dst": DST["collective"], "tables": [
            _geo(c29, "collective_building_geocodes"), _geo(c29, "collective_commercial_map_geocodes"), qa]},
        "rent": {"src": SRC["rent"], "dst": DST["rent"], "tables": [_geo(c29, "rent_building_geocodes")]}}}


def test_good_report_passes(c29):
    assert c29.validate_report(_good(c29), DST, SRC) == []


def _mut(c29, f):
    r = copy.deepcopy(_good(c29))
    f(r)
    return r


@pytest.mark.parametrize("make,needle", [
    (lambda c29: None, "보고서 없음"),
    (lambda c29: {"sides": {}}, "applied"),                                         # Codex 재현: 빈 sides
    (lambda c29: {"applied": True, "sides": {}}, "sides 가 없거나 비었음"),
    (lambda c29: {"applied": True}, "sides 가 없거나 비었음"),
    (lambda c29: [], "보고서 없음"),
    (lambda c29: _mut(c29, lambda r: r.update(applied=False)), "적용 결과가 아님"),     # 드라이런 보고서
    (lambda c29: _mut(c29, lambda r: r.pop("applied")), "적용 결과가 아님"),
    (lambda c29: _mut(c29, lambda r: r["sides"].pop("rent")), "rent 쪽이 없음"),
    (lambda c29: _mut(c29, lambda r: r["sides"]["collective"]["tables"].pop(1)), "collective_commercial_map_geocodes: 보고서에 표 없음"),
    (lambda c29: _mut(c29, lambda r: r["sides"]["collective"]["tables"].pop(2)), "qa_audit_run: 보고서에 표 없음"),
    (lambda c29: _mut(c29, lambda r: r["sides"]["collective"]["tables"][0].pop("update")), "필수 카운터 없음"),
    (lambda c29: _mut(c29, lambda r: r["sides"]["rent"]["tables"][0].update(insert_not_in_ledger=None)), "필수 카운터 없음"),
    (lambda c29: _mut(c29, lambda r: r["sides"]["collective"]["tables"][2].pop("insert_new_id")), "필수 카운터 없음"),
    (lambda c29: _mut(c29, lambda r: r["sides"]["collective"]["tables"][0].update(insert="3")), "필수 카운터 없음"),
    (lambda c29: _mut(c29, lambda r: r["sides"]["collective"].update(dst="collective_stats")), "대상 DB"),
    (lambda c29: _mut(c29, lambda r: r["sides"]["rent"].update(src="other_src")), "원본 DB"),
    (lambda c29: _mut(c29, lambda r: r["sides"]["collective"]["tables"].__setitem__(
        0, {"table": "collective_building_geocodes", "status": "원본에 표 없음"})), "병합되지 않음"),
    (lambda c29: _mut(c29, lambda r: r["sides"]["rent"]["tables"].append(_geo(c29, "x_geocodes"))), "모르는 표"),
    (lambda c29: _mut(c29, lambda r: r["sides"].update(built={})), "모르는 쪽"),
])
def test_report_refused(c29, make, needle):
    fails = c29.validate_report(make(c29), DST, SRC)
    assert fails and any(needle in f for f in fails), fails


def _snap(seq="is_called=True"):
    s = {f"{DST['collective']}.collective_building_geocodes": [3, "h1"],
         f"{DST['collective']}.collective_commercial_map_geocodes": [2, "h2"],
         f"{DST['collective']}.qa_audit_run": [1, "h3"],
         f"{DST['collective']}.qa_audit_run_id_seq": [2, seq],
         f"{DST['rent']}.rent_building_geocodes": [4, "h4"]}
    return s


def test_idempotent_passes_when_nothing_changes(c29):
    assert c29.idempotent_fails(_good(c29), _snap(), _snap(), DST, SRC) == []


@pytest.mark.parametrize("edit,snap_b,needle", [
    (lambda r: r["sides"]["collective"]["tables"][0].update(insert=1), None, "insert=1"),
    (lambda r: r["sides"]["rent"]["tables"][0].update(update=2), None, "update=2"),
    (lambda r: r["sides"]["collective"]["tables"][2].update(insert_new_id=1), None, "insert_new_id=1"),
    (lambda r: r["sides"]["collective"]["tables"][2].update(insert_same_id=1), None, "insert_same_id=1"),
    (lambda r: None, {**_snap(), f"{DST['rent']}.rent_building_geocodes": [4, "hX"]}, "스냅샷 다름"),
    (lambda r: None, _snap(seq="is_called=False"), "qa_audit_run_id_seq"),          # 시퀀스 is_called 만 바뀌어도 실패
    (lambda r: r.update(applied=False), None, "적용 결과가 아님"),
])
def test_idempotent_refused(c29, edit, snap_b, needle):
    r = copy.deepcopy(_good(c29))
    edit(r)
    fails = c29.idempotent_fails(r, _snap(), snap_b or _snap(), DST, SRC)
    assert any(needle in f for f in fails), fails


def test_idempotent_refuses_old_snapshot_without_is_called(c29):
    old = {k: (v if not k.endswith("_id_seq") else [2, ""]) for k, v in _snap().items()}
    assert any("is_called" in f for f in c29.idempotent_fails(_good(c29), old, old, DST, SRC))


def test_rent_only_report_ignores_collective_and_refuses_a_collective_side(c29):
    tables = {"rent": ["rent_building_geocodes"]}
    report = {"applied": True, "sides": {"rent": {
        "src": SRC["rent"], "dst": DST["rent"], "tables": [_geo(c29, "rent_building_geocodes")]}}}
    assert c29.validate_report(report, DST, SRC, tables) == []
    fails = c29.validate_report(_good(c29), DST, SRC, tables)
    assert any("모르는 쪽" in f for f in fails)


def test_rent_only_check_does_not_open_collective(c29, monkeypatch):
    opened = []

    def engine_db(name):
        opened.append(name)
        raise RuntimeError("stop")

    monkeypatch.setattr(c29, "engine_db", engine_db)
    report = {"applied": True, "sides": {"rent": {
        "src": c29.SRC["rent"], "dst": c29.DST["rent"], "tables": [_geo(c29, "rent_building_geocodes")]}}}
    with pytest.raises(RuntimeError, match="stop"):
        c29.check(report, rent_only=True)
    assert opened == [c29.DST["rent"]]


def test_rent_only_cli_refuses_collective_args(c29):
    assert c29.main(["--rent-only", "--src-collective", "collective_stats", "check", "--report", "x"]) == 2


def test_cli_check_requires_report(c29):
    with pytest.raises(SystemExit):
        c29.main(["check"])
