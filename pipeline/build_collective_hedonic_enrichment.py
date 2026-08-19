#!/usr/bin/env python3
"""
집합(주거) 2단계 위치 블록 enrichment — 읍 인구·임대 P50·AL_D155 UQA→토지 P50.

  py pipeline/build_collective_hedonic_enrichment.py --as-of 2026-07-01 --windows 5 --replace
  py pipeline/report_ald155_apartment_pilot.py --as-of 2026-07-01 --output pipeline/rent/_ald155_apartment_pilot.json
"""

from __future__ import annotations

import argparse
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
from app.collective.hedonic.enrichment import (  # noqa: E402
    discover_ald155_dirs,
    fetch_land_p50_for_zones,
    load_ald155_uqa,
    load_apartment_buildings,
    resolve_uqa_for_buildings,
    run_ald155_pilot,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _latest_snapshot(conn) -> str:
    return str(
        conn.execute(text("SELECT MAX(snapshot_ym) FROM collective_building_attributes")).scalar()
    )


def _population_map(land_engine, eup_codes: list[str]) -> dict[str, float]:
    if not eup_codes:
        return {}
    sql = text(
        """
        SELECT LEFT(beopjungri_code, 8) AS eup, SUM(total_population) AS pop
        FROM population_stats
        WHERE LEFT(beopjungri_code, 8) = ANY(:codes)
        GROUP BY 1
        """
    )
    try:
        df = pd.read_sql(sql, land_engine, params={"codes": list(set(eup_codes))})
        return {str(r["eup"]): float(r["pop"]) for _, r in df.iterrows()}
    except Exception as exc:  # noqa: BLE001
        log.warning("population_stats 조회 실패: %s", exc)
        return {}


def _rent_p50_map(collective_engine, as_of: date, wy: int) -> dict[str, float]:
    sql = text(
        """
        SELECT m.sale_building_key AS building_key, r.jeonse_median AS rent_jeonse_p50
        FROM rent_sale_building_map m
        JOIN rent_building_stats r
          ON r.building_key = m.rent_building_key
         AND r.asset_type = m.asset_type
        WHERE m.asset_type = :at
          AND r.as_of_month = :as_of
          AND r.window_years = :wy
          AND r.jeonse_median IS NOT NULL
        """
    )
    try:
        df = pd.read_sql(
            sql,
            collective_engine,
            params={"at": DEFAULT_ASSET_TYPE, "as_of": as_of, "wy": wy},
        )
        return {str(r["building_key"]): float(r["rent_jeonse_p50"]) for _, r in df.iterrows()}
    except Exception as exc:  # noqa: BLE001
        log.warning("rent_building_stats 조회 실패: %s", exc)
        return {}


def build_enrichment(
    *,
    as_of: date,
    window_years: int,
    replace: bool,
    raw_root: Path,
    run_pilot: bool,
    pilot_output: Path | None,
) -> None:
    coll = get_collective_engine()
    land = get_land_engine_for_region_copy()

    if run_pilot:
        report = run_ald155_pilot(
            coll,
            raw_root,
            land_engine=land,
            as_of_month=as_of,
            window_years=window_years,
            output_json=pilot_output,
        )
        log.info("AL_D155 pilot: %s", report.to_dict())

    dirs = discover_ald155_dirs(raw_root)
    pilot_sidos = sorted({d.name.split("_")[1][:2] for d in dirs if "AL_D155_" in d.name})
    ald = pd.concat([load_ald155_uqa(d) for d in dirs], ignore_index=True) if dirs else pd.DataFrame()

    with coll.connect() as conn:
        snap = _latest_snapshot(conn)
        qi = pd.read_sql(
            text(
                """
                SELECT q.building_key, q.sigungu_code,
                       t.beopjungri_code, t.lot_number
                FROM collective_building_quality_index q
                JOIN (
                    SELECT building_key,
                           MAX(beopjungri_code) AS beopjungri_code,
                           MAX(lot_number) AS lot_number
                    FROM collective_transactions
                    GROUP BY building_key
                ) t ON t.building_key = q.building_key
                WHERE q.as_of_month = :as_of AND q.window_years = :wy AND q.asset_type = :at
                """
            ),
            conn,
            params={"as_of": as_of, "wy": window_years, "at": DEFAULT_ASSET_TYPE},
        )

    if qi.empty:
        log.warning("품질지수 mart 없음 — build_collective_quality_index.py 먼저 실행")
        return

    if not ald.empty and pilot_sidos:
        qi = qi[qi["beopjungri_code"].str[:2].isin(pilot_sidos)]
        resolved = resolve_uqa_for_buildings(qi, ald)
    else:
        resolved = qi.copy()
        resolved["uqa_code"] = None
        resolved["uqa_label"] = None
        resolved["zone_resolution"] = "missing"

    pop_map = _population_map(land, resolved["beopjungri_code"].dropna().astype(str).str[:8].tolist())
    rent_map = _rent_p50_map(coll, as_of, window_years)

    rows: list[dict] = []
    for _, r in resolved.iterrows():
        eup = str(r["beopjungri_code"])[:8] if pd.notna(r.get("beopjungri_code")) else None
        land_p50 = None
        if r.get("uqa_label") and eup:
            land_p50, _cnt = fetch_land_p50_for_zones(
                land,
                as_of_month=as_of,
                window_years=window_years,
                eup_code=eup,
                zone_label=str(r["uqa_label"]),
            )
        rows.append(
            {
                "as_of_month": as_of,
                "window_years": window_years,
                "asset_type": DEFAULT_ASSET_TYPE,
                "building_key": r["building_key"],
                "beopjungri_code": r.get("beopjungri_code"),
                "lot_number": r.get("lot_number"),
                "eup_population": pop_map.get(eup) if eup else None,
                "rent_jeonse_p50": rent_map.get(str(r["building_key"])),
                "uqa_code": r.get("uqa_code"),
                "uqa_label": r.get("uqa_label"),
                "land_p50_zone": land_p50,
                "zone_resolution": r.get("zone_resolution") or "missing",
                "pilot_sido_code": str(r["beopjungri_code"])[:2] if pd.notna(r.get("beopjungri_code")) else None,
            }
        )

    if replace:
        with coll.begin() as conn:
            conn.execute(
                text(
                    """
                    DELETE FROM collective_building_location_enrichment
                    WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
                    """
                ),
                {"as_of": as_of, "wy": window_years, "at": DEFAULT_ASSET_TYPE},
            )

    if rows:
        cols = list(rows[0].keys())
        ph = ", ".join(f":{c}" for c in cols)
        sql = text(
            f"INSERT INTO collective_building_location_enrichment ({', '.join(cols)}) VALUES ({ph})"
        )
        with coll.begin() as conn:
            for i in range(0, len(rows), 400):
                conn.execute(sql, rows[i : i + 400])
    log.info("location enrichment upserted: %s rows", len(rows))


def main() -> None:
    p = argparse.ArgumentParser(description="집합 헤도닉 위치 enrichment + AL_D155 파일럿")
    p.add_argument("--as-of", dest="as_of", default=None)
    p.add_argument("--windows", type=int, default=5)
    p.add_argument("--replace", action="store_true")
    p.add_argument("--raw-root", default=str(REPO / "raw"))
    p.add_argument("--pilot-only", action="store_true")
    p.add_argument(
        "--pilot-output",
        default=str(REPO / "pipeline" / "rent" / "_ald155_apartment_pilot.json"),
    )
    args = p.parse_args()
    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()

    if args.pilot_only:
        coll = get_collective_engine()
        land = get_land_engine_for_region_copy()
        run_ald155_pilot(
            coll,
            Path(args.raw_root),
            land_engine=land,
            as_of_month=as_of,
            window_years=args.windows,
            output_json=Path(args.pilot_output),
        )
        return

    build_enrichment(
        as_of=as_of,
        window_years=args.windows,
        replace=args.replace,
        raw_root=Path(args.raw_root),
        run_pilot=True,
        pilot_output=Path(args.pilot_output),
    )


if __name__ == "__main__":
    main()
