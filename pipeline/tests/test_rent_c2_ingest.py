"""월간 임대 적재가 판정표와 pending을 같은 트랜잭션에 남기는지. fixture만 쓴다."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.collective.building_keys import apply_rent_c2_assignment, c2_key  # noqa: E402
from pipeline.rent import import_molit as molit  # noqa: E402

FIXTURE = "ch2rent_c2i_p2r"
BASE = "b" * 64
RAW = "apartment|서울|강남|역삼|name:한빛"
UNITS = {
    (BASE, "1111010100", "10"): (0, "split"),
    (BASE, "1111010100", "11"): (1, "split"),
}


def _base_url():
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
    target = url.set(database=FIXTURE)
    ready = create_engine(
        target, pool_pre_ping=True,
        connect_args={"options": "-c default_transaction_read_only=off"},
    )
    with ready.begin() as conn:
        _schema(conn)
    ready.dispose()
    yield url
    with admin.connect() as conn:
        conn.execute(text("SET default_transaction_read_only = off"))
        conn.execute(text(f'DROP DATABASE IF EXISTS "{FIXTURE}" WITH (FORCE)'))
    admin.dispose()


def _engine(url, *, write: bool):
    mode = "off" if write else "on"
    return create_engine(
        url.set(database=FIXTURE),
        pool_pre_ping=True,
        connect_args={"options": f"-c default_transaction_read_only={mode}"},
    )


def _schema(conn) -> None:
    conn.execute(text(
        """
        CREATE TABLE rent_transactions (
            id bigserial PRIMARY KEY,
            transaction_hash char(64) NOT NULL UNIQUE,
            asset_type varchar(20) NOT NULL,
            molit_lease_kind varchar(20),
            building_key char(64),
            display_name varchar(120),
            building_name varchar(120),
            housing_subtype varchar(40),
            addr1 varchar(30),
            addr2 varchar(30),
            addr3 varchar(30),
            addr4 varchar(30),
            addr5 varchar(30),
            lot_number varchar(64),
            lot_bun varchar(20),
            lot_ji varchar(20),
            road_name varchar(120),
            road_width_label varchar(40),
            sido_code char(2),
            sigungu_code char(5),
            eupmyeondong_code char(8),
            beopjungri_code char(10),
            contract_year smallint,
            contract_month smallint,
            contract_date date,
            building_year smallint,
            building_age numeric(8, 1),
            exclusive_area numeric(14, 4),
            contract_area numeric(14, 4),
            floor numeric(8, 1),
            deposit_manwon numeric(14, 2),
            monthly_rent_manwon numeric(14, 2),
            deposit_per_m2 numeric(14, 4),
            monthly_per_m2 numeric(14, 4),
            prev_deposit_manwon numeric(14, 2),
            prev_monthly_rent_manwon numeric(14, 2),
            lease_term_raw varchar(40),
            contract_class_raw varchar(40),
            renewal_right_raw varchar(40),
            source_path varchar(260),
            is_valid boolean NOT NULL DEFAULT true,
            needs_review boolean NOT NULL DEFAULT false,
            mapping_notes text
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
            note text,
            PRIMARY KEY (base_key, asset_type, beopjungri_code, main_lot)
        );
        CREATE TABLE collective_transactions (
            building_key char(64),
            asset_type varchar(20),
            beopjungri_code char(10),
            lot_number varchar(64),
            is_valid boolean
        );
        CREATE TABLE collective_building_key_map (
            old_key varchar(64),
            new_key varchar(64),
            asset_type varchar(32),
            reason varchar(32),
            split_part int
        );
        """
    ))


def _frame(lots: list[str], hashes: list[str]) -> pd.DataFrame:
    rows = []
    for lot, digest in zip(lots, hashes):
        row = {col: None for col in molit.INSERT_COLS}
        row.update({
            "transaction_hash": digest,
            "asset_type": "apartment",
            "building_key": BASE,
            "beopjungri_code": "1111010100",
            "lot_number": lot,
            "is_valid": True,
            "needs_review": False,
        })
        rows.append(row)
    return pd.DataFrame(rows)


def test_remote_ingest_is_refused():
    engine = create_engine("postgresql+psycopg2://u@203.0.113.9/ch2rent_c2i_p2r")
    with pytest.raises(molit.IngestGuard):
        molit.ingest_asset(
            "apartment", root=REPO, engine=engine, land_engine=engine,
            region_maps={}, read_collective=False,
        )
    engine.dispose()


def test_split_lot_pending_only_for_new_rows_and_rerun_is_zero(fixture_db):
    engine = _engine(fixture_db, write=True)
    with engine.begin() as conn:
        conn.execute(text(
            """
            INSERT INTO rent_building_key_c2_units
                (base_key, asset_type, beopjungri_code, main_lot, part, decision,
                 evidence, source, collective_sha256)
            VALUES
                (:base, 'apartment', '1111010100', '10', 0, 'split', '', 'test', :sha),
                (:base, 'apartment', '1111010100', '11', 1, 'split', '', 'test', :sha)
            """
        ), {"base": BASE, "sha": "a" * 64})
    df = _frame(["11", "12"], ["a" * 64, "b" * 64])
    assigned = apply_rent_c2_assignment(df, "apartment", units=UNITS, raw_of={BASE: RAW})
    assert assigned["building_key"].tolist() == [c2_key(RAW, "p1"), BASE]
    first = molit.commit_rent_batch(engine, assigned, assigned.attrs["rent_c2_pending"])
    assert first == {"inserted": 2, "pending": 1}
    with engine.connect() as conn:
        keys = [str(row[0]).strip() for row in conn.execute(text(
            "SELECT building_key FROM rent_transactions ORDER BY transaction_hash"
        ))]
        pending = conn.execute(text(
            "SELECT count(*) FROM rent_building_key_c2_units WHERE decision = 'pending'"
        )).scalar()
    assert keys == [c2_key(RAW, "p1"), BASE]
    assert pending == 1
    second = molit.commit_rent_batch(engine, assigned, assigned.attrs["rent_c2_pending"])
    assert second == {"inserted": 0, "pending": 0}
    with engine.connect() as conn:
        pending = conn.execute(text(
            "SELECT count(*) FROM rent_building_key_c2_units WHERE decision = 'pending'"
        )).scalar()
        loaded = molit.load_rent_c2_units_for(conn, "apartment")
    engine.dispose()
    assert pending == 1
    assert loaded[(BASE, "1111010100", "12")][1] == "pending"


def test_writable_collective_reader_is_refused(fixture_db):
    engine = _engine(fixture_db, write=True)
    with engine.connect() as conn:
        with pytest.raises(molit.IngestGuard):
            molit.collective_unique_parts(conn, "apartment", [BASE])
    engine.dispose()


def test_unique_collective_part_is_read_only(fixture_db):
    write = _engine(fixture_db, write=True)
    piece = c2_key(RAW, "p2")
    with write.begin() as conn:
        conn.execute(text(
            """
            INSERT INTO collective_building_key_map
                (old_key, new_key, asset_type, reason, split_part)
            VALUES (:base, :piece, 'apartment', 'c2_split', 2);
            INSERT INTO collective_transactions
                (building_key, asset_type, beopjungri_code, lot_number, is_valid)
            VALUES (:piece, 'apartment', '1111010100', '13', true);
            """
        ), {"base": BASE, "piece": piece})
    write.dispose()
    reader = _engine(fixture_db, write=False)
    with reader.connect() as conn:
        found = molit.collective_unique_parts(conn, "apartment", [BASE])
    reader.dispose()
    assert found == {(BASE, "1111010100", "13"): 2}


def test_month_filter_keeps_only_the_requested_month():
    df = pd.DataFrame({
        "contract_year": [2026, 2026, 2025],
        "contract_month": [10, 9, 10],
        "transaction_hash": ["a", "b", "c"],
    })
    picked = molit._limit_month(df, (2026, 10))
    assert picked["transaction_hash"].tolist() == ["a"]
    assert len(molit._limit_month(df, None)) == 3
