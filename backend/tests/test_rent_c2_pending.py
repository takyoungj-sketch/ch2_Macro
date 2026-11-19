"""pending_n 은 판정 표의 pending key 만 센다."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.rent.query import pending_n_by_key

FIXTURE = "ch2rent_c2p_p2r"
KEEP = "k" * 64
PEND = "p" * 64


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


@pytest.fixture(scope="module")
def engine():
    url = _url()
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with admin.connect() as conn:
            conn.execute(text("SET default_transaction_read_only = off"))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{FIXTURE}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{FIXTURE}"'))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(type(exc).__name__)
    target = url.set(database=FIXTURE)
    eng = create_engine(
        target,
        pool_pre_ping=True,
        connect_args={"options": "-c default_transaction_read_only=off"},
    )
    with eng.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE rent_building_stats (
                building_key text PRIMARY KEY,
                display_name text
            );
            INSERT INTO rent_building_stats VALUES (:k, '유지'), (:p, '보류');
            """
        ), {"k": KEEP, "p": PEND})
    yield eng
    eng.dispose()
    with admin.connect() as conn:
        conn.execute(text("SET default_transaction_read_only = off"))
        conn.execute(text(f'DROP DATABASE IF EXISTS "{FIXTURE}" WITH (FORCE)'))
    admin.dispose()


def _ms(conn) -> tuple[float, dict[str, int]]:
    started = time.perf_counter()
    keys = [row[0] for row in conn.execute(text("SELECT building_key FROM rent_building_stats ORDER BY 1"))]
    counts = pending_n_by_key(conn, keys)
    return (time.perf_counter() - started) * 1000, counts


def test_pending_count_ignores_other_decisions_and_times_both_states(engine, capsys):
    with engine.connect() as conn:
        absent_ms, absent = _ms(conn)
    assert absent == {}
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE rent_building_key_c2_units (
                base_key text, decision text, main_lot text
            );
            INSERT INTO rent_building_key_c2_units VALUES
                (:k, 'keep', '1'),
                (:p, 'pending', '2'),
                (:p, 'split', '3');
            """
        ), {"k": KEEP, "p": PEND})
    with engine.connect() as conn:
        present_ms, present = _ms(conn)
    assert present == {PEND: 1}
    print(f"LIST_MS_ABSENT {absent_ms:.3f}")
    print(f"LIST_MS_PRESENT {present_ms:.3f}")
    captured = capsys.readouterr()
    assert "LIST_MS_ABSENT" in captured.out
    assert "LIST_MS_PRESENT" in captured.out
