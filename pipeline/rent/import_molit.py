#!/usr/bin/env python3
"""
임대시장/A.주거용 CSV → rent_stats.rent_transactions

전환율·환산금액 없음. 재실행 시 transaction_hash ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from collective.building_keys import (  # noqa: E402
    apply_building_key_split,
    apply_rent_c2_assignment,
    attach_building_identity,
    derive_display_name,
)
from region_mapping import attach_beopjungri_codes, clean_code_columns  # noqa: E402
from rent.db_utils import get_land_engine_for_region_copy, get_rent_engine  # noqa: E402
from rent.molit_schemas import ASSET_DIRS, FILE_LABEL, RentAssetType  # noqa: E402
from rent.parse import read_rent_csv, refine_rent_dataframe  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DDL = REPO / "db" / "055_rent_transactions.sql"
RAW_ROOT = REPO / "임대시장" / "A.주거용"

INSERT_COLS = (
    "transaction_hash",
    "asset_type",
    "molit_lease_kind",
    "building_key",
    "display_name",
    "building_name",
    "housing_subtype",
    "addr1",
    "addr2",
    "addr3",
    "addr4",
    "addr5",
    "lot_number",
    "lot_bun",
    "lot_ji",
    "road_name",
    "road_width_label",
    "sido_code",
    "sigungu_code",
    "eupmyeondong_code",
    "beopjungri_code",
    "contract_year",
    "contract_month",
    "contract_date",
    "building_year",
    "building_age",
    "exclusive_area",
    "contract_area",
    "floor",
    "deposit_manwon",
    "monthly_rent_manwon",
    "deposit_per_m2",
    "monthly_per_m2",
    "prev_deposit_manwon",
    "prev_monthly_rent_manwon",
    "lease_term_raw",
    "contract_class_raw",
    "renewal_right_raw",
    "source_path",
    "is_valid",
    "needs_review",
    "mapping_notes",
)

INSERT_SQL = f"""
INSERT INTO rent_transactions ({", ".join(INSERT_COLS)})
VALUES %s
ON CONFLICT (transaction_hash) DO NOTHING
"""


def _null_if_nan(val):
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, str) and val.strip().lower() in ("", "nan", "none"):
        return None
    return val


def _int_or_none(val):
    val = _null_if_nan(val)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _float_or_none(val):
    val = _null_if_nan(val)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def ensure_database_and_ddl(admin_url: str, dbname: str) -> None:
    from sqlalchemy import create_engine

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"),
            {"n": dbname},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{dbname}"'))
            log.info("created database %s", dbname)
        else:
            log.info("database %s already exists", dbname)
    eng = get_rent_engine()
    sql = DDL.read_text(encoding="utf-8")
    with eng.begin() as conn:
        conn.execute(text(sql))
    log.info("applied %s", DDL.name)


def sync_region_codes_from_land(rent_engine, land_engine, *, force: bool = False) -> None:
    with rent_engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM region_codes")).scalar()
    if n and int(n) > 0 and not force:
        log.info("region_codes already %s rows", n)
        return
    with land_engine.connect() as src, rent_engine.begin() as dst:
        rows = src.execute(text("SELECT * FROM region_codes")).mappings().all()
        if not rows:
            raise SystemExit("land_stats.region_codes empty")
        if force:
            dst.execute(text("TRUNCATE region_codes RESTART IDENTITY CASCADE"))
        for row in rows:
            dst.execute(
                text(
                    """
                    INSERT INTO region_codes (
                        sido_code, sido_name, sigungu_code, sigungu_name,
                        eupmyeondong_code, eupmyeondong_name,
                        beopjungri_code, beopjungri_name, is_active, updated_at
                    ) VALUES (
                        :sido_code, :sido_name, :sigungu_code, :sigungu_name,
                        :eupmyeondong_code, :eupmyeondong_name,
                        :beopjungri_code, :beopjungri_name, :is_active, :updated_at
                    )
                    ON CONFLICT (beopjungri_code) DO UPDATE SET
                        sido_name = EXCLUDED.sido_name,
                        sigungu_name = EXCLUDED.sigungu_name,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                dict(row),
            )
    log.info("region_codes synced: %s rows", len(rows))


def find_csvs(root: Path, asset_type: RentAssetType) -> list[Path]:
    prefix = ASSET_DIRS[asset_type]
    folders = [p for p in root.iterdir() if p.is_dir() and p.name.startswith(prefix)]
    if not folders:
        log.warning("missing folder prefix %s under %s", prefix, root)
        return []
    token = f"_{FILE_LABEL[asset_type]}_전월세_"
    out: list[Path] = []
    for folder in folders:
        out.extend(p for p in folder.glob("*.csv") if token in p.name)
    return sorted(set(out))


def _prepare(
    df: pd.DataFrame,
    asset_type: RentAssetType,
    land_engine,
    region_maps: dict,
    rent_units: dict | None = None,
    collective_unique: dict | None = None,
) -> pd.DataFrame:
    if asset_type == "detached":
        a3 = df.get("addr3", pd.Series("", index=df.index)).fillna("").astype(str)
        lot = df.get("lot_number", pd.Series("", index=df.index)).fillna("").astype(str)
        road = df.get("road_name", pd.Series("", index=df.index)).fillna("").astype(str)
        addr3_lot = (a3 + " " + lot).str.strip()
        df = df.copy()
        df["building_key"] = None
        df["display_name"] = addr3_lot.where(addr3_lot != "", road).replace("", "(주소 미상)")
    else:
        df = attach_building_identity(df, asset_type)
    df = attach_beopjungri_codes(df, land_engine, region_maps=region_maps)
    df = clean_code_columns(df)
    if asset_type != "detached":
        df = apply_building_key_split(df, asset_type)
        df = apply_rent_c2_assignment(
            df,
            asset_type,
            units=rent_units,
            collective_unique=collective_unique,
        )
    return df


APPROVED_COLLECTIVE_SHA = "372e114bf7c664ca5489660596adc7969f04302d6d0a68b1f7f84ee0aabe62e5"
_LOT_NORM = (
    "CASE WHEN split_part(btrim(lot_number), '-', 1) ~ '^[0-9]+$' "
    "THEN coalesce(nullif(ltrim(split_part(btrim(lot_number), '-', 1), '0'), ''), '0') "
    "ELSE btrim(split_part(btrim(lot_number), '-', 1)) END"
)


class IngestGuard(RuntimeError):
    pass


def assert_rent_write_local(engine) -> None:
    ops = str(REPO / "scripts" / "ops" / "collective_p2_verify")
    if ops not in sys.path:
        sys.path.insert(0, ops)
    from ops_guards import TargetError, assert_local_target

    try:
        assert_local_target(engine)
    except TargetError as exc:
        raise IngestGuard(str(exc)) from None


def load_rent_c2_units_for(conn, asset_type: str) -> dict | None:
    """판정 표가 없거나 이 유형의 행이 없으면 None. 있으면 (base, 법정동, 본번) → (part, decision)."""
    if not conn.execute(text("SELECT to_regclass('public.rent_building_key_c2_units')")).scalar():
        return None
    rows = conn.execute(
        text(
            """
            SELECT rtrim(base_key), left(beopjungri_code, 10), btrim(main_lot), part, decision
            FROM rent_building_key_c2_units
            WHERE asset_type = :asset
            """
        ),
        {"asset": asset_type},
    ).all()
    if not rows:
        return None
    return {
        (str(base).strip(), str(code).strip(), str(lot).strip()): (int(part), str(decision))
        for base, code, lot, part, decision in rows
    }


def split_bases_of(units: dict) -> list[str]:
    return sorted({base for (base, _code, _lot), (_part, decision) in units.items() if decision == "split"})


def collective_unique_parts(conn, asset_type: str, base_keys: list[str]) -> dict:
    """집합 원장에서 본번이 한 조각에만 있는 (base, 법정동, 본번) → part. SELECT 만 실행한다."""
    mode = str(conn.execute(text("SHOW default_transaction_read_only")).scalar() or "").lower()
    if mode not in {"on", "true", "1"}:
        raise IngestGuard("집합 데이터베이스는 읽기 전용이어야 한다")
    if not base_keys:
        return {}
    has_tx = conn.execute(text("SELECT to_regclass('public.collective_transactions')")).scalar()
    has_map = conn.execute(text("SELECT to_regclass('public.collective_building_key_map')")).scalar()
    if not has_tx:
        return {}
    mapped: dict[str, set[tuple[str, int]]] = {key: {(key, 0)} for key in base_keys}
    if has_map:
        rows = conn.execute(
            text(
                """
                SELECT rtrim(old_key), rtrim(new_key), split_part
                FROM collective_building_key_map
                WHERE reason = 'c2_split' AND asset_type = :asset
                  AND rtrim(old_key) = ANY(CAST(:keys AS text[]))
                """
            ),
            {"asset": asset_type, "keys": base_keys},
        ).all()
        for old, new, part in rows:
            mapped.setdefault(str(new).strip(), set()).add((str(old).strip(), int(part or 0)))
    resolved = {key: next(iter(pairs)) for key, pairs in mapped.items() if len(pairs) == 1}
    if not resolved:
        return {}
    tx_rows = conn.execute(
        text(
            f"""
            SELECT rtrim(building_key), left(beopjungri_code, 10), {_LOT_NORM} AS lot
            FROM collective_transactions
            WHERE is_valid AND asset_type = :asset
              AND rtrim(building_key) = ANY(CAST(:keys AS text[]))
              AND beopjungri_code IS NOT NULL
              AND coalesce(btrim(lot_number), '') <> ''
            """
        ),
        {"asset": asset_type, "keys": list(resolved)},
    ).all()
    found: dict[tuple[str, str, str], set[int]] = {}
    for key, code, lot in tx_rows:
        base, part = resolved[str(key).strip()]
        slot = (base, str(code or "").strip(), str(lot or "").strip())
        found.setdefault(slot, set()).add(part)
    return {slot: next(iter(parts)) for slot, parts in found.items() if len(parts) == 1}


def pending_for_inserted(df: pd.DataFrame, pending: list[dict], inserted: set[str]) -> list[dict]:
    """새로 들어간 거래의 본번만 pending 후보로 남긴다. 중복으로 빠진 거래는 만들지 않는다."""
    if not pending or not inserted:
        return []
    from collective.building_keys import main_lot_of

    wanted = {(p["base_key"], p["beopjungri_code"], p["main_lot"]) for p in pending}
    hit: set[tuple] = set()
    for row in df.itertuples(index=False):
        digest = str(getattr(row, "transaction_hash", "") or "").strip()
        if digest not in inserted:
            continue
        slot = (
            str(getattr(row, "building_key", "") or "").strip(),
            str(getattr(row, "beopjungri_code", "") or "").strip()[:10],
            main_lot_of(getattr(row, "lot_number", "")),
        )
        if slot in wanted:
            hit.add(slot)
    return [p for p in pending if (p["base_key"], p["beopjungri_code"], p["main_lot"]) in hit]


def _insert_returning(cur, records: list[tuple]) -> set[str]:
    inserted: set[str] = set()
    page = 2000
    sql = INSERT_SQL + " RETURNING transaction_hash"
    for start in range(0, len(records), page):
        chunk = records[start : start + page]
        got = execute_values(cur, sql, chunk, page_size=len(chunk), fetch=True)
        inserted.update(str(row[0]).strip() for row in got)
    return inserted


def commit_rent_batch(engine, df: pd.DataFrame, pending: list[dict]) -> dict:
    """거래 삽입과 pending 등록을 한 트랜잭션에서 끝낸다. pending 은 실제 삽입된 거래만."""
    assert_rent_write_local(engine)
    records = _records(df)
    chosen_pending = pending
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        inserted = _insert_returning(cur, records) if records else set()
        chosen = pending_for_inserted(df, chosen_pending, inserted)
        if chosen:
            bases = sorted({row["base_key"] for row in chosen})
            for base in bases:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    ("ch2:c2:" + base,),
                )
            payload = [
                (
                    row["base_key"],
                    row["asset_type"],
                    row["beopjungri_code"],
                    row["main_lot"],
                    0,
                    "pending",
                    "",
                    "auto_ingest",
                    APPROVED_COLLECTIVE_SHA,
                    "월간 적재 자동 등록 — 판정 검토 대상",
                )
                for row in chosen
            ]
            execute_values(
                cur,
                """
                INSERT INTO rent_building_key_c2_units
                    (base_key, asset_type, beopjungri_code, main_lot, part, decision,
                     evidence, source, collective_sha256, note)
                VALUES %s
                ON CONFLICT (base_key, asset_type, beopjungri_code, main_lot) DO NOTHING
                """,
                payload,
                page_size=len(payload),
            )
        raw.commit()
        cur.close()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    return {"inserted": len(inserted) if records else 0, "pending": len(chosen) if records else 0}


def _records(df: pd.DataFrame) -> list[tuple]:
    rows: list[tuple] = []
    for row in df.itertuples(index=False):
        rec = {
            "transaction_hash": row.transaction_hash,
            "asset_type": row.asset_type,
            "molit_lease_kind": _null_if_nan(getattr(row, "molit_lease_kind", None)),
            "building_key": _null_if_nan(getattr(row, "building_key", None)),
            "display_name": _null_if_nan(getattr(row, "display_name", None)),
            "building_name": _null_if_nan(getattr(row, "building_name", None)),
            "housing_subtype": _null_if_nan(getattr(row, "housing_subtype", None)),
            "addr1": _null_if_nan(getattr(row, "addr1", None)),
            "addr2": _null_if_nan(getattr(row, "addr2", None)),
            "addr3": _null_if_nan(getattr(row, "addr3", None)),
            "addr4": _null_if_nan(getattr(row, "addr4", None)),
            "addr5": _null_if_nan(getattr(row, "addr5", None)),
            "lot_number": _null_if_nan(getattr(row, "lot_number", None)),
            "lot_bun": _null_if_nan(getattr(row, "lot_bun", None)),
            "lot_ji": _null_if_nan(getattr(row, "lot_ji", None)),
            "road_name": _null_if_nan(getattr(row, "road_name", None)),
            "road_width_label": _null_if_nan(getattr(row, "road_width_label", None)),
            "sido_code": _null_if_nan(getattr(row, "sido_code", None)),
            "sigungu_code": _null_if_nan(getattr(row, "sigungu_code", None)),
            "eupmyeondong_code": _null_if_nan(getattr(row, "eupmyeondong_code", None)),
            "beopjungri_code": _null_if_nan(getattr(row, "beopjungri_code", None)),
            "contract_year": _int_or_none(getattr(row, "contract_year", None)),
            "contract_month": _int_or_none(getattr(row, "contract_month", None)),
            "contract_date": getattr(row, "contract_date", None),
            "building_year": _int_or_none(getattr(row, "building_year", None)),
            "building_age": _float_or_none(getattr(row, "building_age", None)),
            "exclusive_area": _float_or_none(getattr(row, "exclusive_area", None)),
            "contract_area": _float_or_none(getattr(row, "contract_area", None)),
            "floor": _float_or_none(getattr(row, "floor", None)),
            "deposit_manwon": _float_or_none(getattr(row, "deposit_manwon", None)),
            "monthly_rent_manwon": _float_or_none(getattr(row, "monthly_rent_manwon", None)),
            "deposit_per_m2": _float_or_none(getattr(row, "deposit_per_m2", None)),
            "monthly_per_m2": _float_or_none(getattr(row, "monthly_per_m2", None)),
            "prev_deposit_manwon": _float_or_none(getattr(row, "prev_deposit_manwon", None)),
            "prev_monthly_rent_manwon": _float_or_none(getattr(row, "prev_monthly_rent_manwon", None)),
            "lease_term_raw": _null_if_nan(getattr(row, "lease_term_raw", None)),
            "contract_class_raw": _null_if_nan(getattr(row, "contract_class_raw", None)),
            "renewal_right_raw": _null_if_nan(getattr(row, "renewal_right_raw", None)),
            "source_path": _null_if_nan(getattr(row, "source_path", None)),
            "is_valid": True,
            "needs_review": bool(getattr(row, "needs_review", False)),
            "mapping_notes": _null_if_nan(getattr(row, "mapping_notes", None)),
        }
        if rec["display_name"] is None:
            rec["display_name"] = derive_display_name(
                building_name=rec["building_name"],
                addr3=rec["addr3"],
                lot_number=rec["lot_number"],
                road_name=rec["road_name"],
            )
        rows.append(tuple(rec[c] for c in INSERT_COLS))
    return rows


def _insert(engine, records: list[tuple]) -> None:
    if not records:
        return
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        execute_values(cur, INSERT_SQL, records, page_size=2000)
        raw.commit()
        cur.close()
    finally:
        raw.close()


def _limit_month(df: pd.DataFrame, year_month: tuple[int, int] | None) -> pd.DataFrame:
    if year_month is None or df.empty:
        return df
    year, month = year_month
    if "contract_year" not in df.columns or "contract_month" not in df.columns:
        return df.iloc[0:0].copy()
    picked = df[(df["contract_year"] == year) & (df["contract_month"] == month)]
    return picked.copy()


def source_label(path: Path) -> str:
    """원장 source_path. 저장소 안이면 상대 경로, 밖이면 받은 경로."""
    try:
        return str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def ingest_asset(
    asset_type: RentAssetType,
    *,
    root: Path,
    engine,
    land_engine,
    region_maps: dict,
    limit_files: int | None = None,
    collective_engine=None,
    read_collective: bool = True,
    year_month: tuple[int, int] | None = None,
    before_commit=None,
) -> int:
    assert_rent_write_local(engine)
    owned = None
    reader = collective_engine
    if read_collective and reader is None:
        owned = _read_only_collective_engine()
        reader = owned
    paths = find_csvs(root, asset_type)
    if limit_files:
        paths = paths[:limit_files]
    log.info("%s files=%d", asset_type, len(paths))
    total = 0
    try:
        with engine.connect() as conn:
            units = load_rent_c2_units_for(conn, asset_type)
        unique = None
        if units and reader is not None:
            with reader.connect() as conn:
                unique = collective_unique_parts(conn, asset_type, split_bases_of(units))
        for path in paths:
            rel = source_label(path)
            log.info("read %s", rel)
            raw_df = read_rent_csv(path)
            df = refine_rent_dataframe(raw_df, asset_type, source_path=rel)
            df = _limit_month(df, year_month)
            if df.empty:
                log.warning("empty after refine %s", path.name)
                continue
            df = _prepare(
                df, asset_type, land_engine, region_maps,
                rent_units=units, collective_unique=unique,
            )
            pending = list(df.attrs.get("rent_c2_pending") or [])
            if before_commit is not None:
                before_commit(df)
            wrote = commit_rent_batch(engine, df, pending)
            total += wrote["inserted"]
            log.info(
                "inserted %s rows=%d pending=%d (cumulative %d)",
                path.name, wrote["inserted"], wrote["pending"], total,
            )
    finally:
        if owned is not None:
            owned.dispose()
    return total


def _read_only_collective_engine():
    from sqlalchemy import create_engine
    from collective.db_utils import get_collective_engine

    src = get_collective_engine()
    url = src.url
    src.dispose()
    assert_rent_write_local(url)
    opts = "-c statement_timeout=0 -c default_transaction_read_only=on"
    return create_engine(url, pool_pre_ping=True, connect_args={"options": opts})


def print_report(engine) -> None:
    sql = """
    SELECT
        asset_type,
        COUNT(*)::bigint AS n,
        COUNT(*) FILTER (WHERE molit_lease_kind = '전세')::bigint AS n_jeonse,
        COUNT(*) FILTER (WHERE molit_lease_kind = '월세')::bigint AS n_wolse,
        COUNT(*) FILTER (WHERE COALESCE(monthly_rent_manwon, 0) = 0)::bigint AS n_monthly_zero,
        COUNT(*) FILTER (WHERE COALESCE(deposit_manwon, 0) > 0 AND COALESCE(monthly_rent_manwon, 0) > 0)::bigint AS n_mixed,
        COUNT(*) FILTER (WHERE deposit_per_m2 IS NOT NULL)::bigint AS n_dep_unit,
        COUNT(*) FILTER (WHERE monthly_per_m2 IS NOT NULL AND COALESCE(monthly_rent_manwon, 0) > 0)::bigint AS n_mon_unit,
        MIN(contract_year) AS y_min,
        MAX(contract_year) AS y_max
    FROM rent_transactions
    GROUP BY asset_type
    ORDER BY asset_type
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).mappings().all()
        total = conn.execute(text("SELECT COUNT(*) FROM rent_transactions")).scalar()
    log.info("rent_transactions total=%s", total)
    for r in rows:
        log.info("report %s", dict(r))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=RAW_ROOT)
    p.add_argument(
        "--assets",
        default="apartment,rowhouse,officetel,detached",
        help="comma list of asset types",
    )
    p.add_argument("--limit-files", type=int, default=None)
    p.add_argument("--skip-create", action="store_true")
    p.add_argument("--admin-url", default="postgresql+psycopg2://postgres:8972@localhost:5432/postgres")
    p.add_argument("--dbname", default="rent_stats")
    args = p.parse_args()

    if not args.skip_create:
        ensure_database_and_ddl(args.admin_url, args.dbname)

    engine = get_rent_engine()
    land = get_land_engine_for_region_copy()
    sync_region_codes_from_land(engine, land)
    from clean import build_region_lookup

    region_maps = build_region_lookup(land)

    assets: list[RentAssetType] = [
        a.strip()  # type: ignore[assignment]
        for a in args.assets.split(",")
        if a.strip()
    ]
    for asset in assets:
        ingest_asset(
            asset,  # type: ignore[arg-type]
            root=args.root,
            engine=engine,
            land_engine=land,
            region_maps=region_maps,
            limit_files=args.limit_files,
        )
    print_report(engine)


if __name__ == "__main__":
    main()
