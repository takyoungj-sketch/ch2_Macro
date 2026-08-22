"""builder_master.beopjungri_code 백필 — 세종형 시군구=동 키.

    python -m parcel_master.apply_kapt_beopjungri
    python -m parcel_master.apply_kapt_beopjungri --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import text

_PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PIPELINE))

from build_collective_building_attributes import (  # noqa: E402
    load_region_map,
    lookup_beopjungri_code,
)
from parcel_master.db_utils import get_collective_engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SELECT_SQL = text(
    """
    SELECT danji_code, sido_name, sigungu_name, eupmyeon_name, dongri_name, beopjungri_code
    FROM builder_master
    WHERE snapshot_ym = :ym
      AND (beopjungri_code IS NULL OR btrim(beopjungri_code) = '')
    """
)

UPDATE_SQL = text(
    """
    UPDATE builder_master
    SET beopjungri_code = :code
    WHERE snapshot_ym = :ym AND danji_code = :danji_code
    """
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fill builder_master.beopjungri_code from region_codes")
    p.add_argument("--snapshot-ym", default=None)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    engine = get_collective_engine()
    with engine.connect() as conn:
        snapshot_ym = args.snapshot_ym or conn.execute(
            text("SELECT MAX(snapshot_ym) FROM builder_master")
        ).scalar()
        if not snapshot_ym:
            raise SystemExit("builder_master 가 비어 있습니다")
        snapshot_ym = str(snapshot_ym).strip()
        region_map = load_region_map(conn)
        rows = list(conn.execute(SELECT_SQL, {"ym": snapshot_ym}).mappings())

    filled: list[tuple[str, str]] = []
    missed = 0
    for r in rows:
        code = lookup_beopjungri_code(
            region_map,
            sido=str(r["sido_name"] or ""),
            sigungu=str(r["sigungu_name"] or ""),
            dongri=str(r["dongri_name"] or ""),
            eupmyeon=str(r["eupmyeon_name"] or ""),
        )
        if code:
            filled.append((str(r["danji_code"]), code))
        else:
            missed += 1

    log.info("snapshot_ym=%s  empty=%s  fill=%s  miss=%s", snapshot_ym, len(rows), len(filled), missed)
    for danji, code in filled[:15]:
        log.info("  %s → %s", danji, code)
    if len(filled) > 15:
        log.info("  ... %s more", len(filled) - 15)

    if args.dry_run:
        log.info("dry-run: DB not changed")
        return

    with engine.begin() as conn:
        for danji, code in filled:
            conn.execute(UPDATE_SQL, {"ym": snapshot_ym, "danji_code": danji, "code": code})
    log.info("updated=%s", len(filled))


if __name__ == "__main__":
    main()
