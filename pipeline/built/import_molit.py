"""
MOLIT raw base CSV → built_transactions 적재 (Phase A).

  raw/raw base/상업업무_2021_2026  (유형=일반)
  raw/raw base/공장창고_2021_2026  (유형=일반)
  raw/raw base/단독다가구_2021_2026
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clean import build_region_lookup
from region_mapping import attach_beopjungri_codes, clean_code_columns, log_mapping_coverage

from built.db_utils import get_built_engine, get_land_engine_for_region_copy
from built.import_refined import (
    _clean_code,
    _null_if_nan,
    _tx_hash,
    copy_region_codes_if_empty,
    sync_region_codes_from_land,
)
from built.molit_schemas import FILE_LABEL, RAW_BASE_DIRS, BuiltAssetType
from built.refine_built import read_molit_csv, refine_molit_dataframe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
RAW_BASE = REPO / "raw" / "raw base"
DDL_015 = REPO / "db" / "015_built_transactions.sql"
DDL_028 = REPO / "db" / "028_built_ledger_rebuild.sql"
DDL_029 = REPO / "db" / "029_built_scope_stats.sql"

BUILT_PATCH_SQL = """
ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS mapping_notes TEXT;
CREATE INDEX IF NOT EXISTS ix_built_tx_beopjungri
    ON built_transactions (beopjungri_code)
    WHERE beopjungri_code IS NOT NULL AND btrim(beopjungri_code::text) <> '';
"""

INSERT_STMT = text(
    """
    INSERT INTO built_transactions (
        transaction_hash, asset_type, deal_form,
        addr1, addr2, addr3, addr4, addr5, lot_number,
        road_name, display_address,
        beopjungri_code, sido_code, sigungu_code, eupmyeondong_code,
        trade_year_label, contract_year, contract_month, contract_date,
        zone_type, building_use, building_scale, land_scale, age_bucket,
        price, gross_area, land_area, building_age,
        road_code, road_width_label, floor, deal_type,
        is_valid, needs_review, mapping_notes
    ) VALUES (
        :transaction_hash, :asset_type, :deal_form,
        :addr1, :addr2, :addr3, :addr4, :addr5, :lot_number,
        :road_name, :display_address,
        :beopjungri_code, :sido_code, :sigungu_code, :eupmyeondong_code,
        :trade_year_label, :contract_year, :contract_month, :contract_date,
        :zone_type, :building_use, :building_scale, :land_scale, :age_bucket,
        :price, :gross_area, :land_area, :building_age,
        :road_code, :road_width_label, :floor, :deal_type,
        :is_valid, :needs_review, :mapping_notes
    )
    ON CONFLICT (transaction_hash) DO NOTHING
    """
)


def ensure_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(DDL_015.read_text(encoding="utf-8")))
        conn.execute(text(BUILT_PATCH_SQL))
        if DDL_028.is_file():
            conn.execute(text(DDL_028.read_text(encoding="utf-8")))
        if DDL_029.is_file():
            conn.execute(text(DDL_029.read_text(encoding="utf-8")))
    parts = ["015 + built patch"]
    if DDL_028.is_file():
        parts.append(DDL_028.name)
    if DDL_029.is_file():
        parts.append(DDL_029.name)
    log.info("schema ready (%s)", " + ".join(parts))


def _json_safe(val):
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if isinstance(val, float) and pd.isna(val):
        return None
    if hasattr(val, "item"):
        try:
            return val.item()
        except Exception:
            pass
    return val


def _row_to_record(row: pd.Series) -> dict:
    rec = {
        "asset_type": row.get("asset_type"),
        "deal_form": "general",
        "addr1": _null_if_nan(row.get("addr1")),
        "addr2": _null_if_nan(row.get("addr2")),
        "addr3": _null_if_nan(row.get("addr3")),
        "addr4": _null_if_nan(row.get("addr4")),
        "addr5": _null_if_nan(row.get("addr5")),
        "lot_number": _null_if_nan(row.get("lot_number")),
        "road_name": _null_if_nan(row.get("road_name")),
        "display_address": _null_if_nan(row.get("display_address")),
        "trade_year_label": _null_if_nan(row.get("trade_year_label")),
        "contract_year": _null_if_nan(row.get("contract_year")),
        "contract_month": _null_if_nan(row.get("contract_month")),
        "contract_date": _null_if_nan(row.get("contract_date")),
        "zone_type": _null_if_nan(row.get("zone_type")),
        "building_use": _null_if_nan(row.get("building_use")),
        "building_scale": _null_if_nan(row.get("building_scale")),
        "land_scale": _null_if_nan(row.get("land_scale")),
        "age_bucket": _null_if_nan(row.get("age_bucket")),
        "price": _null_if_nan(row.get("price")),
        "gross_area": _null_if_nan(row.get("gross_area")),
        "land_area": _null_if_nan(row.get("land_area")),
        "building_age": _null_if_nan(row.get("building_age")),
        "road_code": None,
        "road_width_label": _null_if_nan(row.get("road_width_label")),
        "floor": _null_if_nan(row.get("floor")),
        "deal_type": _null_if_nan(row.get("deal_type")),
        "is_valid": True,
        "beopjungri_code": _null_if_nan(row.get("beopjungri_code")),
        "sido_code": _null_if_nan(row.get("sido_code")),
        "sigungu_code": _null_if_nan(row.get("sigungu_code")),
        "eupmyeondong_code": _null_if_nan(row.get("eupmyeondong_code")),
        "needs_review": bool(row.get("needs_review")),
        "mapping_notes": _null_if_nan(row.get("mapping_notes")),
    }
    for ck in ("beopjungri_code", "sido_code", "sigungu_code", "eupmyeondong_code"):
        w = {"sido_code": 2, "sigungu_code": 5, "eupmyeondong_code": 8, "beopjungri_code": 10}.get(ck)
        rec[ck] = _clean_code(rec.get(ck), w)
    rec["transaction_hash"] = _tx_hash(rec)
    return rec


def insert_dataframe(df: pd.DataFrame, engine) -> tuple[int, int]:
    """Returns (attempted, skipped_by_conflict estimate via batch)."""
    if df.empty:
        return 0, 0
    attempted = 0
    batch: list[dict] = []
    for _, row in df.iterrows():
        batch.append(_row_to_record(row))
        if len(batch) >= 2000:
            with engine.begin() as conn:
                for rec in batch:
                    conn.execute(INSERT_STMT, rec)
            attempted += len(batch)
            batch.clear()
    if batch:
        with engine.begin() as conn:
            for rec in batch:
                conn.execute(INSERT_STMT, rec)
        attempted += len(batch)
    return attempted, 0


def list_csv_files(
    asset_type: BuiltAssetType,
    *,
    year_from: int = 2021,
    year_to: int = 2026,
    sido_prefix: str | None = None,
) -> list[Path]:
    folder = RAW_BASE / RAW_BASE_DIRS[asset_type]
    if not folder.is_dir():
        raise FileNotFoundError(f"raw base folder missing: {folder}")
    label = FILE_LABEL[asset_type]
    paths: list[Path] = []
    for path in sorted(folder.glob("*.csv")):
        if sido_prefix and not path.name.startswith(sido_prefix):
            continue
        for year in range(year_from, year_to + 1):
            if f"_{year}.csv" in path.name or path.name.endswith(f"_{year}.csv"):
                paths.append(path)
                break
    return paths


def ingest_paths(
    paths: list[Path],
    asset_type: BuiltAssetType,
    engine,
    region_maps: dict,
) -> dict:
    frames: list[pd.DataFrame] = []
    raw_rows = 0
    for path in paths:
        log.info("Reading %s", path.name)
        raw = read_molit_csv(path)
        raw_rows += len(raw)
        part = refine_molit_dataframe(raw, asset_type)
        if not part.empty:
            frames.append(part)
    if not frames:
        return {"files": len(paths), "raw_rows": raw_rows, "refined_rows": 0, "insert_attempted": 0}

    df = pd.concat(frames, ignore_index=True)
    refined_rows = len(df)
    df = attach_beopjungri_codes(df, engine, region_maps=region_maps)
    df = clean_code_columns(df)
    attempted, _ = insert_dataframe(df, engine)
    return {
        "files": len(paths),
        "raw_rows": raw_rows,
        "refined_rows": refined_rows,
        "insert_attempted": attempted,
    }


def truncate_built_transactions(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE built_transactions RESTART IDENTITY"))
    log.info("TRUNCATE built_transactions")


def write_manifest(engine, path: Path, extra: dict) -> None:
    stats: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), **extra}
    with engine.connect() as conn:
        for asset_type in ("commercial", "factory", "detached"):
            row = conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int AS n,
                           COUNT(*) FILTER (WHERE contract_date IS NOT NULL)::int AS with_date,
                           COUNT(*) FILTER (WHERE road_width_label IS NOT NULL)::int AS with_road,
                           COUNT(*) FILTER (WHERE display_address IS NOT NULL)::int AS with_addr,
                           COUNT(*) FILTER (
                               WHERE beopjungri_code IS NOT NULL AND btrim(beopjungri_code::text) <> ''
                           )::int AS mapped
                    FROM built_transactions WHERE asset_type = :t
                    """
                ),
                {"t": asset_type},
            ).one()
            stats[asset_type] = {
                "count": row.n,
                "contract_date": row.with_date,
                "road_width_label": row.with_road,
                "display_address": row.with_addr,
                "beopjungri_mapped": row.mapped,
            }
        stats["total"] = conn.execute(text("SELECT COUNT(*)::int FROM built_transactions")).scalar()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("manifest written: %s", path)


def main() -> None:
    p = argparse.ArgumentParser(description="MOLIT raw base → built_transactions (Phase A)")
    p.add_argument("--commercial-only", action="store_true")
    p.add_argument("--factory-only", action="store_true")
    p.add_argument("--detached-only", action="store_true")
    p.add_argument("--truncate", action="store_true", help="TRUNCATE built_transactions before ingest")
    p.add_argument("--refresh-region-codes", action="store_true")
    p.add_argument("--smoke", action="store_true", help="서울 2021 CSV만")
    p.add_argument("--year-from", type=int, default=2021)
    p.add_argument("--year-to", type=int, default=2026)
    p.add_argument(
        "--manifest",
        type=Path,
        default=REPO / "logs" / "built_rebuild_manifest.json",
    )
    args = p.parse_args()

    only_flags = sum([args.commercial_only, args.factory_only, args.detached_only])
    if only_flags > 1:
        raise SystemExit("--*-only flags are mutually exclusive")

    built = get_built_engine()
    land = get_land_engine_for_region_copy()
    ensure_schema(built)
    if args.refresh_region_codes:
        sync_region_codes_from_land(built, land, force=True)
    else:
        copy_region_codes_if_empty(built, land)

    if args.truncate:
        truncate_built_transactions(built)

    region_maps = build_region_lookup(built)
    sido_prefix = "서울특별시" if args.smoke else None
    year_from = 2021 if args.smoke else args.year_from
    year_to = 2021 if args.smoke else args.year_to

    run_all = only_flags == 0
    ingest_log: dict = {"smoke": args.smoke, "ingest": {}}

    for asset_type in ("commercial", "factory", "detached"):
        if not run_all and not getattr(args, f"{asset_type}_only"):
            continue
        paths = list_csv_files(
            asset_type,  # type: ignore[arg-type]
            year_from=year_from,
            year_to=year_to,
            sido_prefix=sido_prefix,
        )
        if not paths:
            log.warning("no CSV files for %s", asset_type)
            continue
        stats = ingest_paths(paths, asset_type, built, region_maps)  # type: ignore[arg-type]
        ingest_log["ingest"][asset_type] = stats
        log_mapping_coverage(built, "built_transactions", asset_type=asset_type)

    write_manifest(built, args.manifest, ingest_log)

    with built.connect() as conn:
        for t in ("commercial", "factory", "detached"):
            n = conn.execute(
                text("SELECT COUNT(*) FROM built_transactions WHERE asset_type=:t"),
                {"t": t},
            ).scalar()
            log.info("built_transactions.%s = %s", t, n)


if __name__ == "__main__":
    main()
