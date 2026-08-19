#!/usr/bin/env python3
"""
집합(주거) 2단계 특성회귀 + 블록 L mart.

  py pipeline/build_collective_attribute_effects.py --as-of 2026-07-01 --windows 5 --specs A,B,C,L --replace
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from app.collective.hedonic.constants import DEFAULT_ASSET_TYPE  # noqa: E402
from app.collective.hedonic.stage2 import run_attribute_effects, run_block_l_macro  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SIDO_MIN_BUILDINGS = 200


def _load_stage2(engine, as_of: date, wy: int) -> pd.DataFrame:
    snap = engine.connect().execute(text("SELECT MAX(snapshot_ym) FROM collective_building_attributes")).scalar()
    sql = text(
        """
        SELECT q.building_key, q.sigungu_code, q.quality_index, q.quality_se,
               LEFT(q.sigungu_code, 2) AS sido_code,
               a.match_tier, a.brand, a.builder_group, a.structure_group,
               a.households, a.max_floor, a.parking_per_household,
               a.approved_year, a.building_year, a.danji_class, a.supply_type,
               a.danji_code, a.attr_quality_flags, a.n_tx,
               e.eup_population, e.rent_jeonse_p50, e.land_p50_zone
        FROM collective_building_quality_index q
        JOIN collective_building_attributes a
          ON a.building_key = q.building_key AND a.asset_type = q.asset_type
         AND a.snapshot_ym = :snap
        LEFT JOIN collective_building_location_enrichment e
          ON e.building_key = q.building_key
         AND e.as_of_month = q.as_of_month
         AND e.window_years = q.window_years
         AND e.asset_type = q.asset_type
        WHERE q.as_of_month = :as_of AND q.window_years = :wy AND q.asset_type = :at
        """
    )
    return pd.read_sql(sql, engine, params={"as_of": as_of, "wy": wy, "at": DEFAULT_ASSET_TYPE, "snap": snap})


def _macro_frame(base_engine, land_engine, as_of: date, wy: int) -> pd.DataFrame:
    base = pd.read_sql(
        text(
            """
            SELECT sigungu_code, base_ln_price
            FROM collective_sigungu_base_level
            WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
            """
        ),
        base_engine,
        params={"as_of": as_of, "wy": wy, "at": DEFAULT_ASSET_TYPE},
    )
    pop = pd.read_sql(
        text(
            """
            SELECT LEFT(beopjungri_code, 5) AS sigungu_code, SUM(total_population) AS sigungu_population
            FROM population_stats
            GROUP BY 1
            """
        ),
        land_engine,
    )
    land = pd.read_sql(
        text(
            """
            SELECT region_code AS sigungu_code, median AS sigungu_land_p50
            FROM land_upper_stats_v2
            WHERE region_level = 'sigungu'
              AND as_of_month = :as_of AND window_years = :wy
              AND zone_type = '제2종일반주거지역' AND land_category = '대'
            """
        ),
        land_engine,
        params={"as_of": as_of, "wy": wy},
    )
    rent = pd.read_sql(
        text(
            """
            SELECT sigungu_code,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY jeonse_median) AS sigungu_rent_p50
            FROM rent_building_stats
            WHERE asset_type = :at AND as_of_month = :as_of AND window_years = :wy
              AND jeonse_median IS NOT NULL AND sigungu_code IS NOT NULL
            GROUP BY sigungu_code
            """
        ),
        base_engine,
        params={"at": DEFAULT_ASSET_TYPE, "as_of": as_of, "wy": wy},
    )
    out = base.merge(pop, on="sigungu_code", how="left")
    out = out.merge(land, on="sigungu_code", how="left")
    out = out.merge(rent, on="sigungu_code", how="left")
    return out


def _delete_snapshot(engine, as_of: date, wy: int, specs: list[str]) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM collective_attribute_effects
                WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
                  AND spec = ANY(:specs)
                """
            ),
            {"as_of": as_of, "wy": wy, "at": DEFAULT_ASSET_TYPE, "specs": specs},
        )
        conn.execute(
            text(
                """
                DELETE FROM collective_attribute_effects_model
                WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
                  AND spec = ANY(:specs)
                """
            ),
            {"as_of": as_of, "wy": wy, "at": DEFAULT_ASSET_TYPE, "specs": specs},
        )


def _persist(engine, as_of: date, wy: int, result, *, include_location: bool) -> None:
    coef_rows = []
    for c in result.coefficients:
        coef_rows.append(
            {
                "as_of_month": as_of,
                "window_years": wy,
                "asset_type": DEFAULT_ASSET_TYPE,
                "spec": result.spec,
                "scope_level": result.scope_level,
                "scope_code": result.scope_code,
                **c,
            }
        )
    model_row = {
        "as_of_month": as_of,
        "window_years": wy,
        "asset_type": DEFAULT_ASSET_TYPE,
        "spec": result.spec,
        "scope_level": result.scope_level,
        "scope_code": result.scope_code,
        "include_location": include_location,
        "weighting": result.weighting,
        "n_buildings": result.n_buildings,
        "adj_r_squared": result.adj_r_squared,
        "equation": result.equation,
        "warnings": "\n".join(result.warnings),
        "sample_breakdown": json.dumps(result.sample_breakdown, ensure_ascii=False),
        "reference_categories": json.dumps(result.reference_categories, ensure_ascii=False),
    }
    if coef_rows:
        cols = list(coef_rows[0].keys())
        ph = ", ".join(f":{c}" for c in cols)
        with engine.begin() as conn:
            conn.execute(
                text(f"INSERT INTO collective_attribute_effects ({', '.join(cols)}) VALUES ({ph})"),
                coef_rows,
            )
    cols = list(model_row.keys())
    ph = ", ".join(f":{c}" for c in cols)
    with engine.begin() as conn:
        conn.execute(
            text(f"INSERT INTO collective_attribute_effects_model ({', '.join(cols)}) VALUES ({ph})"),
            [model_row],
        )


def main() -> None:
    p = argparse.ArgumentParser(description="집합 2단계 특성회귀 mart")
    p.add_argument("--as-of", dest="as_of", default=None)
    p.add_argument("--windows", type=int, default=5)
    p.add_argument("--specs", default="A,B,C,L")
    p.add_argument("--with-location", action="store_true", help="위치 블록 포함 스펙 A 추가 저장")
    p.add_argument("--replace", action="store_true")
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    specs = [s.strip().upper() for s in args.specs.split(",") if s.strip()]
    coll = get_collective_engine()
    land = get_land_engine_for_region_copy()

    df = _load_stage2(coll, as_of, args.windows)
    if df.empty:
        log.error("stage2 입력 없음 — quality index + attributes 필요")
        sys.exit(1)

    if args.replace:
        _delete_snapshot(coll, as_of, args.windows, specs)

    for spec in specs:
        if spec == "L":
            base = pd.read_sql(
                text(
                    """
                    SELECT sigungu_code, base_ln_price
                    FROM collective_sigungu_base_level
                    WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
                    """
                ),
                coll,
                params={"as_of": as_of, "wy": args.windows, "at": DEFAULT_ASSET_TYPE},
            )
            macro = _macro_frame(coll, land, as_of, args.windows)
            result = run_block_l_macro(base, macro, as_of_month=as_of, window_years=args.windows)
            _persist(coll, as_of, args.windows, result, include_location=False)
            log.info("block L: n_sigungu=%s adj_r2=%s", result.n_buildings, result.adj_r_squared)
            continue

        result = run_attribute_effects(df, spec=spec, scope_level="national")
        _persist(coll, as_of, args.windows, result, include_location=False)
        log.info("spec %s national: n=%s adj_r2=%s", spec, result.n_buildings, result.adj_r_squared)

        if args.with_location and spec == "A":
            loc = run_attribute_effects(
                df,
                spec=spec,
                scope_level="national",
                include_location=True,
                include_terms={
                    "brand",
                    "scale",
                    "structure",
                    "vintage",
                    "parking",
                    "danji_class",
                    "max_floor",
                    "eup_population",
                    "rent_jeonse_p50",
                    "land_p50_zone",
                },
            )
            _persist(coll, as_of, args.windows, loc, include_location=True)
            log.info("spec A+location: n=%s adj_r2=%s", loc.n_buildings, loc.adj_r_squared)

        for sido, cnt in df.groupby("sido_code").size().items():
            if int(cnt) < SIDO_MIN_BUILDINGS:
                continue
            sido_res = run_attribute_effects(
                df,
                spec=spec,
                scope_level="sido",
                scope_code=str(sido),
            )
            _persist(coll, as_of, args.windows, sido_res, include_location=False)
            log.info("spec %s sido %s: n=%s", spec, sido, sido_res.n_buildings)


if __name__ == "__main__":
    main()
