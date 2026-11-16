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


def test_run_refuses_when_main_repo_tracked_files_change(monkeypatch, tmp_path):
    """Codex Phase D 1: 생성기가 이 저장소의 추적 파일(docs/lab 등)을 덮으면 멈춘다(worktree 는 그대로여도)."""
    (tmp_path / c27.GEN).parent.mkdir(parents=True)
    (tmp_path / c27.GEN).write_text("", encoding="utf-8")
    monkeypatch.setattr(c27, "OUT", tmp_path / "out")
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "worktree.json").write_text(json.dumps({"path": str(tmp_path), "commit": "c" * 40}), encoding="utf-8")
    state = {"repo": ""}

    def runner(cmd, **kw):
        state["repo"] = " M docs/lab/rowhouse_elevator_attach.csv"
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def g(*args, cwd=None):
        if args[:2] == ("rev-parse", "HEAD"):
            return "c" * 40
        return state["repo"] if Path(cwd) == c27.ROOT else ""

    with pytest.raises(c27.StopRun, match="저장소 추적 파일 변경 1개"):
        c27.run("after", git_=g, runner=runner)
    state["repo"] = " M x.py"
    with pytest.raises(c27.StopRun, match="실행 전"):
        c27.run("after", git_=g, runner=runner)


def _c22():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "c22", c27.ROOT / "scripts" / "lab" / "collective_p2" / "c22_insight_recompute.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_c22_runner03_redirects_attach_csv_and_title_cache(tmp_path):
    """Codex Phase D 1: Insight 03 의 부속 CSV·표제부 캐시도 logs/<side>/ 로(기본값은 docs/lab — 함수 인자에 묶임)."""
    c22 = _c22()
    code = c22.RUNNERS["03"].format(out=tmp_path, as_of="2026-08-01")
    compile(code, "runner03", "exec")
    assert "cache_path=cache" in code and "rowhouse_elevator_attach.csv" in code and "write_attach_csv" in code
    assert "m.purpose_by_building" in code and "fa.scan_title_for_pnus" in code
    assert "14" not in c22.RUNNERS                         # 14 는 c27 로 통일


def test_c22_tracked_change_guard():
    c22 = _c22()
    c22.assert_clean("x", git_status="")
    assert c22.tracked_changes(git_status=" M docs/lab/a.csv\n D b.json\n") == ["b.json", "docs/lab/a.csv"]
    with pytest.raises(c22.TrackedChange, match="2개"):
        c22.assert_clean("실행 뒤", git_status=" M docs/lab/a.csv\n M docs/lab/b.json\n")
