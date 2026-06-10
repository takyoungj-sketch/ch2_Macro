# -*- coding: utf-8 -*-
"""
문제 historical CSV 6건 교체 + DB 오염 정리 + annual 재빌드.

대상 파일:
  경남 2011, 전남 2017, 전북 2013/2014/2016/2020
"""
from __future__ import annotations

import logging
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from clean import (
    build_region_lookup,
    clean_dataframe,
    map_beopjungri_codes,
    upsert_transactions,
    _make_hash,
)
from collect import collect_from_csv, load_to_raw_table
from db_utils import get_engine

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "raw" / "토지_2010_2020"
PIPELINE = Path(__file__).resolve().parent
PY = sys.executable

BAD_FILES = [
    "경상남도_토지_매매_2011.csv",
    "전라남도_토지_매매_2017.csv",
    "전북특별자치도_토지_매매_2013.csv",
    "전북특별자치도_토지_매매_2014.csv",
    "전북특별자치도_토지_매매_2016.csv",
    "전북특별자치도_토지_매매_2020.csv",
]

# (filename -> source_year for purge)
SOURCE_YEARS = (2011, 2013, 2014, 2016, 2017, 2020)
SIDO_REBUILD = ("46", "48", "52", "41")  # 41: 전남2017 파일이 경기 apt였음

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def backup_bad_csv() -> None:
    for name in BAD_FILES:
        p = RAW / name
        if not p.is_file():
            continue
        bak = p.with_suffix(p.suffix + ".bad")
        if bak.is_file():
            bak.unlink()
        p.rename(bak)
        log.info("백업: %s → %s", name, bak.name)


def download_fixed() -> None:
    cmds = [
        [PY, str(REPO / "scripts/monthly/download_molit_land_historical_csv.py"),
         "--regions", "경상남도", "--years", "2011", "--headless"],
        [PY, str(REPO / "scripts/monthly/download_molit_land_historical_csv.py"),
         "--regions", "전라남도", "--years", "2017", "--headless"],
        [PY, str(REPO / "scripts/monthly/download_molit_land_historical_csv.py"),
         "--regions", "전북특별자치도", "--years", "2013,2014,2016,2020", "--headless"],
    ]
    for cmd in cmds:
        log.info("다운로드: %s", " ".join(cmd[-6:]))
        subprocess.run(cmd, check=True, cwd=str(REPO))


def verify_downloads() -> None:
    r = subprocess.run(
        [PY, "_audit_all_csv_full.py"],
        cwd=str(PIPELINE),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(r.stdout)
    if r.returncode != 0:
        raise SystemExit("audit failed")
    for name in BAD_FILES:
        rep = _audit_one(RAW / name)
        if not rep:
            raise SystemExit(f"검증 실패: {name}")


def _audit_one(path: Path) -> bool:
    from _audit_all_csv_full import audit_file

    if not path.is_file():
        return False
    return audit_file(path).ok


def purge_polluted_raw_and_tx(engine) -> tuple[int, int]:
    """아파트 컬럼·미래 deal_ymd·2013배치의 2012-only 등 오염 raw/tx 삭제."""
    with engine.begin() as conn:
        # polluted raw ids
        tx_del = conn.execute(
            text(
                """
                WITH bad_raw AS (
                  SELECT r.id
                  FROM land_transactions_raw r
                  WHERE r.source_month = 6
                    AND r.source_year = ANY(:years)
                    AND (
                      r.raw_data ? '층'
                      OR r.raw_data ? '단지명'
                      OR r.raw_data ? '건축년도'
                      OR r.raw_data ? '전용면적(㎡)'
                      OR r.raw_data->>'deal_ymd' ~ '^202[4-9]'
                      OR (
                        r.source_year = 2011
                        AND r.raw_data->>'deal_ymd' LIKE '2020%'
                      )
                      OR (
                        r.source_year = 2013
                        AND r.raw_data->>'deal_ymd' ~ '^2012'
                        AND r.raw_data->>'sigungu_name' LIKE '전북%'
                      )
                    )
                ),
                del_tx AS (
                  DELETE FROM land_transactions lt
                  USING bad_raw b
                  WHERE lt.raw_id = b.id
                  RETURNING lt.id
                )
                SELECT COUNT(1) FROM del_tx
                """
            ),
            {"years": list(SOURCE_YEARS)},
        ).scalar() or 0

        raw_del = conn.execute(
            text(
                """
                DELETE FROM land_transactions_raw r
                WHERE r.source_month = 6
                  AND r.source_year = ANY(:years)
                  AND (
                    r.raw_data ? '층'
                    OR r.raw_data ? '단지명'
                    OR r.raw_data ? '건축년도'
                    OR r.raw_data ? '전용면적(㎡)'
                    OR r.raw_data->>'deal_ymd' ~ '^202[4-9]'
                    OR (
                      r.source_year = 2011
                      AND r.raw_data->>'deal_ymd' LIKE '2020%'
                    )
                    OR (
                      r.source_year = 2013
                      AND r.raw_data->>'deal_ymd' ~ '^2012'
                      AND r.raw_data->>'sigungu_name' LIKE '전북%'
                    )
                  )
                """
            ),
            {"years": list(SOURCE_YEARS)},
        ).rowcount or 0

    log.info("삭제: land_transactions %d건, land_transactions_raw %d건", tx_del, raw_del)
    return tx_del, raw_del


def collect_fixed_files() -> int:
    total = 0
    today = date.today()
    for name in BAD_FILES:
        path = RAW / name
        if not path.is_file():
            raise FileNotFoundError(path)
        df = collect_from_csv(str(path))
        ym = __import__("re").search(r"_(\d{4})\.csv$", name)
        sy = int(ym.group(1)) if ym else today.year
        n = load_to_raw_table(df, sy, 6)
        log.info("collect %s: %d rows", name, n)
        total += n
    return total


def clean_new_raw(engine) -> int:
    since = date.today().isoformat()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT r.id AS raw_id, r.source_year, r.source_month, r.raw_data
                FROM land_transactions_raw r
                WHERE r.loaded_at >= :since
                  AND r.source_month = 6
                  AND r.source_year = ANY(:years)
                  AND NOT EXISTS (
                    SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id
                  )
                ORDER BY r.id
                """
            ),
            {"since": since, "years": list(SOURCE_YEARS)},
        ).fetchall()
    if not rows:
        log.info("clean: 신규 raw 없음")
        return 0
    records = []
    for row in rows:
        rec = {"_raw_id": row[0], "_source_year": row[1], "_source_month": row[2]}
        rec.update(row[3])
        records.append(rec)
    df = pd.DataFrame(records)
    log.info("clean: %d건", len(df))
    cleaned = clean_dataframe(df)
    lookup = build_region_lookup(engine)
    meta = map_beopjungri_codes(cleaned, lookup)
    cleaned["beopjungri_code"] = meta["beopjungri_code"].values
    cleaned["needs_review"] = meta["needs_review"].values
    cleaned["mapping_notes"] = meta["mapping_notes"].values
    cleaned["transaction_hash"] = cleaned.apply(_make_hash, axis=1)
    cleaned["sido_code"] = cleaned["beopjungri_code"].astype(str).str[:2]
    cleaned["sigungu_code"] = cleaned["beopjungri_code"].astype(str).str[:5]
    bc_empty = cleaned["beopjungri_code"].fillna("").astype(str).str.strip().eq("")
    cleaned.loc[bc_empty, "needs_review"] = True
    cleaned.loc[bc_empty, "is_valid"] = False
    upsert_transactions(cleaned)
    return len(cleaned)


def rebuild_annual() -> None:
    cmd = [
        PY,
        "build_annual_stats.py",
        "--years",
        "2010-2026",
        "--with-upper",
    ]
    for sc in SIDO_REBUILD:
        cmd.extend(["--sido-code", sc])
    subprocess.run(cmd, check=True, cwd=str(PIPELINE))


def verify_annual() -> None:
    engine = get_engine()
    with engine.connect() as c:
        for sc in ("46", "48", "52"):
            r = c.execute(
                text(
                    """
                    SELECT MIN(calendar_year), MAX(calendar_year), COUNT(1)
                    FROM land_annual_stats
                    WHERE LEFT(btrim(beopjungri_code::text), 2) = :sc
                    """
                ),
                {"sc": sc},
            ).one()
            print(f"annual {sc}: {r[0]}~{r[1]} rows={r[2]}")


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--skip-download", action="store_true")
    p.add_argument("--skip-db", action="store_true")
    args = p.parse_args()

    if not args.skip_download:
        backup_bad_csv()
        download_fixed()
        verify_downloads()

    if not args.skip_db:
        engine = get_engine()
        purge_polluted_raw_and_tx(engine)
        collect_fixed_files()
        clean_new_raw(engine)
        rebuild_annual()
        verify_annual()


if __name__ == "__main__":
    main()
