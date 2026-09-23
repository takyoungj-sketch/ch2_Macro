"""오피스텔 층 효용 1차 — 저층=100 단가 가운데값.

회귀 없음. 1층=100 없음. 아파트도 같은 식으로 다시 계산한다.
재실행 (backend에서): python -m app.officetel_floor_lab.ratio
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.apt_floor_lab.screen import (
    BAND_LABELS,
    BAND_ORDER,
    N_MIN,
    OTHER_BIN_MIN,
    REPORT_MIN_BUILDINGS,
    height_band,
    latest_as_of_month,
)
from app.collective.db import get_collective_engine
from app.land_lab.area_elasticity_screen import period_bounds_for_window

ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "lab" / "officetel_floor_utility_phase1.json"

ASSETS = ("officetel", "apartment")
PROFILE_BINS = ("mid", "high", "top")
ALL_BINS = ("mid", "high", "top", "top_over_high")
BIN_LABELS = {
    "mid": "중층",
    "high": "고층",
    "top": "최상",
    "top_over_high": "최상/고층",
}
CLOSED_CELLS = {("ge26", "top"), ("ge26", "top_over_high")}
INTEREST_POINTS = 10.0

RATIO_SQL = """
    WITH tx AS (
        SELECT
            t.building_key,
            t.floor,
            t.unit_price
        FROM collective_transactions t
        WHERE t.asset_type = :asset
          AND t.is_valid IS TRUE
          AND t.contract_date >= :p_start
          AND t.contract_date <= :p_end
          AND t.unit_price > 0
          AND t.exclusive_area > 0
          AND t.floor >= 1
          AND t.building_key IS NOT NULL
          AND t.building_key <> ''
    ),
    mx AS (
        SELECT building_key, MAX(floor)::float8 AS max_floor
        FROM tx
        GROUP BY building_key
    ),
    binned AS (
        SELECT
            t.building_key,
            m.max_floor,
            CASE
                WHEN t.floor = 1 THEN 'f1'
                WHEN t.floor = m.max_floor THEN 'top'
                WHEN (t.floor::float8 / m.max_floor) <= 0.30 THEN 'low'
                WHEN (t.floor::float8 / m.max_floor) <= 0.70 THEN 'mid'
                ELSE 'high'
            END AS bin,
            t.unit_price
        FROM tx t
        JOIN mx m ON m.building_key = t.building_key
        WHERE m.max_floor >= 2
    )
    SELECT
        building_key,
        max_floor,
        bin,
        COUNT(*)::int AS n_bin,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price) AS med
    FROM binned
    GROUP BY building_key, max_floor, bin
"""


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float | None:
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    v = values[mask]
    w = weights[mask]
    if len(v) == 0:
        return None
    order = np.argsort(v, kind="mergesort")
    v = v[order]
    w = w[order]
    cutoff = float(w.sum()) * 0.5
    return float(v[int(np.searchsorted(np.cumsum(w), cutoff, side="left"))])


def _index(med_bin: float | None, n_bin: int, med_base: float | None, n_base: int) -> float | None:
    if n_bin < OTHER_BIN_MIN or n_base < OTHER_BIN_MIN:
        return None
    if med_bin is None or med_base is None or med_base <= 0 or med_bin <= 0:
        return None
    return float(100.0 * med_bin / med_base)


def rows_to_buildings(bin_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """건물×칸 집계를 저층=100 지수 행으로 만든다. 가격은 남기지 않는다."""
    by_key: dict[str, dict[str, Any]] = {}
    for raw in bin_rows:
        key = str(raw["building_key"]).strip()
        slot = by_key.setdefault(
            key,
            {"building_key": key, "max_floor": float(raw["max_floor"]), "bins": {}},
        )
        slot["bins"][str(raw["bin"])] = {
            "n": int(raw["n_bin"]),
            "med": float(raw["med"]) if raw["med"] is not None else None,
        }
    out: list[dict[str, Any]] = []
    for slot in by_key.values():
        bins = slot["bins"]
        n = sum(int(b["n"]) for b in bins.values())
        low = bins.get("low")
        if n < N_MIN or low is None or int(low["n"]) < OTHER_BIN_MIN:
            continue
        band = height_band(slot["max_floor"])
        if band is None:
            continue
        n_low = int(low["n"])
        med_low = low["med"]
        row: dict[str, Any] = {
            "building_key": slot["building_key"],
            "max_floor": slot["max_floor"],
            "band": band,
            "n": n,
            "n_low": n_low,
        }
        for name in PROFILE_BINS:
            part = bins.get(name)
            n_bin = int(part["n"]) if part else 0
            med = part["med"] if part else None
            row[f"n_{name}"] = n_bin
            row[f"idx_{name}"] = _index(med, n_bin, med_low, n_low)
        high = bins.get("high")
        top = bins.get("top")
        row["idx_top_over_high"] = _index(
            top["med"] if top else None,
            int(top["n"]) if top else 0,
            high["med"] if high else None,
            int(high["n"]) if high else 0,
        )
        out.append(row)
    return out


def _cell_stats(frame: pd.DataFrame, column: str) -> dict[str, Any]:
    part = frame[np.isfinite(frame[column].to_numpy(dtype=float))]
    values = part[column].to_numpy(dtype=float)
    weights = part["n"].to_numpy(dtype=float)
    med = float(np.median(values)) if len(values) else None
    return {
        "n": int(len(values)),
        "equal": None if med is None else round(med, 2),
        "weighted": None if med is None else round(weighted_median(values, weights) or med, 2),
    }


def summarize_asset(buildings: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(buildings)
    cells: list[dict[str, Any]] = []
    if frame.empty:
        return {"buildings": 0, "cells": cells}
    for band in BAND_ORDER:
        sub = frame[frame["band"] == band]
        for name in ALL_BINS:
            stats = _cell_stats(sub, f"idx_{name}")
            cells.append(
                {
                    "band": band,
                    "band_label": BAND_LABELS[band],
                    "bin": name,
                    "bin_label": BIN_LABELS[name],
                    **stats,
                }
            )
    return {"buildings": int(len(frame)), "cells": cells}


def _same_direction(left: float, right: float) -> bool:
    return left * right > 0


def compare_assets(off: dict[str, Any], apt: dict[str, Any]) -> list[dict[str, Any]]:
    off_cells = {(c["band"], c["bin"]): c for c in off["cells"]}
    apt_cells = {(c["band"], c["bin"]): c for c in apt["cells"]}
    rows: list[dict[str, Any]] = []
    for band in BAND_ORDER:
        for name in ALL_BINS:
            o = off_cells[(band, name)]
            a = apt_cells[(band, name)]
            closed = (band, name) in CLOSED_CELLS or o["n"] < REPORT_MIN_BUILDINGS or a["n"] < REPORT_MIN_BUILDINGS
            diff_eq = None
            diff_w = None
            flag = "closed" if closed else "record"
            if not closed and o["equal"] is not None and a["equal"] is not None:
                diff_eq = round(o["equal"] - a["equal"], 2)
                diff_w = round(o["weighted"] - a["weighted"], 2)
                if (
                    abs(diff_eq) >= INTEREST_POINTS
                    and abs(diff_w) >= INTEREST_POINTS
                    and _same_direction(diff_eq, diff_w)
                ):
                    flag = "notable"
            rows.append(
                {
                    "band": band,
                    "band_label": BAND_LABELS[band],
                    "bin": name,
                    "bin_label": BIN_LABELS[name],
                    "off_n": o["n"],
                    "apt_n": a["n"],
                    "off_equal": o["equal"],
                    "apt_equal": a["equal"],
                    "diff_equal": diff_eq,
                    "off_weighted": o["weighted"],
                    "apt_weighted": a["weighted"],
                    "diff_weighted": diff_w,
                    "flag": flag,
                }
            )
    return rows


def phase2_open(compare_rows: list[dict[str, Any]]) -> list[str]:
    """두 가중·둘 이상 대역에서 눈에 띄는 칸만 2차로 연다."""
    opened: list[str] = []
    for name in ALL_BINS:
        bands = [r["band"] for r in compare_rows if r["bin"] == name and r["flag"] == "notable"]
        if len(bands) >= 2:
            opened.append(name)
    return opened


def fetch_bin_rows(conn: Connection, asset: str, p_start, p_end) -> list[dict[str, Any]]:
    rows = conn.execute(text(RATIO_SQL), {"asset": asset, "p_start": p_start, "p_end": p_end}).mappings()
    return [dict(r) for r in rows]


def run_ratio(engine: Engine) -> dict[str, Any]:
    with engine.connect() as conn:
        as_of = latest_as_of_month(conn)
        p_start, p_end = period_bounds_for_window(as_of, 5)
        by_asset: dict[str, Any] = {}
        for asset in ASSETS:
            buildings = rows_to_buildings(fetch_bin_rows(conn, asset, p_start, p_end))
            by_asset[asset] = summarize_asset(buildings)
    compare_rows = compare_assets(by_asset["officetel"], by_asset["apartment"])
    opened = phase2_open(compare_rows)
    return {
        "as_of": as_of.isoformat(),
        "period_start": p_start.isoformat(),
        "period_end": p_end.isoformat(),
        "reference": "low",
        "interest_points": INTEREST_POINTS,
        "note": "저층=100. 회귀 없음. 1층=100 아님. 가격 원자료는 저장하지 않음.",
        "by_asset": by_asset,
        "compare": compare_rows,
        "phase2_bins": opened,
    }


def main() -> None:
    payload = run_ratio(get_collective_engine())
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_JSON),
                "officetel": payload["by_asset"]["officetel"]["buildings"],
                "apartment": payload["by_asset"]["apartment"]["buildings"],
                "phase2_bins": payload["phase2_bins"],
                "flags": [
                    {
                        "band": r["band"],
                        "bin": r["bin"],
                        "diff_equal": r["diff_equal"],
                        "diff_weighted": r["diff_weighted"],
                        "flag": r["flag"],
                    }
                    for r in payload["compare"]
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
