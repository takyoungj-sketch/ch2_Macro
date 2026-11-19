"""이전 전 key 기준 검증. 본번만 같은 다른 거래는 실패가 아니다."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.collective.building_keys import c2_key  # noqa: E402
from pipeline.rent import migrate_rent_c2_keys as mig  # noqa: E402
from pipeline.rent.rent_c2_verify import key_scope_checks  # noqa: E402

FIXTURE = "ch2rent_c2m_p2r_v12"
RAW = "apartment|서울|강남|역삼|name:한빛"
BASE = "b" * 64
OTHER = "d" * 64
PIECE = "e" * 64
SHA = "a" * 64


def _base_url():
    for path in (REPO / "backend" / ".env", Path(r"D:\ch2\ch2_Macro\backend\.env")):
        if not path.is_file():
            continue
        env = dotenv_values(path)
        url = str(env.get("COLLECTIVE_DATABASE_URL") or env.get("DATABASE_URL") or "")
        if url:
            got = make_url(url)
            if got.drivername == "postgresql":
                got = got.set(drivername="postgresql+psycopg2")
            return got
    pytest.skip("로컬 DB 접속 값이 없다")


@pytest.fixture(scope="module")
def fixture_db():
    url = _base_url()
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with admin.connect() as conn:
            conn.execute(text("SET default_transaction_read_only = off"))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{FIXTURE}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{FIXTURE}"'))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"fixture DB를 만들 수 없다: {type(exc).__name__}")
    yield url
    with admin.connect() as conn:
        conn.execute(text("SET default_transaction_read_only = off"))
        conn.execute(text(f'DROP DATABASE IF EXISTS "{FIXTURE}" WITH (FORCE)'))
    admin.dispose()


def _engine(url, *, write: bool):
    return mig.rent_engine(FIXTURE, write=write, base_url=url)


def _reset(url):
    engine = _engine(url, write=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text(
            """
            CREATE TABLE rent_transactions (
                id bigint PRIMARY KEY,
                building_key text,
                asset_type text,
                beopjungri_code text,
                lot_number text
            );
            CREATE TABLE rent_building_key_map (
                old_key varchar(64) NOT NULL,
                new_key varchar(64) NOT NULL,
                asset_type varchar(32) NOT NULL,
                reason varchar(32) NOT NULL,
                split_part int NOT NULL DEFAULT 0,
                n_tx int,
                PRIMARY KEY (old_key, new_key)
            );
            CREATE TABLE rent_building_key_c2_units (
                base_key varchar(64) NOT NULL,
                asset_type varchar(16) NOT NULL,
                beopjungri_code varchar(10) NOT NULL,
                main_lot varchar(16) NOT NULL,
                part integer NOT NULL,
                decision varchar(8) NOT NULL,
                evidence varchar(32) NOT NULL DEFAULT '',
                source varchar(32) NOT NULL,
                collective_sha256 char(64) NOT NULL,
                PRIMARY KEY (base_key, asset_type, beopjungri_code, main_lot)
            );
            CREATE TABLE rent_transactions_rc2_before (
                id bigint PRIMARY KEY,
                building_key text,
                saved_at timestamptz NOT NULL DEFAULT now()
            );
            INSERT INTO rent_building_key_c2_units VALUES
                (:k, 'apartment', '1111010100', '10', 0, 'split', '', 'rent_c2_20261119', :sha),
                (:k, 'apartment', '1111010100', '11', 1, 'split', '', 'rent_c2_20261119', :sha);
            INSERT INTO rent_transactions VALUES
                (1, :k, 'apartment', '1111010100', '10'),
                (2, :piece, 'apartment', '1111010100', '11'),
                (3, :other, 'apartment', '1111010100', '10');
            INSERT INTO rent_transactions_rc2_before (id, building_key) VALUES (2, :k);
            INSERT INTO rent_building_key_map VALUES (:k, :piece, 'apartment', 'c2_split', 1, 1);
            """
        ), {"k": BASE, "piece": PIECE, "other": OTHER, "sha": SHA})
    return engine


def _flags(url, expected_updated=1):
    engine = _engine(url, write=True)
    with engine.begin() as conn:
        got = key_scope_checks(conn, expected_updated=expected_updated)
    engine.dispose()
    return got


def test_other_key_on_part0_lot_is_not_a_move(fixture_db):
    engine = _reset(fixture_db)
    engine.dispose()
    got = _flags(fixture_db)
    assert got["flags"] == {
        "part0_base_changed": 0,
        "non_base_changed": 0,
        "nonzero_key_differ": 0,
        "changed_ne_file": 0,
        "changed_ne_given": 0,
    }
    assert got["changed_n"] == 1
    assert got["expected_n"] == 1


def test_part0_base_change_fails(fixture_db):
    engine = _reset(fixture_db)
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE rent_transactions SET building_key = :now WHERE id = 1"
        ), {"now": "f" * 64})
        conn.execute(text(
            "INSERT INTO rent_transactions_rc2_before (id, building_key) VALUES (1, :k)"
        ), {"k": BASE})
    engine.dispose()
    got = _flags(fixture_db, expected_updated=2)
    assert got["flags"]["part0_base_changed"] == 1
    assert got["flags"]["changed_ne_file"] == 1


def test_non_base_change_fails(fixture_db):
    engine = _reset(fixture_db)
    with engine.begin() as conn:
        conn.execute(text("UPDATE rent_transactions SET building_key = 'zzzz' WHERE id = 3"))
        conn.execute(text(
            "INSERT INTO rent_transactions_rc2_before (id, building_key) VALUES (3, :other)"
        ), {"other": OTHER})
    engine.dispose()
    got = _flags(fixture_db, expected_updated=2)
    assert got["flags"]["non_base_changed"] == 1
    assert got["flags"]["part0_base_changed"] == 0


def test_nonzero_part_wrong_key_fails(fixture_db):
    engine = _reset(fixture_db)
    with engine.begin() as conn:
        conn.execute(text("UPDATE rent_transactions SET building_key = 'wrong' WHERE id = 2"))
    engine.dispose()
    got = _flags(fixture_db)
    assert got["flags"]["nonzero_key_differ"] == 1
    assert got["flags"]["changed_ne_file"] == 0
    assert got["changed_n"] == 1 and got["expected_n"] == 1


def test_given_count_mismatch_fails(fixture_db):
    engine = _reset(fixture_db)
    engine.dispose()
    got = _flags(fixture_db, expected_updated=24718)
    assert got["flags"]["changed_ne_given"] == 1
    assert got["flags"]["changed_ne_file"] == 0
    assert got["changed_n"] == 1


def test_apply_then_scope_matches_file_and_ignores_other_key(fixture_db):
    engine = _engine(fixture_db, write=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text(
            """
            CREATE TABLE rent_transactions (
                id bigint PRIMARY KEY,
                building_key text,
                asset_type text,
                beopjungri_code text,
                lot_number text
            );
            CREATE TABLE rent_building_key_map (
                old_key varchar(64) NOT NULL,
                new_key varchar(64) NOT NULL,
                asset_type varchar(32) NOT NULL,
                reason varchar(32) NOT NULL,
                split_part int NOT NULL DEFAULT 0,
                n_tx int,
                PRIMARY KEY (old_key, new_key)
            );
            CREATE TABLE rent_building_geocodes (
                building_key text PRIMARY KEY,
                label text NOT NULL,
                normalized_address text NOT NULL,
                status text NOT NULL DEFAULT 'ok'
            );
            CREATE TABLE rent_building_key_c2_units (
                base_key varchar(64) NOT NULL,
                asset_type varchar(16) NOT NULL,
                beopjungri_code varchar(10) NOT NULL,
                main_lot varchar(16) NOT NULL,
                part integer NOT NULL,
                decision varchar(8) NOT NULL,
                evidence varchar(32) NOT NULL DEFAULT '',
                source varchar(32) NOT NULL,
                collective_sha256 char(64) NOT NULL,
                PRIMARY KEY (base_key, asset_type, beopjungri_code, main_lot)
            );
            INSERT INTO rent_transactions VALUES
                (1, :k, 'apartment', '1111010100', '10'),
                (2, :k, 'apartment', '1111010100', '11'),
                (3, :other, 'apartment', '1111010100', '10');
            INSERT INTO rent_building_geocodes VALUES (:k, '옛', '주소', 'ok');
            INSERT INTO rent_building_key_c2_units VALUES
                (:k, 'apartment', '1111010100', '10', 0, 'split', '', 'rent_c2_20261119', :sha),
                (:k, 'apartment', '1111010100', '11', 1, 'split', '', 'rent_c2_20261119', :sha);
            """
        ), {"k": BASE, "other": OTHER, "sha": SHA})
    result = mig.apply(engine, raw_of={(BASE, "apartment"): RAW})
    piece = c2_key(RAW, "p1")
    with engine.begin() as conn:
        wide = int(conn.execute(text(
            """
            SELECT count(*) FROM rent_transactions t
            JOIN rent_building_key_c2_units u
              ON t.asset_type = u.asset_type
             AND left(t.beopjungri_code, 10) = left(u.beopjungri_code, 10)
             AND t.lot_number = u.main_lot
            WHERE u.decision = 'split' AND u.part = 0
              AND rtrim(t.building_key) <> u.base_key
            """
        )).scalar() or 0)
        got = key_scope_checks(conn, expected_updated=1)
    engine.dispose()
    assert result["updated"] == 1
    assert wide == 1
    assert got["flags"] == {
        "part0_base_changed": 0,
        "non_base_changed": 0,
        "nonzero_key_differ": 0,
        "changed_ne_file": 0,
        "changed_ne_given": 0,
    }
    assert got["changed_n"] == 1 and got["expected_n"] == 1
    assert piece
