"""시군구×지목 적격 표 — 전국 5년 창 1회 스캔.

배치 전량 스캔이라 `ANY` 핫패스 규칙의 예외(파이프라인). 칸 거래 조회는
canonical 조인 + 시군구 `=` (원장 `beopjungri_code = ANY` 금지).

재실행 (backend에서):
  python -m app.land_lab.area_elasticity_screen
  python -m app.land_lab.area_elasticity_screen --screen-only
"""
from __future__ import annotations

import argparse
import csv
import json
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.land_lab.area_elasticity import (
    AREA_MAX_SQM,
    LAND_CATEGORIES,
    PHASE1_PER_TYPE,
    WINDOW_YEARS,
    CellRow,
    cell_from_agg,
    select_phase1,
)
from app.region_canonical import canonical_select_expr, region_codes_join_on_canonical
from app.region_sido import is_retired_sido_code, is_retired_sido_name

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "land_area_elasticity_screen.json"
KEEP_LAB_KEYS = (
    "verdict",
    "answers",
    "next",
    "limits",
    "resume",
    "phase2",
    "phase2_rows",
    "phase2_csv",
    "phase3",
    "phase3_csv",
)


def period_bounds_for_window(as_of_month: date, window_years: int) -> tuple[date, date]:
    if as_of_month.day != 1:
        raise ValueError(f"as_of_month 는 월 1일이어야 합니다: {as_of_month}")
    last = monthrange(as_of_month.year, as_of_month.month)[1]
    period_end = date(as_of_month.year, as_of_month.month, last)
    y = period_end.year - window_years
    day = min(period_end.day, monthrange(y, period_end.month)[1])
    anchor = date(y, period_end.month, day)
    return anchor + timedelta(days=1), period_end


def latest_as_of_month(conn: Connection) -> date:
    raw = conn.execute(
        text(
            """
            SELECT MAX(contract_date)::date
            FROM land_transactions
            WHERE is_valid = TRUE
              AND is_cancelled = FALSE
              AND contract_date IS NOT NULL
            """
        )
    ).scalar()
    if raw is None:
        raise RuntimeError("원장 contract_date 없음")
    d = raw if isinstance(raw, date) else date.fromisoformat(str(raw)[:10])
    return date(d.year, d.month, 1)


def build_screen_sql(join_sql: str) -> str:
    cats = ", ".join(f"'{c}'" for c in LAND_CATEGORIES)
    return f"""
WITH base AS (
    SELECT
        btrim(r.sido_code::text) AS sido_code,
        btrim(r.sido_name::text) AS sido_name,
        btrim(r.sigungu_code::text) AS sigungu_code,
        btrim(r.sigungu_name::text) AS sigungu_name,
        btrim(r.eupmyeondong_code::text) AS eup_code,
        btrim(lt.land_category_resolved::text) AS land_category,
        lt.area_sqm::float8 AS area_sqm
    FROM land_transactions_resolved lt
    {join_sql}
    WHERE lt.is_valid = TRUE
      AND lt.is_cancelled = FALSE
      AND COALESCE(lt.is_partial_ownership, FALSE) = FALSE
      AND lt.contract_date IS NOT NULL
      AND lt.contract_date >= :p_start
      AND lt.contract_date <= :p_end
      AND lt.area_sqm > 0
      AND lt.area_sqm < :area_max
      AND lt.unit_price_per_sqm > 0
      AND btrim(COALESCE(lt.beopjungri_code::text, '')) <> ''
      AND btrim(lt.land_category_resolved::text) IN ({cats})
),
dong AS (
    SELECT sigungu_code, land_category, eup_code, COUNT(*)::int AS n_dong
    FROM base
    GROUP BY sigungu_code, land_category, eup_code
),
dong_med AS (
    SELECT
        sigungu_code,
        land_category,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY n_dong) AS dong_n_median
    FROM dong
    GROUP BY sigungu_code, land_category
),
cell AS (
    SELECT
        sido_code,
        sido_name,
        sigungu_code,
        sigungu_name,
        land_category,
        COUNT(*)::int AS n,
        percentile_cont(0.10) WITHIN GROUP (ORDER BY area_sqm) AS area_p10,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY area_sqm) AS area_p50,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY area_sqm) AS area_p75,
        percentile_cont(0.90) WITHIN GROUP (ORDER BY area_sqm) AS area_p90,
        COUNT(*) FILTER (WHERE area_sqm >= 300)::int AS n_ge_300,
        COUNT(*) FILTER (WHERE area_sqm >= 500)::int AS n_ge_500,
        COUNT(*) FILTER (WHERE area_sqm >= 1000)::int AS n_ge_1000,
        COUNT(*) FILTER (WHERE area_sqm >= 3000)::int AS n_ge_3000,
        COUNT(*) FILTER (WHERE area_sqm >= 5000)::int AS n_ge_5000,
        COUNT(DISTINCT eup_code)::int AS n_dongs
    FROM base
    GROUP BY sido_code, sido_name, sigungu_code, sigungu_name, land_category
)
SELECT
    c.sido_code,
    c.sido_name,
    c.sigungu_code,
    c.sigungu_name,
    c.land_category,
    c.n,
    c.area_p10,
    c.area_p50,
    c.area_p75,
    c.area_p90,
    c.n_ge_300,
    c.n_ge_500,
    c.n_ge_1000,
    c.n_ge_3000,
    c.n_ge_5000,
    c.n_dongs,
    m.dong_n_median
FROM cell c
LEFT JOIN dong_med m
  ON m.sigungu_code = c.sigungu_code
 AND m.land_category = c.land_category
ORDER BY c.sido_code, c.sigungu_code, c.land_category
"""


def fetch_screen_rows(
    conn: Connection,
    *,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    sql = build_screen_sql(join_sql)
    rows = conn.execute(
        text(sql),
        {
            "p_start": period_start,
            "p_end": period_end,
            "area_max": AREA_MAX_SQM,
        },
    ).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        if is_retired_sido_code(str(d.get("sido_code") or "")):
            continue
        if is_retired_sido_name(str(d.get("sido_name") or "")):
            continue
        out.append(d)
    return out


def fetch_cell_transactions(
    db: Session,
    *,
    sigungu_code: str,
    land_category: str,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    """시군구 칸 거래. canonical 조인 + sigungu `=`. 원장 beopjungri ANY 금지."""
    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    code_expr = canonical_select_expr("lt")
    sql = f"""
        SELECT
            ({code_expr}) AS beopjungri_code,
            lt.road_condition,
            lt.contract_year::int AS contract_year,
            lt.area_sqm::float8 AS area_sqm,
            lt.unit_price_per_sqm::float8 AS unit_price_per_sqm
        FROM land_transactions_resolved lt
        {join_sql}
        WHERE btrim(r.sigungu_code::text) = :sg
          AND lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND COALESCE(lt.is_partial_ownership, FALSE) = FALSE
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.area_sqm < :area_max
          AND lt.unit_price_per_sqm > 0
          AND btrim(lt.land_category_resolved::text) = :cat
    """
    rows = db.execute(
        text(sql),
        {
            "sg": str(sigungu_code).strip(),
            "p_start": period_start,
            "p_end": period_end,
            "area_max": AREA_MAX_SQM,
            "cat": land_category,
        },
    ).mappings().all()
    return [dict(r) for r in rows]


def _summarize(cells: list[CellRow], phase1: list[CellRow]) -> dict[str, Any]:
    eligible = [c for c in cells if c.eligible]
    by_type: dict[str, dict[str, int]] = {}
    for c in cells:
        slot = by_type.setdefault(
            c.region_type, {"cells": 0, "eligible": 0, "phase1": 0}
        )
        slot["cells"] += 1
        if c.eligible:
            slot["eligible"] += 1
    for c in phase1:
        by_type.setdefault(c.region_type, {"cells": 0, "eligible": 0, "phase1": 0})
        by_type[c.region_type]["phase1"] += 1
    return {
        "n_cells": len(cells),
        "n_eligible": len(eligible),
        "n_phase1": len(phase1),
        "by_type": by_type,
    }


def run_screen(
    *,
    as_of_month: date | None = None,
    window_years: int = WINDOW_YEARS,
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        if as_of_month is None:
            as_of_month = latest_as_of_month(db)
        period_start, period_end = period_bounds_for_window(as_of_month, window_years)
        raw = fetch_screen_rows(db, period_start=period_start, period_end=period_end)
        cells = [cell_from_agg(r) for r in raw]
        phase1 = select_phase1(cells, per_type=PHASE1_PER_TYPE)
        payload = {
            "run_id": "land-area-elasticity-screen",
            "date": date.today().isoformat(),
            "status": "screened",
            "product_change": False,
            "window_years": window_years,
            "as_of_month": as_of_month.isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "area_max_sqm": AREA_MAX_SQM,
            "selection": "n_and_area_spectrum_only",
            "summary": _summarize(cells, phase1),
            "phase1": [c.to_dict() for c in phase1],
            "cells": [c.to_dict() for c in cells],
        }
        return payload
    finally:
        db.close()


def write_payload(payload: dict[str, Any], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old: dict[str, Any] = {}
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = {}
    cells = payload.get("cells") or []
    csv_path = path.with_suffix(".csv")
    if cells:
        fields = list(cells[0].keys())
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(cells)
    slim = {k: v for k, v in payload.items() if k != "cells"}
    slim["cells_csv"] = csv_path.name
    for key in KEEP_LAB_KEYS:
        if key not in slim and key in old:
            slim[key] = old[key]
    path.write_text(
        json.dumps(slim, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    p = argparse.ArgumentParser(description="토지 면적 탄성 적격 표")
    p.add_argument("--as-of", default="", help="YYYY-MM-01. 비우면 원장 최신월")
    p.add_argument("--window", type=int, default=WINDOW_YEARS)
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--screen-only", action="store_true")
    args = p.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    payload = run_screen(as_of_month=as_of, window_years=int(args.window))
    if not args.screen_only:
        from app.land_lab.area_elasticity_fit import attach_phase1_fits

        payload = attach_phase1_fits(payload, engine_bind=engine)
    write_payload(payload, Path(args.out))
    s = payload["summary"]
    print(
        f"cells={s['n_cells']} eligible={s['n_eligible']} phase1={s['n_phase1']}",
        flush=True,
    )
    print(f"wrote {args.out}", flush=True)
    csv_path = Path(args.out).with_suffix(".csv")
    if csv_path.exists():
        print(f"csv {csv_path}", flush=True)
    if payload.get("phase1_fits"):
        print(f"fits={len(payload['phase1_fits'])}", flush=True)


if __name__ == "__main__":
    main()
