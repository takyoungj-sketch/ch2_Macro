"""임대 C-2 키 이전. rent fixture 만 쓰고 집합 엔진은 열지 않는다."""
from __future__ import annotations

import json
import re

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from pipeline.collective.building_keys import c2_key, main_lot_of
from pipeline.collective.migrate_p2_keys import server_url_from_env

FIXTURE_RE = re.compile(r"^ch2rent_c2m_p2r(_[a-z0-9]+)?$")
FORBIDDEN = {
    "rent_stats",
    "rent_stats_rc2r",
    "collective_stats",
    "built_stats",
    "land_stats",
    "macro_ts",
    "platform",
    "postgres",
    "parcel_master",
}


class GuardError(RuntimeError):
    pass


class MigrateError(RuntimeError):
    pass


def assert_fixture(name: str) -> None:
    if name in FORBIDDEN or FIXTURE_RE.fullmatch(name) is None:
        raise GuardError("이 실행기는 테스트 fixture 데이터베이스만 연다")


def rent_engine(dbname: str, *, write: bool, base_url: str | None = None) -> Engine:
    url = make_url(base_url or server_url_from_env()).set(database=dbname)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    mode = "off" if write else "on"
    opts = f"-c statement_timeout=0 -c default_transaction_read_only={mode}"
    return create_engine(url, pool_pre_ping=True, connect_args={"options": opts})


def _exists(conn, table: str) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar())


def _piece(base: str, asset: str, part: int, raw_of: dict[tuple[str, str], str]) -> str:
    if part == 0:
        return base
    raw = raw_of.get((base, asset))
    if not raw:
        raise MigrateError("분할 조각의 원문이 없다")
    return c2_key(raw, f"p{part}")


def apply(engine: Engine, *, raw_of: dict[tuple[str, str], str] | None = None) -> dict:
    raw_of = raw_of or {}
    with engine.begin() as conn:
        name = str(conn.execute(text("SELECT current_database()")).scalar() or "")
        assert_fixture(name)
        if not _exists(conn, "rent_building_key_c2_units"):
            return {"changed": 0, "updated": 0, "geocode_dropped": 0, "mapped": 0}
        units = conn.execute(text(
            """
            SELECT base_key, asset_type, beopjungri_code, main_lot, part, decision
            FROM rent_building_key_c2_units
            WHERE decision = 'split'
            """
        )).mappings().all()
        old_keys = sorted({str(r["base_key"]) for r in units})
        moves: list[dict] = []
        for row in units:
            part = int(row["part"])
            if part == 0:
                continue
            new_key = _piece(str(row["base_key"]), str(row["asset_type"]), part, raw_of)
            moves.append({
                "base": str(row["base_key"]),
                "asset": str(row["asset_type"]),
                "bjd": str(row["beopjungri_code"])[:10],
                "lot": main_lot_of(row["main_lot"]) or "",
                "part": part,
                "new": new_key,
            })
        dropped = 0
        if old_keys and _exists(conn, "rent_building_geocodes"):
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS rent_building_geocodes_rc2_before
                (LIKE rent_building_geocodes)
                """
            ))
            conn.execute(text(
                """
                INSERT INTO rent_building_geocodes_rc2_before
                SELECT * FROM rent_building_geocodes WHERE building_key = ANY(:k)
                """
            ), {"k": old_keys})
            dropped = int(conn.execute(text(
                "DELETE FROM rent_building_geocodes WHERE building_key = ANY(:k)"
            ), {"k": old_keys}).rowcount or 0)
        updated = 0
        if moves:
            frame = pd.DataFrame(moves)
            conn.execute(text(
                "CREATE TEMP TABLE _rc2_move (base text, asset text, bjd text, lot text, part int, new text) ON COMMIT DROP"
            ))
            conn.execute(
                text("INSERT INTO _rc2_move VALUES (:base, :asset, :bjd, :lot, :part, :new)"),
                frame.to_dict("records"),
            )
        if moves and _exists(conn, "rent_transactions"):
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS rent_transactions_rc2_before (
                    id bigint PRIMARY KEY,
                    building_key text,
                    saved_at timestamptz NOT NULL DEFAULT now()
                )
                """
            ))
            conn.execute(text(
                """
                INSERT INTO rent_transactions_rc2_before (id, building_key)
                SELECT t.id, t.building_key
                FROM rent_transactions t
                JOIN _rc2_move m
                  ON t.building_key = m.base
                 AND t.asset_type = m.asset
                 AND left(t.beopjungri_code, 10) = m.bjd
                 AND CASE WHEN split_part(btrim(t.lot_number), '-', 1) ~ '^[0-9]+$'
                          THEN coalesce(nullif(ltrim(split_part(btrim(t.lot_number), '-', 1), '0'), ''), '0')
                          ELSE btrim(split_part(btrim(t.lot_number), '-', 1)) END = m.lot
                ON CONFLICT (id) DO NOTHING
                """
            ))
            updated = int(conn.execute(text(
                """
                UPDATE rent_transactions t
                SET building_key = m.new
                FROM _rc2_move m
                WHERE t.building_key = m.base
                  AND t.asset_type = m.asset
                  AND left(t.beopjungri_code, 10) = m.bjd
                  AND CASE WHEN split_part(btrim(t.lot_number), '-', 1) ~ '^[0-9]+$'
                           THEN coalesce(nullif(ltrim(split_part(btrim(t.lot_number), '-', 1), '0'), ''), '0')
                           ELSE btrim(split_part(btrim(t.lot_number), '-', 1)) END = m.lot
                  AND t.building_key IS DISTINCT FROM m.new
                """
            )).rowcount or 0)
        mapped = 0
        if moves and _exists(conn, "rent_building_key_map"):
            result = conn.execute(text(
                """
                INSERT INTO rent_building_key_map
                    (old_key, new_key, asset_type, reason, split_part, n_tx)
                SELECT base, new, asset, 'c2_split', part, 0
                FROM _rc2_move
                ON CONFLICT DO NOTHING
                """
            ))
            mapped = int(result.rowcount or 0)
        changed = dropped + updated + mapped
        if _exists(conn, "rent_c2_migration_log"):
            conn.execute(text(
                "INSERT INTO rent_c2_migration_log (step, detail) VALUES ('rent_c2_migrate', CAST(:d AS jsonb))"
            ), {"d": json.dumps({"changed": changed, "updated": updated, "geocode_dropped": dropped, "mapped": mapped})})
        return {"changed": changed, "updated": updated, "geocode_dropped": dropped, "mapped": mapped}
