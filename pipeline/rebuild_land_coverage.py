#!/usr/bin/env python3
"""land_transactions 재구축 커버리지·표시 컬럼 실측 + Promote 게이트."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from sqlalchemy import text

from db_utils import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEFAULT_MIN_LOT_PCT = 95.0
DEFAULT_MIN_DEAL_PCT = 95.0
DEFAULT_YEAR_FROM = 2021


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


def report_by_year(engine, *, year_from: int) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    contract_year AS year,
                    COUNT(*) FILTER (WHERE is_valid)::bigint AS valid,
                    COUNT(*) FILTER (
                        WHERE is_valid AND lot_display IS NOT NULL
                            AND btrim(lot_display::text) <> ''
                    )::bigint AS lot_ok,
                    COUNT(*) FILTER (
                        WHERE is_valid AND deal_type IS NOT NULL
                            AND btrim(deal_type::text) <> ''
                    )::bigint AS deal_ok
                FROM land_transactions
                WHERE contract_year >= :year_from
                GROUP BY contract_year
                ORDER BY contract_year
                """
            ),
            {"year_from": year_from},
        ).mappings().all()
    out: list[dict] = []
    for r in rows:
        v = int(r["valid"] or 0)
        lot_pct = round(100.0 * int(r["lot_ok"] or 0) / v, 2) if v else 0.0
        deal_pct = round(100.0 * int(r["deal_ok"] or 0) / v, 2) if v else 0.0
        out.append(
            {
                "year": int(r["year"]),
                "valid": v,
                "lot_display_pct": lot_pct,
                "deal_type_pct": deal_pct,
            }
        )
    return out


def exception_queue_report(engine) -> dict:
    """land_exception_queue pending 건수 조회."""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'pending')::bigint AS pending,
                        COUNT(*) FILTER (WHERE status = 'resolved')::bigint AS resolved,
                        COUNT(*) FILTER (WHERE status = 'dismissed')::bigint AS dismissed
                    FROM land_exception_queue
                    """
                )
            ).mappings().one()
        return dict(row)
    except Exception:
        return {"pending": 0, "resolved": 0, "dismissed": 0, "_unavailable": True}


def raw_id_dup_report(engine) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*)::bigint AS dup_groups,
                    COALESCE(SUM(cnt - 1), 0)::bigint AS extra_rows
                FROM (
                    SELECT COUNT(*) AS cnt
                    FROM land_transactions
                    WHERE raw_id IS NOT NULL
                    GROUP BY raw_id
                    HAVING COUNT(*) > 1
                ) s
                """
            )
        ).mappings().one()
    return dict(row)


def run_gate(
    by_year: list[dict],
    *,
    min_lot_pct: float,
    min_deal_pct: float,
) -> list[str]:
    failures: list[str] = []
    for row in by_year:
        y = row["year"]
        if row["lot_display_pct"] < min_lot_pct:
            failures.append(
                f"{y}: lot_display {row['lot_display_pct']}% < {min_lot_pct}%"
            )
        if row["deal_type_pct"] < min_deal_pct:
            failures.append(
                f"{y}: deal_type {row['deal_type_pct']}% < {min_deal_pct}%"
            )
    return failures


def main() -> None:
    p = argparse.ArgumentParser(description="land_transactions 표시 컬럼·커버리지 리포트")
    p.add_argument("--out", type=Path, help="JSON 저장 경로")
    p.add_argument("--by-year", action="store_true", help="연도별 lot_display/deal_type 채움률")
    p.add_argument("--year-from", type=int, default=DEFAULT_YEAR_FROM)
    p.add_argument("--gate", action="store_true", help="임계 미달 시 exit 1 (Promote 전 필수)")
    p.add_argument("--min-lot-pct", type=float, default=DEFAULT_MIN_LOT_PCT)
    p.add_argument("--min-deal-pct", type=float, default=DEFAULT_MIN_DEAL_PCT)
    args = p.parse_args()

    eng = get_engine()
    data = report(eng)
    raw_dup = raw_id_dup_report(eng)
    data["raw_id_dup_groups"] = int(raw_dup.get("dup_groups") or 0)
    data["raw_id_extra_rows"] = int(raw_dup.get("extra_rows") or 0)
    eq = exception_queue_report(eng)
    data["exception_queue_pending"] = int(eq.get("pending") or 0)
    data["exception_queue_resolved"] = int(eq.get("resolved") or 0)
    log.info("coverage: %s", json.dumps(data, ensure_ascii=False, default=str))

    payload: dict = {"summary": data}
    if args.by_year or args.gate:
        by_year = report_by_year(eng, year_from=args.year_from)
        payload["by_year"] = by_year
        for row in by_year:
            log.info(
                "year=%s valid=%s lot_display=%s%% deal_type=%s%%",
                row["year"],
                row["valid"],
                row["lot_display_pct"],
                row["deal_type_pct"],
            )

    if args.gate:
        failures = run_gate(
            payload.get("by_year") or [],
            min_lot_pct=args.min_lot_pct,
            min_deal_pct=args.min_deal_pct,
        )
        if int(data.get("raw_id_dup_groups") or 0) > 0:
            failures.append(
                f"raw_id 중복 {data['raw_id_dup_groups']}그룹 "
                f"(+{data['raw_id_extra_rows']}행) — dedupe_land_transactions.py --execute"
            )
        eq_pending = int(data.get("exception_queue_pending") or 0)
        if eq_pending > 0:
            log.warning(
                "Exception Queue pending %d건 — detect_land_exceptions.py 결과를 검토하고 "
                "land_correction_rules 에 Rule 등록 또는 dismissed 처리 권장.",
                eq_pending,
            )
        if failures:
            log.error("GATE FAIL:")
            for f in failures:
                log.error("  - %s", f)
            log.error(
                "표시 컬럼: python backfill_land_display.py  |  "
                "중복: python dedupe_land_transactions.py --execute  |  "
                "예외 검토: python detect_land_exceptions.py --dry-run"
            )
            sys.exit(1)
        log.info(
            "GATE OK (year_from=%s, raw_id duplicates=0, exception_queue_pending=%d)",
            args.year_from,
            eq_pending,
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        log.info("wrote %s", args.out)


if __name__ == "__main__":
    main()
