"""임대 스모크. 운영 URL 은 거절하고, 표 없음·빈 표·표 있음만 구분한다."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPO = Path(__file__).resolve().parents[2]
SMOKE_PATH = REPO / "scripts" / "ops" / "rent_c2_smoke.py"
FIXTURE = "ch2rent_c2s_p2r"


def _load():
    spec = importlib.util.spec_from_file_location("rent_c2_smoke", SMOKE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


smoke = _load()


def test_smoke_does_not_import_pipeline():
    text = SMOKE_PATH.read_text(encoding="utf-8")
    assert "import pipeline" not in text
    assert "from pipeline" not in text


def test_remote_url_exits_2():
    assert smoke.main(["--base-url", "https://example.com/rent"]) == 2


def test_anon_response_is_login_only():
    assert smoke.anon_ok(401, '{"detail":"로그인이 필요합니다."}')
    assert not smoke.anon_ok(200, "확인되지 않은 거래 포함")
    assert not smoke.anon_ok(401, "다른 오류")


def _url():
    env_path = Path(r"D:\ch2\ch2_Macro\backend\.env")
    if not env_path.is_file():
        pytest.skip("로컬 DB 접속 값이 없다")
    env = dotenv_values(env_path)
    raw = str(env.get("COLLECTIVE_DATABASE_URL") or env.get("DATABASE_URL") or "")
    if not raw:
        pytest.skip("로컬 DB 접속 값이 없다")
    url = make_url(raw)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    return url


def test_three_table_states_change_the_list_check():
    url = _url()
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with admin.connect() as conn:
            conn.execute(text("SET default_transaction_read_only = off"))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{FIXTURE}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{FIXTURE}"'))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(type(exc).__name__)
    engine = create_engine(
        url.set(database=FIXTURE),
        connect_args={"options": "-c default_transaction_read_only=off"},
    )
    try:
        with engine.connect() as conn:
            assert smoke.table_state(conn) == "missing"
        assert smoke.list_ok("missing", 200, "목록")
        assert not smoke.list_ok("missing", 200, "확인되지 않은 거래 포함")
        with engine.begin() as conn:
            conn.execute(text(
                """
                CREATE TABLE rent_building_key_c2_units (
                    base_key text, decision text
                )
                """
            ))
        with engine.connect() as conn:
            assert smoke.table_state(conn) == "empty"
        assert smoke.list_ok("empty", 200, "목록")
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO rent_building_key_c2_units VALUES ('k', 'pending')"))
        with engine.connect() as conn:
            assert smoke.table_state(conn) == "present"
        assert smoke.list_ok("present", 200, "확인되지 않은 거래 포함")
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text("SET default_transaction_read_only = off"))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{FIXTURE}" WITH (FORCE)'))
        admin.dispose()
