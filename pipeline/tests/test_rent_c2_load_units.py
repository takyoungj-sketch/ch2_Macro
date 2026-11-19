"""임대 C-2 판정 적재. fixture 데이터베이스만 쓰고 rent_stats에는 연결하지 않는다."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.rent import load_rent_c2_units as loader  # noqa: E402

FIXTURE = "ch2rent_c2u_p2r"
FIXTURE_B = "ch2rent_c2u_p2r_b"
SHA = "a" * 64
H_R = "2660f8e2d75728caa06c6e7899141d8f7cbfbb7698c2bd89637b53ea22506681"


def _base_url() -> str:
    for path in (REPO / "backend" / ".env", Path(r"D:\ch2\ch2_Macro\backend\.env")):
        if not path.is_file():
            continue
        env = dotenv_values(path)
        url = str(env.get("RENT_DATABASE_URL") or env.get("COLLECTIVE_DATABASE_URL") or env.get("DATABASE_URL") or "")
        if url:
            return url
    pytest.skip("로컬 DB 접속 값이 없다")
    return ""


def _csv(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "units.csv"
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
    return path


def _row(**kwargs) -> dict:
    base = {
        "base_key": "b1",
        "asset_type": "apartment",
        "beopjungri_code": "1111010100",
        "main_lot": "1",
        "part": "0",
        "decision": "keep",
        "evidence": "collective_reuse",
        "source": "rent_c2_20261119",
        "collective_sha256": SHA,
        "note": "",
    }
    base.update(kwargs)
    return base


def _split_rows() -> list[dict]:
    return [
        _row(base_key="s1", main_lot="10", part="0", decision="split", evidence="collective_ledger"),
        _row(base_key="s1", main_lot="11", part="1", decision="split", evidence="collective_ledger"),
        _row(base_key="p1", main_lot="20", part="0", decision="pending", evidence=""),
    ]


@pytest.fixture(scope="module")
def fixture_db():
    try:
        url = make_url(_base_url())
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"로컬 DB에 연결할 수 없다: {type(exc).__name__}")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with admin.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("SET default_transaction_read_only = off"))
            for name in (FIXTURE, FIXTURE_B):
                conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
                conn.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"fixture DB를 만들 수 없다: {type(exc).__name__}")
    yield url
    with admin.connect() as conn:
        conn.execute(text("SET default_transaction_read_only = off"))
        for name in (FIXTURE, FIXTURE_B):
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def test_approved_constants_match_decision():
    assert loader.APPROVED_ROWS == 6054
    assert loader.APPROVED_SHA256 == H_R


def test_wrong_approval_rejected_before_any_db(tmp_path: Path):
    path = _csv(tmp_path, _split_rows())
    df = loader.read_units(path)
    with pytest.raises(loader.LoadError):
        loader.check_approved_file(path, df, H_R, loader.APPROVED_ROWS)


def test_content_hash_ignores_row_order(tmp_path: Path):
    first = tmp_path / "units.csv"
    second = tmp_path / "reversed.csv"
    pd.DataFrame(_split_rows()).to_csv(first, index=False, encoding="utf-8", lineterminator="\n")
    pd.DataFrame(list(reversed(_split_rows()))).to_csv(
        second, index=False, encoding="utf-8", lineterminator="\n"
    )
    left = loader.content_sha256(loader.read_units(first))
    right = loader.content_sha256(loader.read_units(second))
    assert left == right
    assert left != hashlib.sha256(first.read_bytes()).hexdigest()


def test_split_without_part_zero_is_invalid():
    rows = pd.DataFrame([
        _row(base_key="s1", main_lot="10", part="1", decision="split", evidence="manual"),
        _row(base_key="s1", main_lot="11", part="2", decision="split", evidence="manual"),
    ])
    rows["part"] = pd.to_numeric(rows["part"])
    rows["main_lot"] = rows["main_lot"]
    assert loader.final_state_errors(rows)


def _frame(rows: list[dict]) -> pd.DataFrame:
    out = pd.DataFrame(rows)
    out["part"] = pd.to_numeric(out["part"])
    return out


def test_part_zero_keep_and_split_may_span_legal_dongs():
    rows = _frame([
        _row(base_key="k1", beopjungri_code="1111010100", main_lot="1", part="0", decision="keep", evidence=""),
        _row(base_key="k1", beopjungri_code="1111010200", main_lot="2", part="0", decision="keep", evidence="title_register"),
        _row(base_key="s1", beopjungri_code="1111010100", main_lot="10", part="0", decision="split", evidence="collective_reuse"),
        _row(base_key="s1", beopjungri_code="1111010100", main_lot="11", part="1", decision="split", evidence="collective_reuse"),
        _row(base_key="s1", beopjungri_code="1111010200", main_lot="12", part="0", decision="split", evidence=""),
        _row(base_key="s1", beopjungri_code="1111010200", main_lot="13", part="2", decision="split", evidence="collective_reuse"),
    ])
    assert loader.final_state_errors(rows) == []


def test_nonzero_part_spanning_legal_dongs_is_rejected():
    rows = _frame([
        _row(base_key="s1", beopjungri_code="1111010100", main_lot="10", part="0", decision="split", evidence="collective_ledger"),
        _row(base_key="s1", beopjungri_code="1111010100", main_lot="11", part="1", decision="split", evidence="collective_ledger"),
        _row(base_key="s1", beopjungri_code="1111010200", main_lot="12", part="0", decision="split", evidence="collective_ledger"),
        _row(base_key="s1", beopjungri_code="1111010200", main_lot="13", part="1", decision="split", evidence="collective_ledger"),
    ])
    errors = loader.final_state_errors(rows)
    assert any("0이 아닌 조각이 법정동을 넘는다" in item for item in errors)


def test_split_dong_and_keep_dong_on_one_key_passes():
    rows = _frame([
        _row(base_key="b1", beopjungri_code="1111010100", main_lot="10", part="0", decision="split", evidence="collective_reuse"),
        _row(base_key="b1", beopjungri_code="1111010100", main_lot="11", part="1", decision="split", evidence="collective_reuse"),
        _row(base_key="b1", beopjungri_code="1111010200", main_lot="20", part="0", decision="keep", evidence=""),
        _row(base_key="b1", beopjungri_code="1111010200", main_lot="21", part="0", decision="keep", evidence="title_register"),
    ])
    assert loader.final_state_errors(rows) == []


def test_rent_stats_is_refused_and_rehearsal_name_is_allowed():
    for name in ("rent_stats", "collective_stats"):
        with pytest.raises(loader.GuardError):
            loader.assert_write_db(name)
    loader.assert_write_db("rent_stats_rc2r")


def _db_url(url) -> str:
    return url.render_as_string(hide_password=False)


def test_dry_run_does_not_create_table(fixture_db, tmp_path: Path):
    path = _csv(tmp_path, _split_rows())
    code = loader.main(["--rent-db", FIXTURE, "--csv", str(path), "--base-url", _db_url(fixture_db)])
    assert code == 0
    engine = loader.rent_engine(FIXTURE, apply=False, base_url=fixture_db)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass('rent_building_key_c2_units')")).scalar() is None
    engine.dispose()


def test_apply_then_same_file_inserts_once(fixture_db, tmp_path: Path):
    path = _csv(tmp_path, _split_rows())
    assert loader.main([
        "--rent-db", FIXTURE, "--csv", str(path), "--apply", "--base-url", _db_url(fixture_db),
    ]) == 0
    engine = loader.rent_engine(FIXTURE, apply=False, base_url=fixture_db)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM rent_building_key_c2_units")).scalar()
        logs = conn.execute(text("SELECT count(*) FROM rent_c2_migration_log")).scalar()
    engine.dispose()
    assert count == 3
    assert logs == 1
    assert loader.main([
        "--rent-db", FIXTURE, "--csv", str(path), "--apply", "--base-url", _db_url(fixture_db),
    ]) == 0
    engine = loader.rent_engine(FIXTURE, apply=False, base_url=fixture_db)
    with engine.connect() as conn:
        logs = conn.execute(text("SELECT count(*) FROM rent_c2_migration_log")).scalar()
    engine.dispose()
    assert logs == 1


def test_value_conflict_rolls_back(fixture_db, tmp_path: Path):
    path = _csv(tmp_path, [_row(base_key="s1", main_lot="10", part="0", decision="keep")])
    engine = loader.rent_engine(FIXTURE_B, apply=True, base_url=fixture_db)
    with engine.begin() as conn:
        conn.execute(text(loader.DDL))
        conn.execute(text(
            """
            INSERT INTO rent_building_key_c2_units
                (base_key, asset_type, beopjungri_code, main_lot, part, decision,
                 evidence, source, collective_sha256)
            VALUES ('s1', 'apartment', '1111010100', '10', 1, 'split',
                    'manual', 'rent_c2_20261119', :sha)
            """
        ), {"sha": SHA})
    engine.dispose()
    assert loader.main([
        "--rent-db", FIXTURE_B, "--csv", str(path), "--apply", "--base-url", _db_url(fixture_db),
    ]) == 2
    engine = loader.rent_engine(FIXTURE_B, apply=False, base_url=fixture_db)
    with engine.connect() as conn:
        part = conn.execute(text(
            "SELECT part FROM rent_building_key_c2_units WHERE base_key = 's1' AND main_lot = '10'"
        )).scalar()
    engine.dispose()
    assert int(part) == 1
