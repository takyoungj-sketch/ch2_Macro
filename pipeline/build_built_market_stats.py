#!/usr/bin/env python3
"""
built_transactions(built_stats DB) → market_stats(collective_stats DB) + built_annual_stats(built_stats DB).

일반 부동산(상업업무/공장창고/단독다가구) — Layer 3 market_stats 도메인 공백 메움.
단가 = price / gross_area (만원/㎡, gross_area>0 인 거래만). 원장·기존 built 파이프라인은 무변경.

설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md §12 (D-027)
DDL: db/042_built_annual_stats.sql

예)
  cd pipeline
  python build_built_market_stats.py --windows 3,5
  python build_built_market_stats.py --annual-only --years 2023-2025
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_collective_market_stats import upsert_market_stats  # noqa: E402
from build_stats_v2 import (  # noqa: E402
    default_as_of_month,
    parse_as_of_month,
    period_bounds_for_window,
)
from built.db_utils import get_built_engine  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from stats import compute_stats  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

ASSET_DOMAINS: dict[str, str] = {
    "commercial": "commercial_market",
    "factory": "factory_market",
    "detached": "detached_market",
}

from region_canonical import canonical_prefix_coalesce_sql, canonical_select_expr  # noqa: E402
from region_mapping import region_codes_lateral_sql  # noqa: E402

# D-028/D-015: beop·eup NULL + 구·addr4(처인구·양지읍) → region_codes LATERAL → canonical grain
_CANON = canonical_select_expr("t")
_RC_LATERAL = region_codes_lateral_sql("t", canon_beop_expr=_CANON)
_BEOP = "COALESCE(NULLIF(btrim(t.beopjungri_code::text), ''), NULLIF(btrim(rc.beopjungri_code::text), ''))"
_EUP = "COALESCE(NULLIF(btrim(t.eupmyeondong_code::text), ''), NULLIF(btrim(rc.eupmyeondong_code::text), ''))"
_SIG = "COALESCE(NULLIF(btrim(t.sigungu_code::text), ''), NULLIF(btrim(rc.sigungu_code::text), ''))"
_SIDO = "COALESCE(NULLIF(btrim(t.sido_code::text), ''), NULLIF(btrim(rc.sido_code::text), ''))"
_REGION_CODE_SQL = f"""
    {canonical_prefix_coalesce_sql(_BEOP, _EUP, _SIG, _SIDO, 8)} AS bcode8,
    {canonical_prefix_coalesce_sql(_BEOP, _EUP, _SIG, _SIDO, 5)} AS sigungu,
    {canonical_prefix_coalesce_sql(_BEOP, _EUP, _SIG, _SIDO, 2)} AS sido,
"""
_HAS_REGION = """
(
  NULLIF(btrim(t.beopjungri_code::text), '') IS NOT NULL
  OR NULLIF(btrim(t.eupmyeondong_code::text), '') IS NOT NULL
  OR rc.beopjungri_code IS NOT NULL
)
"""
_SIDO_FILTER = """
  AND COALESCE(NULLIF(btrim(t.sido_code::text), ''), NULLIF(btrim(rc.sido_code::text), '')) = :sido
"""

ROLLING_SQL = f"""
SELECT
{_REGION_CODE_SQL}
    t.asset_type,
    array_agg(
        CASE WHEN t.gross_area IS NOT NULL AND t.gross_area > 0
             THEN (t.price / t.gross_area) END
        ORDER BY t.price
    ) AS unit_prices
FROM built_transactions t
{_RC_LATERAL}
WHERE t.is_valid = true
  AND t.price IS NOT NULL AND t.price > 0
  AND {_HAS_REGION}
  AND t.contract_date IS NOT NULL
  AND t.contract_date >= :p_start
  AND t.contract_date <= :p_end
  {{sido_clause}}
GROUP BY 1, 2, 3, 4
"""

ANNUAL_SQL = f"""
SELECT
{_REGION_CODE_SQL}
    t.asset_type,
    t.contract_year,
    COUNT(*) AS raw_count,
    array_agg(
        CASE WHEN t.gross_area IS NOT NULL AND t.gross_area > 0
             THEN (t.price / t.gross_area) END
        ORDER BY t.price
    ) AS unit_prices,
    SUM(t.price) AS amount_sum
FROM built_transactions t
{_RC_LATERAL}
WHERE t.is_valid = true
  AND t.price IS NOT NULL AND t.price > 0
  AND {_HAS_REGION}
  AND t.contract_year IS NOT NULL
  {{sido_clause}}
GROUP BY 1, 2, 3, 4, 5
"""


def _distinct_sido(conn) -> list[str]:
    rows = conn.execute(
        text(
            "SELECT DISTINCT sido_code FROM built_transactions "
            "WHERE sido_code IS NOT NULL AND btrim(sido_code::text) <> '' ORDER BY 1"
        )
    ).fetchall()
    return [str(r[0]).strip() for r in rows if r[0]]


def _rollup_rolling(rows, *, as_of: date, window_years: int, ps: date, pe: date, batch_id: str) -> list[dict]:
    buckets: dict[tuple[str, str, str], list[float]] = {}
    for row in rows:
        domain = ASSET_DOMAINS.get(row["asset_type"])
        if not domain:
            continue
        prices = [float(x) for x in (row["unit_prices"] or []) if x is not None]
        if not prices:
            continue
        for level, rc in (
            ("eupmyeondong", (row.get("bcode8") or "").strip()),
            ("sigungu", (row.get("sigungu") or "").strip()),
            ("sido", (row.get("sido") or "").strip()),
        ):
            if not rc or not rc.isdigit():
                continue
            buckets.setdefault((domain, level, rc), []).extend(prices)

    out: list[dict] = []
    for (domain, level, rc), prices in buckets.items():
        st = compute_stats(prices)
        if st["count"] <= 0:
            continue
        out.append(
            {
                "market_domain": domain,
                "region_level": level,
                "region_code": rc,
                "as_of_month": as_of,
                "window_years": window_years,
                "period_start": ps,
                "period_end": pe,
                "count": st["count"],
                "mean": st["mean"],
                "std": st["std"],
                "ci_lower": st["ci_lower"],
                "ci_upper": st["ci_upper"],
                "p25": st["p25"],
                "median": st["median"],
                "p75": st["p75"],
                "yoy": None,
                "volatility": round(float(st["std"]) / float(st["mean"]), 4)
                if st["mean"] and st["std"] is not None and float(st["mean"]) > 0
                else None,
                "batch_id": batch_id,
            }
        )
    return out


def _rollup_annual(rows, *, batch_id: str) -> list[dict]:
    """거래건수는 raw row 수 기준(gross_area 결측 여부와 무관), 단가 통계는 gross_area>0 인 거래만."""
    prices_by_key: dict[tuple[str, str, str, int], list[float]] = {}
    amount_by_key: dict[tuple[str, str, str, int], float] = {}
    count_by_key: dict[tuple[str, str, str, int], int] = {}

    for row in rows:
        asset_type = row["asset_type"]
        if asset_type not in ASSET_DOMAINS:
            continue
        cy = int(row["contract_year"])
        prices = [float(x) for x in (row["unit_prices"] or []) if x is not None]
        amt = float(row["amount_sum"]) if row.get("amount_sum") is not None else 0.0
        raw_n = int(row["raw_count"] or 0)
        for level, rc in (
            ("eupmyeondong", (row.get("bcode8") or "").strip()),
            ("sigungu", (row.get("sigungu") or "").strip()),
            ("sido", (row.get("sido") or "").strip()),
        ):
            if not rc or not rc.isdigit():
                continue
            key = (asset_type, level, rc, cy)
            amount_by_key[key] = amount_by_key.get(key, 0.0) + amt
            count_by_key[key] = count_by_key.get(key, 0) + raw_n
            if prices:
                prices_by_key.setdefault(key, []).extend(prices)

    out: list[dict] = []
    for key, count in count_by_key.items():
        asset_type, level, rc, cy = key
        prices = prices_by_key.get(key, [])
        st = compute_stats(prices) if prices else None
        out.append(
            {
                "asset_type": asset_type,
                "region_level": level,
                "region_code": rc,
                "calendar_year": cy,
                "count": count,
                "amount_sum": round(amount_by_key.get(key, 0.0), 2),
                "mean": st["mean"] if st else None,
                "median": st["median"] if st else None,
                "std": st["std"] if st else None,
                "batch_id": batch_id,
            }
        )
    return out


def upsert_built_annual(records: list[dict], engine) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO built_annual_stats (
            asset_type, region_level, region_code, calendar_year,
            count, amount_sum, mean, median, std, computed_at, batch_id
        ) VALUES (
            :asset_type, :region_level, :region_code, :calendar_year,
            :count, :amount_sum, :mean, :median, :std, NOW(), :batch_id
        )
        ON CONFLICT (asset_type, region_level, region_code, calendar_year)
        DO UPDATE SET
            count = EXCLUDED.count,
            amount_sum = EXCLUDED.amount_sum,
            mean = EXCLUDED.mean,
            median = EXCLUDED.median,
            std = EXCLUDED.std,
            computed_at = NOW(),
            batch_id = EXCLUDED.batch_id
        """
    )
    with engine.begin() as conn:
        for rec in records:
            conn.execute(sql, rec)


def ensure_built_annual_table(engine) -> None:
    ddl_path = REPO / "db" / "042_built_annual_stats.sql"
    if not ddl_path.is_file():
        return
    with engine.begin() as conn:
        conn.execute(text(ddl_path.read_text(encoding="utf-8")))


def build_rolling(built_eng, coll_eng, *, as_of: date, windows: list[int], sido_filter: str | None, batch_id: str) -> int:
    total = 0
    with built_eng.connect() as conn:
        sidos = [sido_filter] if sido_filter else _distinct_sido(conn)

    for wy in windows:
        ps, pe = period_bounds_for_window(as_of, wy)
        log.info("built market window=%sy period=%s..%s", wy, ps, pe)
        for sc in tqdm(sidos, desc=f"built-mkt-w{wy}"):
            params = {"p_start": ps, "p_end": pe, "sido": sc}
            with built_eng.connect() as conn:
                rows = conn.execute(
                    text(ROLLING_SQL.format(sido_clause=_SIDO_FILTER)),
                    params,
                ).mappings().all()
            records = _rollup_rolling(rows, as_of=as_of, window_years=wy, ps=ps, pe=pe, batch_id=batch_id)
            upsert_market_stats(records, coll_eng)
            total += len(records)
    return total


def build_annual(built_eng, *, sido_filter: str | None, batch_id: str) -> int:
    ensure_built_annual_table(built_eng)
    total = 0
    with built_eng.connect() as conn:
        sidos = [sido_filter] if sido_filter else _distinct_sido(conn)

    for sc in tqdm(sidos, desc="built-annual"):
        params = {"sido": sc}
        with built_eng.connect() as conn:
            rows = conn.execute(
                text(ANNUAL_SQL.format(sido_clause=_SIDO_FILTER)),
                params,
            ).mappings().all()
        rows = [dict(r) for r in rows]
        records = _rollup_annual(rows, batch_id=batch_id)
        upsert_built_annual(records, built_eng)
        total += len(records)
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="상업업무/공장창고/단독다가구 market_stats + built_annual_stats")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--windows", type=str, default="3,5")
    p.add_argument("--sido-code", type=str, default=None, help="시도 2자리 스모크")
    p.add_argument("--rolling-only", action="store_true")
    p.add_argument("--annual-only", action="store_true")
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = sorted({int(x.strip()) for x in args.windows.split(",") if x.strip()})
    sido = str(args.sido_code).strip() if args.sido_code else None
    batch_id = str(uuid.uuid4())

    built_eng = get_built_engine()
    coll_eng = get_collective_engine()

    with built_eng.connect() as conn:
        tx_n = conn.execute(text("SELECT COUNT(*) FROM built_transactions")).scalar()
    log.info("built_transactions rows=%s as_of=%s", tx_n, as_of)
    if not tx_n:
        raise SystemExit("built_transactions empty")

    if not args.annual_only:
        n = build_rolling(built_eng, coll_eng, as_of=as_of, windows=windows, sido_filter=sido, batch_id=batch_id)
        log.info("market_stats(built domains) upserted ~%s rows", n)

    if not args.rolling_only:
        n = build_annual(built_eng, sido_filter=sido, batch_id=batch_id)
        log.info("built_annual_stats upserted ~%s rows", n)


if __name__ == "__main__":
    main()
