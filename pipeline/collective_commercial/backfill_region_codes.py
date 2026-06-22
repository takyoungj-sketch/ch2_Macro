"""기존 collective_commercial_transactions/commercial_clusters 행정코드 백필."""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

_PIPELINE = Path(__file__).resolve().parent.parent
_ROOT = _PIPELINE / "collective"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_PIPELINE))

from clean import build_region_lookup  # noqa: E402
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from region_mapping import (  # noqa: E402
    CODE_WIDTH,
    attach_beopjungri_codes,
    clean_code_columns,
    log_mapping_coverage,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
DDL_REGION = REPO / "db" / "030_collective_commercial_region_codes.sql"

UPDATE_TX = text(
    """
    UPDATE collective_commercial_transactions
    SET beopjungri_code = :beopjungri_code,
        sido_code = :sido_code,
        sigungu_code = :sigungu_code,
        eupmyeondong_code = :eupmyeondong_code,
        needs_review = :needs_review,
        mapping_notes = :mapping_notes
    WHERE id = :id
    """
)

UPDATE_CLUSTER = text(
    """
    UPDATE commercial_clusters c
    SET beopjungri_code = s.beopjungri_code,
        sido_code = s.sido_code,
        sigungu_code = s.sigungu_code,
        eupmyeondong_code = s.eupmyeondong_code,
        updated_at = NOW()
    FROM (
        SELECT DISTINCT ON (cluster_key)
            cluster_key,
            beopjungri_code,
            sido_code,
            sigungu_code,
            eupmyeondong_code
        FROM collective_commercial_transactions
        WHERE cluster_key IS NOT NULL
          AND beopjungri_code IS NOT NULL
          AND btrim(beopjungri_code::text) <> ''
        ORDER BY cluster_key, id
    ) s
    WHERE c.cluster_key = s.cluster_key
    """
)


def _load_sync_region_codes():
    spec = importlib.util.spec_from_file_location(
        "collective_import_refined", _ROOT / "import_refined.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load collective/import_refined.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.sync_region_codes_from_land


def apply_ddl(engine) -> None:
    if not DDL_REGION.is_file():
        return
    with engine.begin() as conn:
        conn.execute(text(DDL_REGION.read_text(encoding="utf-8")))
    log.info("DDL applied: %s", DDL_REGION.name)


def backfill_transactions(engine, *, batch_size: int, force: bool) -> int:
    region_maps = build_region_lookup(engine)
    updated = 0
    while True:
        missing_clause = "" if force else """
              AND (beopjungri_code IS NULL OR btrim(beopjungri_code::text) = '')
              AND COALESCE(needs_review, false) = false
        """
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT id, addr1, addr2, addr3, addr4, addr5
                    FROM collective_commercial_transactions
                    WHERE is_valid = true
                    {missing_clause}
                    ORDER BY id
                    LIMIT :lim
                    """
                ),
                {"lim": batch_size},
            ).mappings().all()
        if not rows:
            break

        df = pd.DataFrame(rows)
        mapped = clean_code_columns(attach_beopjungri_codes(df, engine, region_maps=region_maps))
        payloads = []
        for _, row in mapped.iterrows():
            rec = {"id": int(row["id"])}
            for col, width in CODE_WIDTH.items():
                val = row.get(col)
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    rec[col] = None
                else:
                    s = str(val).strip()
                    rec[col] = s[:width] if s else None
            rec["needs_review"] = bool(row.get("needs_review", False))
            notes = row.get("mapping_notes")
            if notes is None or (isinstance(notes, float) and pd.isna(notes)):
                rec["mapping_notes"] = None
            else:
                rec["mapping_notes"] = str(notes).strip() or None
            payloads.append(rec)
        with engine.begin() as conn:
            conn.execute(UPDATE_TX, payloads)
        updated += len(payloads)
        log.info("backfill batch: %d rows (total %d)", len(payloads), updated)
        if force:
            break
    return updated


def sync_cluster_codes(engine) -> None:
    with engine.begin() as conn:
        conn.execute(UPDATE_CLUSTER)
    log.info("commercial_clusters region codes synced from transactions")


def main() -> None:
    p = argparse.ArgumentParser(description="집합상가·공장 행정코드 백필")
    p.add_argument("--skip-ddl", action="store_true")
    p.add_argument("--refresh-region-codes", action="store_true")
    p.add_argument("--force", action="store_true", help="이미 매핑된 행도 재계산(단일 배치)")
    p.add_argument("--batch-size", type=int, default=5000)
    args = p.parse_args()

    engine = get_collective_engine()
    if not args.skip_ddl:
        apply_ddl(engine)

    sync_fn = _load_sync_region_codes()
    sync_fn(engine, get_land_engine_for_region_copy(), force=args.refresh_region_codes)

    n = backfill_transactions(engine, batch_size=args.batch_size, force=args.force)
    sync_cluster_codes(engine)
    log.info("backfill complete: %d transactions updated", n)
    log_mapping_coverage(engine, "collective_commercial_transactions", asset_type="collective_shop")
    log_mapping_coverage(engine, "collective_commercial_transactions", asset_type="collective_factory")


if __name__ == "__main__":
    main()
