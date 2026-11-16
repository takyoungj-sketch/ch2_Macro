# -*- coding: utf-8 -*-
"""집합 2단계 P3 — C-2 판정 파일 적재 도구: 형식 검사·리허설 이름 가드·멱등·값 충돌 멈춤."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parents[1]
for p in (PIPE, PIPE / "collective"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from collective import building_keys as bk  # noqa: E402
from collective import load_c2_units as lc  # noqa: E402
from collective import migrate_p2_keys as mig  # noqa: E402

DB = "ch2c3_p2r_fixture"
A, B, C = "a" * 64, "b" * 64, "c" * 64
HEAD = "base_key,asset_type,beopjungri_code,main_lot,building_year,part,decision,source,note,n_tx\n"
GOOD = HEAD + (f"{A},rowhouse,1150010300,354,2015.0,0.0,split,c2_final,확실 분할,11\n"
               f"{A},rowhouse,1150010300,0360,2018.0,1.0,split,c2_final,확실 분할,4\n"
               f"{B},officetel,1168010100,12,,0,split,c2_final,,3\n"
               f"{B},officetel,1168010100,15,,1,split,c2_final,,3\n"
               f"{B},officetel,1168010100,19,,2,split,c2_final,,3\n"
               f"{C},presale,3017010100,,,,keep,c2_final,확실 유지,344\n")


def _csv(tmp_path, body, name="u.csv"):
    f = tmp_path / name
    f.write_text("﻿" + body, encoding="utf-8")
    return f


def test_read_units_normalizes_and_summarizes(tmp_path):
    df = lc.read_units(_csv(tmp_path, GOOD))
    assert list(df["main_lot"]) == ["354", "360", "12", "15", "19", ""]          # 앞자리 0 제거
    assert list(df["part"]) == [0, 1, 0, 1, 2, None] and df["building_year"].iloc[0] == 2015
    s = lc.summary(df)
    assert s == {"rows": 6, "split_rows": 5, "keep_rows": 1, "split_units": 2, "added_keys": 3,
                 "by_asset": {"officetel": 1, "rowhouse": 1}}


@pytest.mark.parametrize("body,needle", [
    (HEAD + f"{A},rowhouse,1150010300,354,,1,split,x,,1\n{A},rowhouse,1150010300,355,,2,split,x,,1\n", "본 조각(0) 없는"),
    (HEAD + f"{A},rowhouse,1150010300,354,,0,split,x,,1\n", "조각이 하나뿐인"),
    (HEAD + f"{A},rowhouse,1150010300,,,0,split,x,,1\n{A},rowhouse,1150010300,9,,1,split,x,,1\n", "split 인데 본번 없음"),
    (HEAD + f"{A},rowhouse,1150010300,9,,,split,x,,1\n", "split 인데 조각 번호 없음"),
    (HEAD + f"{A[:-1]},rowhouse,1150010300,,,,keep,x,,1\n", "base_key 형식"),
    (HEAD + f"{A},rowhouse,11500103,,,,keep,x,,1\n", "법정동 코드"),
    (HEAD + f"{A},rowhouse,1150010300,,,,maybe,x,,1\n", "decision"),
    (HEAD + f"{A},presale,1150010300,1,,0,split,x,,1\n{A},presale,1150010300,2,,1,split,x,,1\n", "분양권 split"),
    (HEAD + f"{A},rowhouse,1150010300,1,,0,split,x,,1\n{A},rowhouse,1150010300,01,,1,split,x,,1\n", "중복"),
    (HEAD + f"{A},rowhouse,1150010300,,,,keep,x,,1\n{A},apartment,1168010100,,,,keep,x,,1\n", "유형 여럿"),
    (HEAD + f"{A},rowhouse,1150010300,1,,0,split,x,,1\n{A},rowhouse,1150010300,2,,1,split,x,,1\n"
            f"{A},rowhouse,1150010400,5,,0,split,x,,1\n{A},rowhouse,1150010400,6,,1,split,x,,1\n", "두 법정동에서 같이"),
])
def test_read_units_rejects_bad_rows(tmp_path, body, needle):
    with pytest.raises(lc.LoadError) as ei:
        lc.read_units(_csv(tmp_path, body))
    assert needle in str(ei.value)


def test_write_refused_for_non_rehearsal_names(tmp_path):
    f = _csv(tmp_path, GOOD)
    for name in ("collective_stats", "collective_stats_p2", "built_stats_p2r_x_y", "postgres"):
        with pytest.raises(mig.GuardError):
            lc.main(["--collective-db", name, "--csv", str(f), "--apply", "--base-url", "postgresql://u@127.0.0.1/x"])


@pytest.fixture(scope="module")
def eng():
    try:
        base = mig.server_url_from_env()
        admin = create_engine(make_url(base).set(database="postgres", drivername="postgresql+psycopg2"),
                              isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {DB}"))
            c.execute(text(f"CREATE DATABASE {DB}"))
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"로컬 PostgreSQL 임시 DB 생성 불가: {type(ex).__name__}")
    e = mig.engine_for(DB, read_only=False, base_url=base)
    yield {"eng": e, "base": base}
    e.dispose()
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)"))
    admin.dispose()


def test_load_dryrun_apply_idempotent_and_conflict(eng, tmp_path):
    e, base = eng["eng"], eng["base"]
    f = _csv(tmp_path, GOOD)
    args = ["--collective-db", DB, "--csv", str(f), "--base-url", base]
    assert lc.main(args) == 0                                           # 드라이런: 표 없음 그대로
    with e.connect() as c:
        assert c.execute(text("SELECT to_regclass(:t)"), {"t": bk.C2_TABLE}).scalar() is None
    assert lc.main(args + ["--apply"]) == 0
    with e.connect() as c:
        assert bk.c2_table_state(c) == ("ok", 6)
        units = bk.load_split_units_c2(c)
    assert units == {A: {"1150010300": [("354", 2015, 0), ("360", 2018, 1)]},
                     B: {"1168010100": [("12", None, 0), ("15", None, 1), ("19", None, 2)]}}
    # 자동 등록 행이 표에만 있어도 다시 적재하면 건너뛴다(멱등)
    with e.begin() as c:
        c.execute(text(f"""INSERT INTO {bk.C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, building_year, part,
            decision, source) VALUES (:a, 'rowhouse', '1150010300', '400', 2020, 2, 'split', 'p2_migrate')"""), {"a": A})
    df = lc.read_units(f)
    out = lc.load(e, DB, df, apply=True)
    assert (out["insert"], out["already_same"], out["table_only_rows"], out["table_rows_after"]) == (0, 6, 1, 7)
    # 값이 다른 파일 → 쓰지 않고 멈춤
    bad = _csv(tmp_path, GOOD.replace(f"{A},rowhouse,1150010300,0360,2018.0,1.0", f"{A},rowhouse,1150010300,0360,2018.0,3.0"),
               "bad.csv")
    with pytest.raises(lc.LoadError):
        lc.load(e, DB, lc.read_units(bad), apply=True)
    with e.connect() as c:
        assert c.execute(text(f"SELECT count(*) FROM {bk.C2_TABLE}")).scalar() == 7


def test_load_rejects_connected_db_name_mismatch(eng, tmp_path):
    """이름 확인을 통과해도 접속한 DB 이름이 다르면(assert_rehearsal_db) 쓰지 않는다."""
    with pytest.raises(mig.GuardError):
        lc.load(eng["eng"], "other_p2r", lc.read_units(_csv(tmp_path, GOOD)), apply=True)


def test_real_decision_file_passes_checks_if_present():
    """로컬 확정 파일(logs/, 커밋 안 됨)이 있으면 형식 검사를 통과해야 한다 — 건수만 확인."""
    if not lc.DEFAULT_CSV.is_file():
        pytest.skip("확정 판정 파일 없음(로컬 전용)")
    s = lc.summary(lc.read_units(lc.DEFAULT_CSV))
    assert s["rows"] == 4311 and s["split_units"] == 1610 and s["added_keys"] == 2045


def test_final_state_rejects_fragment_number_reused_in_other_dong(eng, tmp_path):
    """Codex 재현: 표에 이미 있는 자동 등록 조각(다른 법정동, 조각 1)과 파일의 조각 1 이 같은 키 → 거절, 아무것도 쓰지 않음."""
    import pandas as pd

    e = eng["eng"]
    df = lc.read_units(_csv(tmp_path, GOOD))
    cur = pd.DataFrame([{"base_key": A, "asset_type": "rowhouse", "beopjungri_code": "1150010400", "main_lot": "77",
                         "building_year": 2020, "part": 1, "decision": "split", "source": "auto_ingest", "note": ""},
                        {"base_key": A, "asset_type": "rowhouse", "beopjungri_code": "1150010400", "main_lot": "70",
                         "building_year": 2019, "part": 0, "decision": "split", "source": "auto_ingest", "note": ""}])
    assert any("두 법정동" in x for x in lc.final_state_errors(df, cur))
    # 같은 법정동 안 다른 본번이 같은 조각이면 정상
    ok = cur.assign(beopjungri_code="1150010300", main_lot=["377", "378"], part=[1, 0])
    assert lc.final_state_errors(df, ok) == []
    # 본 조각 0 이 없는 묶음이 최종 상태에 생기면 거절
    assert any("본 조각(0)" in x for x in lc.final_state_errors(df, cur.iloc[[0]]))
    # DB 에서도: 표에 다른 법정동 조각 1 을 넣어 두면 적재가 멈추고 표는 그대로
    with e.begin() as c:
        c.execute(text(f"DELETE FROM {bk.C2_TABLE}"))
        c.execute(text(f"""INSERT INTO {bk.C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, building_year, part,
            decision, source) VALUES (:a, 'rowhouse', '1150010400', '77', 2020, 1, 'split', 'auto_ingest'),
            (:a, 'rowhouse', '1150010400', '70', 2019, 0, 'split', 'auto_ingest')"""), {"a": A})
    with pytest.raises(lc.LoadError, match="최종 상태"):
        lc.load(e, DB, df, apply=True)
    with e.connect() as c:
        assert c.execute(text(f"SELECT count(*) FROM {bk.C2_TABLE}")).scalar() == 2


# --- Codex Phase D 3: 실제 DB 판정 표 적재 — 승인 파일 해시·행 수 대조, 키 이전 시작 전 확인 ------------------

def _fresh(e):
    with e.begin() as c:
        c.execute(text(f"DROP TABLE IF EXISTS {bk.C2_TABLE}"))
        c.execute(text("DROP TABLE IF EXISTS p2_migration_log"))


def test_approved_file_check_hash_and_rows(tmp_path):
    f = _csv(tmp_path, GOOD)
    df = lc.read_units(f)
    sha = lc.file_sha256(f)
    lc.check_approved_file(f, df, sha, 6)
    lc.check_approved_file(f, df, sha.upper(), 6)                      # 대소문자 무관
    with pytest.raises(lc.LoadError, match="SHA-256 이 승인값과 다름"):
        lc.check_approved_file(f, df, "0" * 64, 6)
    with pytest.raises(lc.LoadError, match="행 수"):
        lc.check_approved_file(f, df, sha, 4311)
    with pytest.raises(lc.LoadError, match="형식"):
        lc.check_approved_file(f, df, "abc", 6)


def test_real_apply_cli_needs_approval_args_and_refuses_wrong_hash_before_write(tmp_path):
    f = _csv(tmp_path, GOOD)
    base = ["--collective-db", "collective_stats", "--csv", str(f), "--base-url", "postgresql://u@127.0.0.1/x",
            "--real-apply", "--confirm-db", "collective_stats"]
    with pytest.raises(lc.LoadError, match="approved-sha256"):
        lc.main(base)
    with pytest.raises(lc.LoadError, match="SHA-256 이 승인값과 다름"):     # 가드(동기화 확인) 전에 파일 대조에서 멈춤
        lc.main(base + ["--approved-sha256", "0" * 64, "--approved-rows", "6"])
    with pytest.raises(mig.GuardError):                                   # 해시는 맞아도 동기화 확인 결과 없음 → 거부
        lc.main(base + ["--approved-sha256", lc.file_sha256(f), "--approved-rows", "6"])


def test_migrate_real_apply_refuses_empty_table_wrong_hash_and_passes_when_approved(eng, tmp_path):
    """키 이전 시작 전 판정 표 대조 — 빈 표 · 다른 해시 · 정상(+ 행 수 다름 · 적재 뒤 바뀜)."""
    e, base = eng["eng"], eng["base"]
    f = _csv(tmp_path, GOOD)
    sha = lc.file_sha256(f)
    _fresh(e)
    with pytest.raises(mig.GuardError, match="없음"):                      # 표 자체가 없음
        mig.assert_c2_units_approved(e, sha, 6)
    with e.begin() as c:
        mig._exec_script(c, bk.C2_DDL)
    with pytest.raises(mig.GuardError, match="비었음"):                    # 빈 표
        mig.assert_c2_units_approved(e, sha, 6)
    # 승인 파일로 적재(리허설 모드) → 적재 기록에 파일 해시·내용 해시
    assert lc.main(["--collective-db", DB, "--csv", str(f), "--base-url", base, "--apply",
                    "--approved-sha256", sha, "--approved-rows", "6"]) == 0
    ok = mig.assert_c2_units_approved(e, sha, 6)                          # 정상
    assert ok["rows"] == 6 and ok["file_sha256"] == sha
    with pytest.raises(mig.GuardError, match="SHA-256 이 승인값과 다름"):    # 다른 해시
        mig.assert_c2_units_approved(e, "f" * 64, 6)
    with pytest.raises(mig.GuardError, match="행 수"):
        mig.assert_c2_units_approved(e, sha, 4311)
    # 키 이전이 자동 등록한 행(p2_migrate)은 판정 행으로 세지 않는다
    with e.begin() as c:
        c.execute(text(f"""INSERT INTO {bk.C2_TABLE} (base_key, asset_type, beopjungri_code, main_lot, building_year, part,
            decision, source) VALUES (:a, 'rowhouse', '1150010300', '400', 2020, 2, 'split', 'p2_migrate')"""), {"a": A})
    assert mig.assert_c2_units_approved(e, sha, 6)["rows"] == 6
    # 적재 뒤 판정 행이 바뀌면 거부
    with e.begin() as c:
        c.execute(text(f"UPDATE {bk.C2_TABLE} SET part = 5 WHERE base_key = :a AND main_lot = '360'"), {"a": A})
    with pytest.raises(mig.GuardError, match="적재 기록과 다름"):
        mig.assert_c2_units_approved(e, sha, 6)
    _fresh(e)


def test_migrate_cli_real_apply_requires_c2_approval_args():
    with pytest.raises(mig.GuardError, match="c2-approved"):
        mig.main(["--collective-db", "collective_stats", "--real-apply", "--confirm-db", "collective_stats",
                  "--base-url", "postgresql://u@127.0.0.1/x"])
