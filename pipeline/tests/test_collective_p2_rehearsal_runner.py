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


def _load(name):
    import os
    import sys

    if str(SCRIPT.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT.parent))   # c8 은 같은 폴더의 _db 를 import(_db 는 cwd 를 backend 로 바꾼다)
    cwd = os.getcwd()
    try:
        return _load_inner(name)
    finally:
        os.chdir(cwd)


def _load_inner(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPT.with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_built_scope_cleanup_commits_only_legacy_rows_of_as_of(tmp_path):
    """옛 한 줄 코드는 첫 쿼리에서 「Connection is closed」로 실패했다 → 실제 PG 임시 DB 에서 삭제·커밋 확인."""
    from sqlalchemy import create_engine, text

    sys_path = str(ROOT / "pipeline")
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    from collective import migrate_p2_keys as mig

    cl = _load("c3_built_scope_cleanup")
    fx = "ch2_scope_cleanup_p2r"
    try:
        base = make_url(mig.server_url_from_env())
        admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT",
                              connect_args={"connect_timeout": 3})
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {fx}"))
            c.execute(text(f"CREATE DATABASE {fx}"))
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"로컬 PostgreSQL 임시 DB 생성 불가: {type(ex).__name__}")
    eng = create_engine(base.set(database=fx))
    try:
        with eng.begin() as c:
            c.execute(text("CREATE TABLE built_scope_stats (as_of_month date, addr1 text)"))
            c.execute(text("INSERT INTO built_scope_stats VALUES ('2026-10-01','광주광역시'), ('2026-10-01','전라남도'), "
                           "('2026-10-01','전남광주통합특별시'), ('2026-09-01','전라남도')"))
        assert cl.cleanup(eng, "2026-10-01") == 2
        with eng.connect() as c:   # 커밋됨 + 과거 as_of·새 이름 행은 남음
            left = sorted(tuple(map(str, r)) for r in c.execute(text("SELECT as_of_month, addr1 FROM built_scope_stats")))
        assert left == [("2026-09-01", "전라남도"), ("2026-10-01", "전남광주통합특별시")]
        other = create_engine(base.set(database="postgres"))
        with pytest.raises(SystemExit):
            cl.cleanup(other, "2026-10-01")   # 리허설 이름이 아니면 쓰기 전에 멈춤
        other.dispose()
    finally:
        eng.dispose()
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {fx} WITH (FORCE)"))
        admin.dispose()


def test_rollback_compare_classifies_rehearsal_tables():
    """C-10 보존 표(*_p2_oldjoin)는 리허설이 만든 표로 — 「원본에 없음」(차이)으로 세지 않는다."""
    c8 = _load("c8_rollback_rehearsal")
    same, other = (3, "h"), (3, "x")
    assert c8.classify("t", same, same) == "같음"
    assert c8.classify("t", same, other) == "다름"
    assert c8.classify("collective_building_stats_p2_oldjoin", None, same).startswith("이전이 만든 표")
    assert c8.classify("collective_transactions_p2_before", None, same).startswith("이전이 만든 표")
    assert c8.classify("collective_building_key_map", None, same).startswith("이전이 만든 표")
    assert c8.classify("collective_building_key_c2_units", None, same).startswith("이전이 만든 표")      # C-2 판정 표
    assert c8.classify("collective_building_annual_orphan_p2_before", None, same).startswith("이전이 만든 표")
    assert c8.classify("new_table", None, same) == "원본에 없음"
    assert c8.classify("t", same, None) == "리허설에 없음"


def test_c9_before_side_read_only_and_gates_open(monkeypatch):
    """c9: 전(진짜 로컬 DB)은 모든 세션 읽기 전용, 후는 *_p2r. 처음 실행은 게이트 401 로 화면을 재현하지 못했다."""
    c9 = _load("c9_screens")
    monkeypatch.setattr("collective.migrate_p2_keys.server_url_from_env",
                        lambda: "postgresql+psycopg2://u:p@localhost:5432/postgres")
    before, after = c9._env("before"), c9._env("after")
    assert before["PGOPTIONS"] == "-c default_transaction_read_only=on"
    assert "PGOPTIONS" not in after or after["PGOPTIONS"] == __import__("os").environ.get("PGOPTIONS")
    for k in ("COLLECTIVE_DATABASE_URL", "BUILT_DATABASE_URL", "RENT_DATABASE_URL"):
        assert make_url(after[k]).database.endswith("_p2r") and not make_url(before[k]).database.endswith("_p2r")

    import sys

    sys.path.insert(0, str(ROOT / "backend"))
    import asyncio

    from app import product_gate
    from app.config import settings

    monkeypatch.setattr(settings, "api_token", "x")
    monkeypatch.setattr(product_gate, "product_gate_response", product_gate.product_gate_response)
    c9._open_gates()
    assert settings.api_token == "" and asyncio.run(product_gate.product_gate_response(None)) is None


def test_c14_links_main_raw_into_worktree(tmp_path):
    """c14: 표제부 원천 경로가 저장소 기준이라 worktree 에서 raw 를 못 찾아 실패했다 → 원본 raw 정션."""
    import os

    c14 = _load("c14_title_copy")
    main_raw = tmp_path / "main" / "raw"
    (main_raw / "raw addition").mkdir(parents=True)
    (main_raw / "raw addition" / "x.txt").write_text("1", encoding="utf-8")
    wt = tmp_path / "wt"
    wt.mkdir()
    link = c14.ensure_raw_link(wt, main_raw)
    assert (link / "raw addition" / "x.txt").read_text(encoding="utf-8") == "1"
    assert c14.ensure_raw_link(wt, main_raw) == link        # 두 번째는 그대로
    os.rmdir(link)                                            # 정션만 지움(원본 유지)
    assert (main_raw / "raw addition" / "x.txt").exists()
    with pytest.raises(SystemExit):
        c14.ensure_raw_link(wt, tmp_path / "none")


def test_attribute_steps_pin_snapshot_and_key_list(c3):
    """1차 리허설: title_fill 이 판 없이 돌아 최신 판(202610)으로 갔다 → 속성·공시지가 단계는 판·키 목록 명시."""
    steps = dict(c3.step_list())
    kapt = steps["kapt_new_keys_apartment"]
    assert kapt[kapt.index("--snapshot-ym") + 1] == c3.ATTR_SNAPSHOT == "202607"
    assert "--new-keys-only" in kapt and kapt[kapt.index("--keys-file") + 1] == str(c3.KEYS_FILE)
    tfc = " ".join(steps["title_fill_new_keys"])
    assert f"snapshot_ym='{c3.ATTR_SNAPSHOT}'" in tfc and "keys=load_keys_file(" in tfc and "new_keys_only=True" in tfc
    lp = steps["land_price_new_keys"]
    assert "--insert-only" in lp and "--rehearsal" in lp and "--keys-file" in lp
    names = [n for n, _ in c3.step_list()]
    assert names.index("split_keys_file") < names.index("kapt_new_keys_apartment") < names.index("title_fill_new_keys") \
        < names.index("land_price_new_keys")
    env = c3.env_for()
    assert make_url(env["DATABASE_URL"]).database == c3.LAND_DB and c3.REHEARSAL_RE.match(c3.LAND_DB)


def test_rollback_restores_attribute_and_land_price_tables():
    """속성·builder_master·공시지가는 분할 새 키 행이 추가되고 키 이전 되돌리기가 그 행을 지우지 않는다 → 덤프 복원 대상."""
    c8 = _load("c8_rollback_rehearsal")
    need = {"collective_building_attributes", "builder_master", "collective_building_assessed_land_price"}
    assert need <= set(c8.MARTS["collective_stats"])


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
