#!/usr/bin/env python3
"""land_transactions 재구축 커버리지·표시 컬럼 실측."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from sqlalchemy import text

from db_utils import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def report(engine) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*)::bigint AS total,
                    COUNT(*) FILTER (WHERE is_valid)::bigint AS valid,
                    COUNT(*) FILTER (WHERE beopjungri_code IS NOT NULL
                        AND btrim(beopjungri_code::text) <> '')::bigint AS mapped,
                    COUNT(*) FILTER (WHERE COALESCE(needs_review, false))::bigint AS needs_review,
                    COUNT(*) FILTER (WHERE is_valid AND lot_display IS NOT NULL
                        AND btrim(lot_display::text) <> '')::bigint AS lot_display_valid,
                    COUNT(*) FILTER (WHERE is_valid AND deal_type IS NOT NULL
                        AND btrim(deal_type::text) <> '')::bigint AS deal_type_valid,
                    COUNT(*) FILTER (WHERE is_valid AND partial_ownership_label IS NOT NULL
                        AND btrim(partial_ownership_label::text) <> '')::bigint AS partial_valid,
                    COUNT(*) FILTER (WHERE is_valid AND contract_date IS NOT NULL)::bigint AS contract_date_valid,
                    MIN(contract_year) AS min_year,
                    MAX(contract_year) AS max_year
                FROM land_transactions
                """
            )
        ).mappings().one()
    out = dict(row)
    v = int(out.get("valid") or 0)
    if v:
        out["lot_display_pct"] = round(100.0 * int(out["lot_display_valid"]) / v, 2)
        out["deal_type_pct"] = round(100.0 * int(out["deal_type_valid"]) / v, 2)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, help="JSON 저장 경로")
    args = p.parse_args()
    eng = get_engine()
    data = report(eng)
    log.info("coverage: %s", json.dumps(data, ensure_ascii=False, default=str))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        log.info("wrote %s", args.out)


if __name__ == "__main__":
    main()
