# -*- coding: utf-8 -*-
"""집합 2단계 리허설 실행기(c3) — 표제부 DB 가 리허설 사본만 가리키고, 사본이 없으면 그 단계를 건너뛴다.

Phase C 리허설에서 title_fill_new_keys 가 기본값(같은 서버의 진짜 parcel_master)으로 붙으려다
DB 가 없어 실패했다(쓰기 0). 사본이 있었다면 apply_schema 가 진짜 DB 에 DDL 을 쓸 뻔했다.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lab" / "collective_p2" / "c3_run_rehearsal.py"


@pytest.fixture
def c3(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("c3_run_rehearsal", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "server_url_from_env", lambda: "postgresql+psycopg2://u:p@localhost:5432/postgres")
    monkeypatch.setattr(mod, "OUT", tmp_path)
    return mod


def test_parcel_engine_points_only_to_rehearsal_copy(c3):
    env = c3.env_for()
    db = make_url(env["PARCEL_MASTER_DATABASE_URL"]).database
    assert db == c3.PARCEL_DB and c3.REHEARSAL_RE.match(db)
    for k in ("COLLECTIVE_DATABASE_URL", "BUILT_DATABASE_URL", "RENT_DATABASE_URL"):
        assert c3.REHEARSAL_RE.match(make_url(env[k]).database)


def test_every_as_of_argument_is_accepted_by_builders(c3):
    """built_scope_stats 에 `2026-10`(월만)을 넘겨 실패했다 → 모든 단계의 --as-of 가 빌더 형식(월 1일)인지."""
    import sys

    sys.path.insert(0, str(ROOT / "pipeline"))
    from build_stats_v2 import parse_as_of_month

    seen = 0
    for name, cmd in c3.step_list():
        for i, a in enumerate(cmd):
            if a == "--as-of":
                parse_as_of_month(cmd[i + 1])
                seen += 1
    assert seen == 8   # 단계 목록의 --as-of 개수(빌더 8개)


def test_parcel_step_skipped_and_logged_when_copy_missing(c3, monkeypatch):
    ran: list[str] = []
    monkeypatch.setattr(c3, "database_exists", lambda name: False)
    monkeypatch.setattr(c3, "probe", lambda env: {"collective": "collective_stats_p2r"})
    monkeypatch.setattr(c3, "step_list", lambda: [("title_fill_new_keys", ["x"]), ("rent_sale_map", ["y"])])

    class _R:
        returncode = 0

    monkeypatch.setattr(c3.subprocess, "run", lambda cmd, **kw: ran.append(cmd[0]) or _R())
    monkeypatch.setattr("sys.argv", ["c3", "--from-step", "title_fill_new_keys"])
    c3.main()
    assert ran == ["y"]                                   # 표제부 단계는 실행하지 않음
    recs = [json.loads(x) for x in (c3.OUT / "c3_steps.jsonl").read_text(encoding="utf-8").splitlines()]
    assert recs[0]["step"] == "title_fill_new_keys" and "skipped" in recs[0]
    assert recs[1]["step"] == "rent_sale_map" and recs[1]["rc"] == 0
