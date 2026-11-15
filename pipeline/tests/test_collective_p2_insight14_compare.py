# -*- coding: utf-8 -*-
"""집합 2단계 P5 — Insight 14 리허설 비교 스크립트(c27): 읽기 전용 실행 가드·숫자 뽑기·비교."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("c27", ROOT / "scripts" / "lab" / "collective_p2" / "c27_insight14_compare.py")
c27 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c27)

SAMPLE = {
    "status": "executed", "as_of": "2026-10-01", "period_start": "2021-11-01", "period_end": "2026-10-31",
    "stage1": {"same_building_n": 2417},
    "same_building": {
        "direct": {"pass_n": 104, "distribution": {"n": 104, "median": 0.6195, "p25": 0.5374, "p75": 0.7499,
                                                    "share_below": 0.9808}},
        "followup": {"strict_90_92d": {"pass_n": 62, "distribution": {"median": 0.6138}}},
        "regression": {"n_fit": 88, "intervals": {"entirely_below_0": 84}, "pooled": {"percent": -37.83}},
    },
}


def test_headline_matches_published_text_numbers():
    h = c27.headline(SAMPLE)
    assert (h["nHeadline"], h["nStrict"], h["nRegression"], h["nIntervalBelow"]) == (104, 62, 88, 84)
    assert (h["medianPct"], h["p25Pct"], h["p75Pct"], h["nBelow"], h["strictMedianPct"]) == (62.0, 53.7, 75.0, 102, 61.4)
    assert h["candidates"] == 2417 and h["periodEnd"] == "2026-10-31"


def test_snapshot_from_main_ts():
    s = c27.ts_snapshot()
    assert s["nHeadline"] == 104 and s["nStrict"] == 62 and s["periodStart"] == "2021-11-01"


def test_compare_table_flags_differences():
    snap = {"nHeadline": 104, "nStrict": 62}
    tab, diffs = c27.compare_table(snap, SAMPLE, SAMPLE)
    assert diffs == [] and "| nHeadline | 104 | 104 | 104 | 0 |" in tab
    after = json.loads(json.dumps(SAMPLE))
    after["same_building"]["direct"]["pass_n"] = 101
    _, diffs = c27.compare_table(snap, SAMPLE, after)
    assert diffs == ["nHeadline"]
    tab, diffs = c27.compare_table(snap, SAMPLE, None)
    assert diffs == [] and "| nHeadline | 104 | 104 | — |" in tab


def test_env_is_read_only_and_after_uses_rehearsal_names():
    env = c27.env_for("after", "postgresql://u:secret@127.0.0.1:5432/x")
    assert env["PGOPTIONS"] == "-c default_transaction_read_only=on" and env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["COLLECTIVE_DATABASE_URL"].endswith("/collective_stats_p2r")
    assert env["PARCEL_MASTER_DATABASE_URL"].endswith("/parcel_master_p2r")
    assert not any(k.endswith("_DATABASE_URL") and k not in ("COLLECTIVE_DATABASE_URL", "PARCEL_MASTER_DATABASE_URL")
                   for k in env)


def test_runner_redirects_output_and_pins_period(tmp_path):
    code = c27.runner_code({"path": str(tmp_path / "wt")}, tmp_path / "after.json")
    assert "m.OUT = Path(" in code and "2026-10-01" in code and "is_relative_to" in code
    compile(code, "runner", "exec")


def _fake_git(head="c" * 40, dirty=""):
    def g(*args, cwd=None):
        if args[:2] == ("rev-parse", "HEAD"):
            return head
        if args[0] == "status":
            return dirty
        raise AssertionError(args)
    return g


def test_check_worktree_refuses_moved_head_or_dirty(tmp_path):
    (tmp_path / c27.GEN).parent.mkdir(parents=True)
    (tmp_path / c27.GEN).write_text("", encoding="utf-8")
    info = {"path": str(tmp_path), "commit": "c" * 40}
    c27.check_worktree(info, git_=_fake_git())
    with pytest.raises(c27.StopRun, match="HEAD"):
        c27.check_worktree(info, git_=_fake_git(head="d" * 40))
    with pytest.raises(c27.StopRun, match="바뀐 파일"):
        c27.check_worktree(info, git_=_fake_git(dirty=" M backend/x.py\n?? y.pyc"))
    with pytest.raises(c27.StopRun, match="생성기"):
        c27.check_worktree({"path": str(tmp_path / "none"), "commit": "c" * 40}, git_=_fake_git())


def test_run_checks_worktree_before_and_after(monkeypatch, tmp_path):
    (tmp_path / c27.GEN).parent.mkdir(parents=True)
    (tmp_path / c27.GEN).write_text("", encoding="utf-8")
    monkeypatch.setattr(c27, "OUT", tmp_path / "out")
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "worktree.json").write_text(json.dumps({"path": str(tmp_path), "commit": "c" * 40}), encoding="utf-8")
    state = {"dirty": ""}

    def runner(cmd, **kw):
        assert kw["env"]["PGOPTIONS"].endswith("read_only=on")
        state["dirty"] = " M backend/app/x.py"          # 실행 중 worktree 가 바뀐 경우
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def g(*args, cwd=None):
        return "c" * 40 if args[:2] == ("rev-parse", "HEAD") else state["dirty"]

    with pytest.raises(c27.StopRun, match="바뀐 파일"):
        c27.run("after", git_=g, runner=runner)
