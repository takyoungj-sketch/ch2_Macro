"""
MOLIT raw 또는 정제 xlsx/csv → collective_transactions 적재.

  원본/아파트/*.xlsx (raw, skiprows=13)
  원본/오피스텔/*.csv (raw, skiprows=16 — 동 컬럼 없음)
  원본/연립다세대/*.csv (raw, skiprows=16 — 대지권면적 col7)
  원본/분양입주권/*.csv (raw, skiprows=16 — 분양권/입주권 col10)

집합부동산 적재 정책 (토지와 다름):
  - 해제 거래만 refine 단계에서 제외
  - 그 외 원본 행은 semantic dedupe 없이 전량 INSERT
  - transaction_hash = SHA-256(asset_type|파일명|원본순번) — 행 식별용, UNIQUE 아님
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from region_mapping import attach_beopjungri_codes, clean_code_columns, log_mapping_coverage

from building_keys import _sha256_series, attach_building_identity
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy
from refine import InputKind, detect_input_kind, read_source_file, refine_dataframe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
RAW_BASE = REPO / "raw" / "raw base"
DEFAULT_APARTMENT_DIR = RAW_BASE / "아파트_2021_2026"
DEFAULT_OFFICETEL_DIR = RAW_BASE / "오피스텔_2021_2026"
DEFAULT_ROWHOUSE_DIR = RAW_BASE / "연립다세대_2021_2026"
DEFAULT_PRESALE_DIR = RAW_BASE / "분양입주권_2021_2026"
DEFAULT_ROWHOUSE = DEFAULT_ROWHOUSE_DIR  # legacy --rowhouse 단일 파일 대신 디렉터리 기본
DEFAULT_OFFICETEL = DEFAULT_OFFICETEL_DIR  # legacy --officetel 단일 파일 대신 디렉터리 기본
DDL = REPO / "db" / "016_collective_transactions.sql"
MIGRATION_ROW_IDENTITY = REPO / "db" / "017_collective_tx_row_identity.sql"
MIGRATION_LAND_AREA = REPO / "db" / "018_collective_land_area.sql"
MIGRATION_REGION = REPO / "db" / "022_collective_region_patch.sql"
MIGRATION_REGION_META = REPO / "db" / "022b_region_sigungu_meta.sql"
MIGRATION_DISPLAY = REPO / "db" / "026_collective_tx_display_columns.sql"
MIGRATION_ROLLING = REPO / "db" / "027_collective_building_rolling_stats.sql"

RESIDENTIAL_ASSET_TYPES = ("apartment", "rowhouse", "officetel", "presale")

INSERT_STMT = text(
    """
    INSERT INTO collective_transactions (
        transaction_hash, asset_type, building_key, display_name,
        building_name, housing_subtype,
        addr1, addr2, addr3, addr4, addr5, lot_number, road_name,
        sido_code, sigungu_code, eupmyeondong_code, beopjungri_code,
        contract_year, contract_month, contract_date,
        building_year, building_age, exclusive_area, land_area, price, unit_price,
        area_bucket, age_bucket, floor, dong,
        buyer_type, seller_type, deal_type,
        is_valid, needs_review, mapping_notes
    ) VALUES (
        :transaction_hash, :asset_type, :building_key, :display_name,
        :building_name, :housing_subtype,
        :addr1, :addr2, :addr3, :addr4, :addr5, :lot_number, :road_name,
        :sido_code, :sigungu_code, :eupmyeondong_code, :beopjungri_code,
        :contract_year, :contract_month, :contract_date,
        :building_year, :building_age, :exclusive_area, :land_area, :price, :unit_price,
        :area_bucket, :age_bucket, :floor, :dong,
        :buyer_type, :seller_type, :deal_type,
        :is_valid, :needs_review, :mapping_notes
    )
    """
)


def _null_if_nan(val):
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, str) and val.strip().lower() in ("", "nan", "none"):
        return None
    return val


def _clean_code(val, width: int | None = None) -> str | None:
    val = _null_if_nan(val)
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    if width is not None:
        s = s[:width]
    return s or None


def _load_region_codes_df(engine) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(
            text(
                """
                SELECT sido_name, sigungu_name, eupmyeondong_name, beopjungri_name,
                       sido_code, sigungu_code, eupmyeondong_code, beopjungri_code
                FROM region_codes WHERE COALESCE(is_active, true)
                """
            ),
            conn,
        )


def _attach_codes(df: pd.DataFrame, rc: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ("addr1", "addr2", "addr3", "addr4", "addr5"):
        if c not in out.columns:
            out[c] = ""
        out[c] = out[c].fillna("").astype(str).str.strip()

    code_cols = ["sido_code", "sigungu_code", "eupmyeondong_code", "beopjungri_code"]
    name_cols = ["sido_name", "sigungu_name", "eupmyeondong_name", "beopjungri_name"]
    rc = rc.copy()
    for c in name_cols:
        rc[c] = rc[c].fillna("").astype(str).str.strip()

    out["_ri"] = out["addr5"].where(out["addr5"] != "", out["addr4"])
    merged = out.merge(
        rc[name_cols + code_cols],
        left_on=["addr1", "addr2", "addr3", "_ri"],
        right_on=name_cols,
        how="left",
        suffixes=("", "_rc"),
    )

    miss = merged["sido_code"].isna() & (merged["addr4"] != "")
    if miss.any():
        m2 = out.loc[miss].merge(
            rc[name_cols + code_cols],
            left_on=["addr1", "addr2", "addr3", "addr4"],
            right_on=name_cols,
            how="left",
        )
        for c in code_cols:
            merged.loc[miss, c] = m2[c].values

    miss = merged["sido_code"].isna()
    if miss.any():
        eup = rc.drop_duplicates(subset=name_cols[:3], keep="first")
        m3 = out.loc[miss, ["addr1", "addr2", "addr3"]].merge(
            eup[name_cols[:3] + code_cols],
            left_on=["addr1", "addr2", "addr3"],
            right_on=name_cols[:3],
            how="left",
        )
        for c in code_cols:
            merged.loc[miss, c] = m3[c].values

    for c in code_cols:
        out[c] = merged[c]
    return out.drop(columns=["_ri"], errors="ignore")


def ensure_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(DDL.read_text(encoding="utf-8")))
        if MIGRATION_ROW_IDENTITY.is_file():
            conn.execute(text(MIGRATION_ROW_IDENTITY.read_text(encoding="utf-8")))
        if MIGRATION_LAND_AREA.is_file():
            conn.execute(text(MIGRATION_LAND_AREA.read_text(encoding="utf-8")))
        if MIGRATION_REGION.is_file():
            conn.execute(text(MIGRATION_REGION.read_text(encoding="utf-8")))
        if MIGRATION_REGION_META.is_file():
            conn.execute(text(MIGRATION_REGION_META.read_text(encoding="utf-8")))
        if MIGRATION_DISPLAY.is_file():
            conn.execute(text(MIGRATION_DISPLAY.read_text(encoding="utf-8")))
        if MIGRATION_ROLLING.is_file():
            conn.execute(text(MIGRATION_ROLLING.read_text(encoding="utf-8")))


def truncate_residential(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM collective_transactions
                WHERE asset_type IN ('apartment', 'rowhouse', 'officetel', 'presale')
                """
            )
        )
    log.info("truncated residential collective_transactions (4 types)")


def sync_region_codes_from_land(collective_engine, land_engine, *, force: bool = False) -> None:
    with collective_engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM region_codes")).scalar()
    if n and int(n) > 0 and not force:
        log.info("region_codes already %s rows", n)
        return
    with land_engine.connect() as src, collective_engine.begin() as dst:
        rows = src.execute(text("SELECT * FROM region_codes")).mappings().all()
        if not rows:
            raise SystemExit("land_stats.region_codes empty")
        if force:
            dst.execute(text("TRUNCATE region_codes RESTART IDENTITY"))
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


def _attach_source_keys(
    df_raw: pd.DataFrame, path: Path, *, input_kind: InputKind
) -> pd.DataFrame:
    """원본 파일·순번 기준 행 식별자 (집합부동산 전량 적재용)."""
    out = df_raw.copy()
    if input_kind == "raw" and out.shape[1] > 0:
        row_id = out.iloc[:, 0].astype(str).str.strip()
    else:
        row_id = pd.Series(range(len(out)), index=out.index, dtype="int64").astype(str)
    out["_source_key"] = path.name + "|" + row_id
    return out


def _prepare_df(
    df_raw: pd.DataFrame,
    asset_type: str,
    path: Path,
    *,
    input_kind: InputKind | None = None,
) -> pd.DataFrame:
    kind = input_kind or detect_input_kind(df_raw)
    keyed = _attach_source_keys(df_raw, path, input_kind=kind)
    df = refine_dataframe(keyed, asset_type, input_kind=kind)
    return attach_building_identity(df, asset_type)


def _add_row_hashes(df: pd.DataFrame, asset_type: str) -> pd.DataFrame:
    if "_source_key" not in df.columns:
        raise ValueError("_source_key missing — call _attach_source_keys before refine")
    out = df.copy()
    raw = asset_type + "|" + out["_source_key"].astype(str)
    out["transaction_hash"] = _sha256_series(raw)
    return out.drop(columns=["_source_key"], errors="ignore")


def _records_from_df(df: pd.DataFrame, asset_type: str) -> list[dict]:
    work = _add_row_hashes(df, asset_type)
    records: list[dict] = []
    for row in work.itertuples(index=False):
        rec = {
            "transaction_hash": row.transaction_hash,
            "asset_type": asset_type,
            "building_key": row.building_key,
            "display_name": row.display_name,
            "building_name": _null_if_nan(getattr(row, "building_name", None)),
            "housing_subtype": _null_if_nan(getattr(row, "housing_subtype", None)),
            "addr1": _null_if_nan(getattr(row, "addr1", None)),
            "addr2": _null_if_nan(getattr(row, "addr2", None)),
            "addr3": _null_if_nan(getattr(row, "addr3", None)),
            "addr4": _null_if_nan(getattr(row, "addr4", None)),
            "addr5": _null_if_nan(getattr(row, "addr5", None)),
            "lot_number": _null_if_nan(getattr(row, "lot_number", None)),
            "road_name": _null_if_nan(getattr(row, "road_name", None)),
            "contract_year": int(row.contract_year) if pd.notna(getattr(row, "contract_year", None)) else None,
            "contract_month": int(row.contract_month) if pd.notna(getattr(row, "contract_month", None)) else None,
            "contract_date": getattr(row, "contract_date", None),
            "building_year": int(row.building_year) if pd.notna(getattr(row, "building_year", None)) else None,
            "building_age": _null_if_nan(getattr(row, "building_age", None)),
            "exclusive_area": float(row.exclusive_area),
            "land_area": _null_if_nan(getattr(row, "land_area", None)),
            "price": float(row.price),
            "unit_price": float(row.unit_price) if pd.notna(getattr(row, "unit_price", None)) else None,
            "area_bucket": _null_if_nan(getattr(row, "area_bucket", None)),
            "age_bucket": _null_if_nan(getattr(row, "age_bucket", None)),
            "floor": _null_if_nan(getattr(row, "floor", None)),
            "dong": _null_if_nan(getattr(row, "dong", None)),
            "buyer_type": _null_if_nan(getattr(row, "buyer_type", None)),
            "seller_type": _null_if_nan(getattr(row, "seller_type", None)),
            "deal_type": _null_if_nan(getattr(row, "deal_type", None)),
            "is_valid": True,
            "sido_code": getattr(row, "sido_code", None),
            "sigungu_code": getattr(row, "sigungu_code", None),
            "eupmyeondong_code": getattr(row, "eupmyeondong_code", None),
            "beopjungri_code": getattr(row, "beopjungri_code", None),
            "needs_review": bool(getattr(row, "needs_review", False)),
            "mapping_notes": _null_if_nan(getattr(row, "mapping_notes", None)),
        }
        for ck in ("sido_code", "sigungu_code", "eupmyeondong_code", "beopjungri_code"):
            w = {"sido_code": 2, "sigungu_code": 5, "eupmyeondong_code": 8, "beopjungri_code": 10}[ck]
            rec[ck] = _clean_code(rec.get(ck), w)
        records.append(rec)
    return records


def _insert_records(engine, records: list[dict]) -> int:
    if not records:
        return 0
    inserted = 0
    batch_size = 2000
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        with engine.begin() as conn:
            for rec in batch:
                conn.execute(INSERT_STMT, rec)
        inserted += len(batch)
    return inserted


def ingest_paths(
    paths: list[Path],
    asset_type: str,
    engine,
    region_maps: dict,
    truncate_type: bool,
    *,
    resume_from: str | None = None,
) -> int:
    if truncate_type:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM collective_transactions WHERE asset_type = :t"),
                {"t": asset_type},
            )

    total = 0
    past_resume = resume_from is None
    for path in paths:
        if not past_resume:
            if path.name == resume_from:
                past_resume = True
            else:
                log.info("skip (resume) %s", path.name)
                continue
        if not path.is_file():
            log.warning("skip missing %s", path)
            continue
        log.info("Reading %s", path)
        df_raw, kind = read_source_file(path)
        df = _prepare_df(df_raw, asset_type, path, input_kind=kind)
        df = attach_beopjungri_codes(df, engine, region_maps=region_maps)
        df = clean_code_columns(df)
        n = _insert_records(engine, _records_from_df(df, asset_type))
        total += n
        log.info("%s: %d rows (cumulative %d)", path.name, n, total)

    log.info("%s: inserted %d rows", asset_type, total)
    return total


def resolve_apartment_paths(apartment_dir: Path) -> list[Path]:
    if apartment_dir.is_dir():
        paths = sorted(apartment_dir.glob("*.csv"))
        if not paths:
            paths = sorted(apartment_dir.glob("*.xlsx"))
        return paths
    return [apartment_dir]


resolve_officetel_paths = resolve_apartment_paths
resolve_rowhouse_paths = resolve_apartment_paths


def resolve_presale_paths(presale_arg: Path) -> list[Path]:
    paths = resolve_officetel_paths(presale_arg)
    return [p for p in paths if "_분양입주권_매매_" in p.name]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apartment-dir", type=Path, default=DEFAULT_APARTMENT_DIR)
    p.add_argument("--rowhouse", type=Path, default=DEFAULT_ROWHOUSE, help="연립 정제 xlsx 단일 또는 원본 csv 디렉터리")
    p.add_argument("--rowhouse-dir", type=Path, default=None, help="원본/연립다세대/*.csv (--rowhouse 보다 우선)")
    p.add_argument(
        "--officetel",
        type=Path,
        default=DEFAULT_OFFICETEL,
        help="오피스텔 정제 xlsx 단일 파일 또는 원본 csv 디렉터리",
    )
    p.add_argument("--officetel-dir", type=Path, default=None, help="원본/오피스텔/*.csv ( --officetel 보다 우선 )")
    p.add_argument(
        "--presale-dir",
        type=Path,
        default=DEFAULT_PRESALE_DIR,
        help="원본/분양입주권/*.csv 디렉터리",
    )
    p.add_argument("--apartment-only", action="store_true")
    p.add_argument("--rowhouse-only", action="store_true")
    p.add_argument("--officetel-only", action="store_true")
    p.add_argument("--presale-only", action="store_true")
    p.add_argument("--refresh-region-codes", action="store_true")
    p.add_argument(
        "--truncate-residential",
        action="store_true",
        help="주거 4유형 collective_transactions 전량 삭제 후 ingest",
    )
    p.add_argument(
        "--resume-from",
        metavar="FILENAME",
        help="해당 파일명부터 ingest (이전 파일 스킵, truncate 없이 재개)",
    )
    args = p.parse_args()

    only = sum([args.apartment_only, args.rowhouse_only, args.officetel_only, args.presale_only])
    if only > 1:
        raise SystemExit("only one --*-only flag")

    from clean import build_region_lookup

    eng = get_collective_engine()
    land = get_land_engine_for_region_copy()
    ensure_schema(eng)
    sync_region_codes_from_land(eng, land, force=args.refresh_region_codes)
    region_maps = build_region_lookup(eng)

    if args.truncate_residential and only == 0:
        truncate_residential(eng)

    run_all = only == 0
    if run_all or args.apartment_only:
        apt_paths = resolve_apartment_paths(args.apartment_dir)
        if not apt_paths:
            raise SystemExit(f"no apartment files under {args.apartment_dir}")
        ingest_paths(
            apt_paths,
            "apartment",
            eng,
            region_maps,
            truncate_type=(run_all or args.apartment_only) and not args.resume_from,
            resume_from=args.resume_from if (run_all or args.apartment_only) else None,
        )
        log_mapping_coverage(eng, "collective_transactions", asset_type="apartment")
    if run_all or args.rowhouse_only:
        rh_root = args.rowhouse_dir or args.rowhouse
        rh_paths = resolve_rowhouse_paths(rh_root)
        if not rh_paths:
            raise SystemExit(f"no rowhouse files under {rh_root}")
        ingest_paths(rh_paths, "rowhouse", eng, region_maps, truncate_type=run_all or args.rowhouse_only)
        log_mapping_coverage(eng, "collective_transactions", asset_type="rowhouse")
    if run_all or args.officetel_only:
        ot_root = args.officetel_dir or args.officetel
        ot_paths = resolve_officetel_paths(ot_root)
        if not ot_paths:
            raise SystemExit(f"no officetel files under {ot_root}")
        ingest_paths(ot_paths, "officetel", eng, region_maps, truncate_type=run_all or args.officetel_only)
        log_mapping_coverage(eng, "collective_transactions", asset_type="officetel")
    if run_all or args.presale_only:
        ps_paths = resolve_presale_paths(args.presale_dir)
        if not ps_paths:
            if args.presale_only:
                raise SystemExit(f"no presale files under {args.presale_dir}")
            log.warning("no presale csv under %s — skip", args.presale_dir)
        else:
            ingest_paths(ps_paths, "presale", eng, region_maps, truncate_type=run_all or args.presale_only)
            log_mapping_coverage(eng, "collective_transactions", asset_type="presale")


if __name__ == "__main__":
    main()
