"""읍면동×용도×지목 중앙단가 — 전국 5년 창 1회 스캔.

배치 전량 스캔이라 `ANY` 핫패스 규칙의 예외(파이프라인).
지목·용도는 고정 `IN` 목록이다. 원장 `beopjungri_code = ANY` 는 쓰지 않는다.

재실행 (backend에서):
  python -m app.land_lab.road_jimok_ratio_screen
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.land_lab.area_elasticity import AREA_MAX_SQM, WINDOW_YEARS
from app.land_lab.area_elasticity_screen import latest_as_of_month, period_bounds_for_window
from app.land_lab.road_jimok_ratio import (
    GREENBELT_ZONES,
    NONURBAN_ZONES,
    URBAN_ZONES,
    build_screen,
)
from app.region_canonical import region_codes_join_on_canonical
from app.region_sido import is_retired_sido_code, is_retired_sido_name

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "land_road_jimok_ratio_screen.json"

_ZONES = tuple(sorted(URBAN_ZONES | NONURBAN_ZONES | GREENBELT_ZONES))
_ZONE_SQL = ", ".join(f"'{z}'" for z in _ZONES)
_JIMOK_SQL = "'도', '도로', '대', '전', '답'"


def fetch_agg(
    db: Session,
    *,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    sql = f"""
        SELECT
            btrim(r.sido_code::text) AS sido_code,
            btrim(r.sido_name::text) AS sido_name,
            btrim(r.sigungu_name::text) AS sigungu_name,
            btrim(r.eupmyeondong_code::text) AS eup_code,
            btrim(r.eupmyeondong_name::text) AS eup_name,
            btrim(lt.zone_type_resolved::text) AS zone_type,
            btrim(lt.land_category_resolved::text) AS land_category,
            COUNT(*)::int AS n,
            percentile_cont(0.5) WITHIN GROUP (
                ORDER BY lt.unit_price_per_sqm
            )::float8 AS p50,
            avg(lt.unit_price_per_sqm)::float8 AS mean_px
        FROM land_transactions_resolved lt
        {join_sql}
        WHERE lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND COALESCE(lt.is_partial_ownership, FALSE) = FALSE
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.area_sqm < :area_max
          AND lt.unit_price_per_sqm > 0
          AND btrim(COALESCE(lt.beopjungri_code::text, '')) <> ''
          AND btrim(lt.land_category_resolved::text) IN ({_JIMOK_SQL})
          AND btrim(lt.zone_type_resolved::text) IN ({_ZONE_SQL})
          AND btrim(COALESCE(r.eupmyeondong_code::text, '')) <> ''
        GROUP BY 1, 2, 3, 4, 5, 6, 7
    """
    rows = db.execute(
        text(sql),
        {
            "p_start": period_start,
            "p_end": period_end,
            "area_max": AREA_MAX_SQM,
        },
    ).mappings().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        if is_retired_sido_code(str(d.get("sido_code") or "")):
            continue
        if is_retired_sido_name(str(d.get("sido_name") or "")):
            continue
        out.append(d)
    return out


def run_screen(*, as_of_month: date | None = None, window_years: int = WINDOW_YEARS) -> dict[str, Any]:
    db = SessionLocal()
    try:
        as_of = as_of_month or latest_as_of_month(db)
        start, end = period_bounds_for_window(as_of, window_years)
        aggs = fetch_agg(db, period_start=start, period_end=end)
    finally:
        db.close()
    return build_screen(
        aggs,
        as_of_month=as_of.isoformat()[:7],
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        window_years=window_years,
    )


def write_payload(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    p = argparse.ArgumentParser(description="도로 지목 상대가격 1차 스냅샷")
    p.add_argument("--as-of", default="", help="YYYY-MM-01. 비우면 원장 최신월")
    p.add_argument("--window", type=int, default=WINDOW_YEARS)
    p.add_argument("--out", default=str(OUT))
    args = p.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    payload = run_screen(as_of_month=as_of, window_years=int(args.window))
    write_payload(payload, Path(args.out))
    bits = []
    for band in payload["bands"]:
        cut = band["cuts"]["10"]
        bits.append(f"{band['id']}={cut['n_cells']} r50={cut['r_p50']}")
    print(" ".join(bits), flush=True)
    print(f"cells={len(payload['cells'])} wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
