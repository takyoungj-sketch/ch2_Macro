"""임대 C-2 키 이전. fixture 만 쓰고 집합 쓰기는 실패로 본다."""
from __future__ import annotations

import hashlib
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

FIXTURE = "ch2rent_c2m_p2r"
RAW = "apartment|서울|강남|역삼|name:한빛"
BASE = "b" * 64
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


def _schema(conn, *, units: bool) -> None:
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
        CREATE TABLE rent_c2_migration_log (
            id bigserial PRIMARY KEY,
            step varchar(64) NOT NULL,
            detail jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    ))
    conn.execute(text(
        """
        INSERT INTO rent_transactions VALUES
            (1, :k, 'apartment', '1111010100', '10'),
            (2, :k, 'apartment', '1111010100', '11');
        INSERT INTO rent_building_geocodes VALUES (:k, '옛', '주소', 'ok');
        INSERT INTO rent_building_key_map VALUES (:k, :other, 'apartment', 'split', 1, 3);
        """
    ), {"k": BASE, "other": "c" * 64})
    if units:
        conn.execute(text(
            """
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
            INSERT INTO rent_building_key_c2_units VALUES
                (:k, 'apartment', '1111010100', '10', 0, 'split', 'collective_reuse', 'rent_c2_20261119', :sha),
                (:k, 'apartment', '1111010100', '11', 1, 'split', 'collective_reuse', 'rent_c2_20261119', :sha);
            """
        ), {"k": BASE, "sha": SHA})


def test_source_does_not_open_collective_writer():
    text = (REPO / "pipeline" / "rent" / "migrate_rent_c2_keys.py").read_text(encoding="utf-8")
    assert "get_collective_engine" not in text
    assert "apply_collective" not in text
    assert "apply_rent" not in text


def test_rehearsal_local_guard_accepts_loopback():
    mig.assert_rehearsal_local(make_url("postgresql+psycopg2://local@127.0.0.1:5432/rent_stats_rc2r"))


def test_real_rent_names_are_refused():
    for name in ("rent_stats", "collective_stats"):
        with pytest.raises(mig.GuardError):
            mig.assert_fixture(name)
    mig.assert_fixture("rent_stats_rc2r")


def _reset(url):
    engine = _engine(url, write=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    return engine


def test_missing_table_changes_nothing(fixture_db):
    engine = _reset(fixture_db)
    with engine.begin() as conn:
        _schema(conn, units=False)
    first = mig.apply(engine, raw_of={(BASE, "apartment"): RAW})
    engine.dispose()
    assert first["changed"] == 0
    engine = _engine(fixture_db, write=False)
    with engine.connect() as conn:
        left = conn.execute(text("SELECT count(*) FROM rent_building_geocodes")).scalar()
    engine.dispose()
    assert int(left) == 1


def test_split_moves_keys_and_drops_old_geocode(fixture_db):
    engine = _reset(fixture_db)
    with engine.begin() as conn:
        _schema(conn, units=False)
        conn.execute(text(
            """
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
            INSERT INTO rent_building_key_c2_units VALUES
                (:k, 'apartment', '1111010100', '10', 0, 'split', 'collective_reuse', 'rent_c2_20261119', :sha),
                (:k, 'apartment', '1111010100', '11', 1, 'split', 'collective_reuse', 'rent_c2_20261119', :sha);
            """
        ), {"k": BASE, "sha": SHA})
    result = mig.apply(engine, raw_of={(BASE, "apartment"): RAW})
    again = mig.apply(engine, raw_of={(BASE, "apartment"): RAW})
    engine.dispose()
    assert result["updated"] == 1
    assert result["geocode_dropped"] == 1
    assert again["changed"] == 0
    piece = c2_key(RAW, "p1")
    engine = _engine(fixture_db, write=False)
    with engine.connect() as conn:
        part0 = conn.execute(text("SELECT building_key FROM rent_transactions WHERE id = 1")).scalar()
        part1 = conn.execute(text("SELECT building_key FROM rent_transactions WHERE id = 2")).scalar()
        kept = conn.execute(text(
            "SELECT reason FROM rent_building_key_map WHERE reason = 'split'"
        )).scalar()
        added = conn.execute(text(
            "SELECT new_key FROM rent_building_key_map WHERE reason = 'c2_split'"
        )).scalar()
        gone = conn.execute(text("SELECT count(*) FROM rent_building_geocodes")).scalar()
        saved = conn.execute(text(
            "SELECT count(*) FROM rent_building_geocodes_rc2_before WHERE building_key = :k"
        ), {"k": BASE}).scalar()
    engine.dispose()
    assert part0 == BASE
    assert part1 == piece
    assert kept == "split"
    assert added == piece
    assert int(gone) == 0
    assert int(saved) == 1


def test_rerun_with_no_valid_part0_changes_nothing(fixture_db):
    engine = _reset(fixture_db)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE rent_transactions (
                id bigint PRIMARY KEY,
                building_key text,
                asset_type text,
                beopjungri_code text,
                lot_number text,
                is_valid boolean NOT NULL
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
                (1, :k, 'apartment', '1111010100', '10', false),
                (2, :k, 'apartment', '1111010100', '11', true);
            INSERT INTO rent_building_geocodes VALUES (:k, '옛', '주소', 'ok');
            INSERT INTO rent_building_key_c2_units VALUES
                (:k, 'apartment', '1111010100', '10', 0, 'split', '', 'rent_c2_20261119', :sha),
                (:k, 'apartment', '1111010100', '11', 1, 'split', '', 'rent_c2_20261119', :sha);
            """
        ), {"k": BASE, "sha": SHA})
    with pytest.raises(mig.MigrateError):
        mig.apply(engine, raw_of={})
    first = mig.apply(engine, raw_of={(BASE, "apartment"): RAW})
    again = mig.apply(engine, raw_of={})
    engine.dispose()
    assert first["updated"] == 1
    assert again["changed"] == 0
    engine = _engine(fixture_db, write=False)
    with engine.connect() as conn:
        valid_part0 = conn.execute(text(
            "SELECT count(*) FROM rent_transactions WHERE id = 1 AND is_valid"
        )).scalar()
        part1 = conn.execute(text("SELECT building_key FROM rent_transactions WHERE id = 2")).scalar()
    engine.dispose()
    assert int(valid_part0) == 0
    assert part1 == c2_key(RAW, "p1")


def test_resume_after_partial_matches_one_shot(fixture_db):
    raw = "apartment|서울|강남|역삼|name:한빛"
    base = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    piece = c2_key(raw, "p1")

    def build(engine):
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
                    lot_number text,
                    is_valid boolean NOT NULL,
                    addr1 text,
                    addr2 text,
                    addr3 text,
                    addr4 text,
                    building_name text,
                    road_name text
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
                    (2, :k, 'apartment', '1111010100', '11', true, '서울', '강남', '역삼', '', '한빛', ''),
                    (3, :k, 'apartment', '1111010100', '11', true, '서울', '강남', '역삼', '', '한빛', '');
                INSERT INTO rent_building_geocodes VALUES (:k, '옛', '주소', 'ok');
                INSERT INTO rent_building_key_c2_units VALUES
                    (:k, 'apartment', '1111010100', '10', 0, 'split', '', 'rent_c2_20261119', :sha),
                    (:k, 'apartment', '1111010100', '11', 1, 'split', '', 'rent_c2_20261119', :sha);
                """
            ), {"k": base, "sha": SHA})

    def snapshot(engine):
        with engine.connect() as conn:
            txs = conn.execute(text(
                "SELECT id, building_key FROM rent_transactions ORDER BY id"
            )).all()
            mapped = conn.execute(text(
                """
                SELECT old_key, new_key, split_part FROM rent_building_key_map
                WHERE reason = 'c2_split' ORDER BY split_part, new_key
                """
            )).all()
            geo = int(conn.execute(text("SELECT count(*) FROM rent_building_geocodes")).scalar() or 0)
            saved = int(conn.execute(text(
                "SELECT count(*) FROM rent_building_geocodes_rc2_before"
            )).scalar() or 0)
        return [(int(i), str(k)) for i, k in txs], [(str(a), str(b), int(c)) for a, b, c in mapped], geo, saved

    engine = _engine(fixture_db, write=True)
    build(engine)
    mig.apply(engine, raw_of={(base, "apartment"): raw})
    once = snapshot(engine)
    engine.dispose()

    engine = _engine(fixture_db, write=True)
    build(engine)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE rent_transactions_rc2_before (
                id bigint PRIMARY KEY,
                building_key text,
                saved_at timestamptz NOT NULL DEFAULT now()
            );
            INSERT INTO rent_transactions_rc2_before (id, building_key) VALUES
                (2, :k), (3, :k);
            UPDATE rent_transactions SET building_key = :piece WHERE id = 2;
            CREATE TABLE rent_building_geocodes_rc2_before (LIKE rent_building_geocodes);
            INSERT INTO rent_building_geocodes_rc2_before
            SELECT * FROM rent_building_geocodes;
            DELETE FROM rent_building_geocodes;
            """
        ), {"k": base, "piece": piece})
    mig.apply(engine, raw_of={})
    resumed = snapshot(engine)
    engine.dispose()
    assert once == resumed
    assert once[0] == [(2, piece), (3, piece)]


def test_remote_fixture_write_is_refused():
    with pytest.raises(mig.GuardError):
        mig.rent_engine("ch2rent_c2m_p2r", write=True, base_url="postgresql://u@203.0.113.9/unused")
