"""집합상가 층 효용 — cluster별 1층=100 단가 가운데값.

회귀 없음. 전국 평균 없음. 10포인트 문턱 없음.
재실행 (backend에서): python -m app.shop_floor_lab.ratio
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.apt_floor_lab.screen import TIER_LABELS, place_name, region_tier
from app.collective.db import get_collective_engine
from app.land_lab.area_elasticity_screen import period_bounds_for_window

ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "lab" / "shop_floor_utility_phase1.json"

AS_OF = date(2026, 8, 1)
WINDOW_YEARS = 5
N_MIN = 50
BIN_MIN = 5
REPORT_MIN = 30
AREA_BAND = 0.20

PROFILE_BINS = ("f2", "low", "mid", "high", "ultra")
BIN_LABELS = {
    "f2": "2층",
    "low": "3–4층",
    "mid": "5–9층",
    "high": "10–19층",
    "ultra": "20층 이상",
}
N1_BANDS = (
    ("n1_5_9", "1층 5–9건", 5, 9),
    ("n1_10_19", "1층 10–19건", 10, 19),
    ("n1_20", "1층 20건 이상", 20, None),
)
TIER_ORDER = ("metro", "metro_city", "other_urban", "nonurban", "sejong")

_TX = """
    WITH tx AS (
        SELECT
            t.cluster_key,
            t.floor,
            t.unit_price,
            t.gross_area,
            t.addr1,
            t.addr3,
            t.addr4
        FROM collective_commercial_transactions t
        WHERE t.asset_type = 'collective_shop'
          AND t.is_valid IS TRUE
          AND t.contract_date >= :p_start
          AND t.contract_date <= :p_end
          AND t.unit_price > 0
          AND t.gross_area > 0
          AND t.floor >= 1
          AND t.cluster_key IS NOT NULL
          AND t.cluster_key <> ''
    ),
    scoped AS (
        SELECT
            tx.cluster_key,
            CASE
                WHEN tx.floor = 1 THEN 'f1'
                WHEN tx.floor = 2 THEN 'f2'
                WHEN tx.floor >= 3 AND tx.floor <= 4 THEN 'low'
                WHEN tx.floor >= 5 AND tx.floor <= 9 THEN 'mid'
                WHEN tx.floor >= 10 AND tx.floor <= 19 THEN 'high'
                WHEN tx.floor >= 20 THEN 'ultra'
                ELSE 'other'
            END AS bin,
            tx.unit_price,
            tx.gross_area,
            tx.addr1,
            tx.addr3,
            tx.addr4
        FROM tx
    )
"""

BIN_SQL = (
    _TX
    + """
    SELECT
        cluster_key,
        bin,
        COUNT(*)::int AS n_bin,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price) AS med,
        MAX(addr1) AS addr1,
        MAX(addr3) AS addr3,
        MAX(addr4) AS addr4
    FROM scoped
    WHERE bin <> 'other'
    GROUP BY cluster_key, bin
"""
)

AREA_SQL = (
    _TX
    + """
    , area AS (
        SELECT
            cluster_key,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gross_area) AS med_area
        FROM scoped
        WHERE bin <> 'other'
        GROUP BY cluster_key
    ),
    kept AS (
        SELECT s.*
        FROM scoped s
        JOIN area a ON a.cluster_key = s.cluster_key
        WHERE s.bin <> 'other'
          AND s.gross_area >= a.med_area * (1 - :band)
          AND s.gross_area <= a.med_area * (1 + :band)
    )
    SELECT
        cluster_key,
        bin,
        COUNT(*)::int AS n_bin,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price) AS med,
        MAX(addr1) AS addr1,
        MAX(addr3) AS addr3,
        MAX(addr4) AS addr4
    FROM kept
    GROUP BY cluster_key, bin
"""
)


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


def _index(med_bin: float | None, n_bin: int, med_f1: float | None, n_f1: int) -> float | None:
    if n_bin < BIN_MIN or n_f1 < BIN_MIN:
        return None
    if med_bin is None or med_f1 is None or med_f1 <= 0 or med_bin <= 0:
        return None
    return float(100.0 * med_bin / med_f1)


def _n1_band(n_f1: int) -> str | None:
    if 5 <= n_f1 <= 9:
        return "n1_5_9"
    if 10 <= n_f1 <= 19:
        return "n1_10_19"
    if n_f1 >= 20:
        return "n1_20"
    return None


def rows_to_clusters(bin_rows: list[dict[str, Any]], *, min_cluster_n: int = N_MIN) -> list[dict[str, Any]]:
    """cluster×칸 집계를 1층=100 지수 행으로 만든다. 가격은 남기지 않는다."""
    by_key: dict[str, dict[str, Any]] = {}
    for raw in bin_rows:
        key = str(raw["cluster_key"]).strip()
        slot = by_key.setdefault(
            key,
            {
                "cluster_key": key,
                "addr1": str(raw.get("addr1") or ""),
                "addr3": str(raw.get("addr3") or ""),
                "addr4": str(raw.get("addr4") or ""),
                "bins": {},
            },
        )
        slot["bins"][str(raw["bin"])] = {
            "n": int(raw["n_bin"]),
            "med": float(raw["med"]) if raw["med"] is not None else None,
        }
    out: list[dict[str, Any]] = []
    for slot in by_key.values():
        bins = slot["bins"]
        n = sum(int(b["n"]) for b in bins.values())
        f1 = bins.get("f1")
        if n < min_cluster_n or f1 is None or int(f1["n"]) < BIN_MIN:
            continue
        n_f1 = int(f1["n"])
        med_f1 = f1["med"]
        place = place_name(slot["addr3"], slot["addr4"])
        row: dict[str, Any] = {
            "cluster_key": slot["cluster_key"],
            "n": n,
            "n_f1": n_f1,
            "n1_band": _n1_band(n_f1),
            "tier": region_tier(slot["addr1"], place),
        }
        for name in PROFILE_BINS:
            part = bins.get(name)
            n_bin = int(part["n"]) if part else 0
            med = part["med"] if part else None
            row[f"n_{name}"] = n_bin
            row[f"idx_{name}"] = _index(med, n_bin, med_f1, n_f1)
        out.append(row)
    return out


def _round(value: float | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), 2)


def cell_stats(frame: pd.DataFrame, column: str) -> dict[str, Any]:
    if frame.empty or column not in frame.columns:
        values = np.array([], dtype=float)
        weights = np.array([], dtype=float)
    else:
        mask = np.isfinite(frame[column].to_numpy(dtype=float))
        values = frame.loc[mask, column].to_numpy(dtype=float)
        weights = frame.loc[mask, "n"].to_numpy(dtype=float)
    if len(values) == 0:
        return {
            "n": 0,
            "equal": None,
            "weighted": None,
            "p25": None,
            "p75": None,
            "iqr_excludes_100": False,
            "phase2_open": False,
        }
    p25, equal, p75 = (float(x) for x in np.quantile(values, [0.25, 0.5, 0.75]))
    weighted = weighted_median(values, weights)
    excludes = p75 < 100 or p25 > 100
    both_below = equal < 100 and weighted is not None and weighted < 100
    return {
        "n": int(len(values)),
        "equal": _round(equal),
        "weighted": _round(weighted),
        "p25": _round(p25),
        "p75": _round(p75),
        "iqr_excludes_100": bool(excludes),
        "phase2_open": bool(both_below and excludes and len(values) >= REPORT_MIN),
    }


def summarize_profile(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(clusters)
    rows: list[dict[str, Any]] = []
    for name in PROFILE_BINS:
        stats = cell_stats(frame, f"idx_{name}")
        rows.append({"bin": name, "bin_label": BIN_LABELS[name], **stats})
    return rows


def summarize_f2_by_n1(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(clusters)
    rows: list[dict[str, Any]] = []
    for key, label, _lo, _hi in N1_BANDS:
        sub = frame[frame["n1_band"] == key] if not frame.empty else frame
        stats = cell_stats(sub, "idx_f2")
        stats["phase2_open"] = False
        rows.append({"n1_band": key, "label": label, **stats})
    return rows


def opened_bins(profile: list[dict[str, Any]]) -> list[str]:
    return [row["bin"] for row in profile if row["phase2_open"]]


def summarize_tiers(clusters: list[dict[str, Any]], bins: list[str]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(clusters)
    rows: list[dict[str, Any]] = []
    for name in bins:
        for tier in TIER_ORDER:
            sub = frame[frame["tier"] == tier] if not frame.empty else frame
            stats = cell_stats(sub, f"idx_{name}")
            reportable = stats["n"] >= REPORT_MIN
            rows.append(
                {
                    "bin": name,
                    "bin_label": BIN_LABELS[name],
                    "tier": tier,
                    "tier_label": TIER_LABELS.get(tier, tier),
                    "reportable": reportable,
                    "equal": stats["equal"] if reportable else None,
                    "weighted": stats["weighted"] if reportable else None,
                    "p25": stats["p25"] if reportable else None,
                    "p75": stats["p75"] if reportable else None,
                    "n": stats["n"],
                    "phase2_open": bool(reportable and stats["phase2_open"]),
                }
            )
    return rows


def fetch_bin_rows(conn: Connection, p_start: date, p_end: date, *, area_band: bool) -> list[dict[str, Any]]:
    sql = AREA_SQL if area_band else BIN_SQL
    params: dict[str, Any] = {"p_start": p_start, "p_end": p_end}
    if area_band:
        params["band"] = AREA_BAND
    rows = conn.execute(text(sql), params).mappings()
    return [dict(r) for r in rows]


def run_ratio(engine: Engine) -> dict[str, Any]:
    p_start, p_end = period_bounds_for_window(AS_OF, WINDOW_YEARS)
    with engine.connect() as conn:
        base_rows = fetch_bin_rows(conn, p_start, p_end, area_band=False)
        clusters = rows_to_clusters(base_rows)
        profile = summarize_profile(clusters)
        opened = opened_bins(profile)
        area_clusters: list[dict[str, Any]] = []
        area_profile: list[dict[str, Any]] = []
        region_rows: list[dict[str, Any]] = []
        if opened:
            area_rows = fetch_bin_rows(conn, p_start, p_end, area_band=True)
            eligible = {row["cluster_key"] for row in clusters}
            area_clusters = [
                row
                for row in rows_to_clusters(area_rows, min_cluster_n=0)
                if row["cluster_key"] in eligible
            ]
            area_profile = [row for row in summarize_profile(area_clusters) if row["bin"] in opened]
            still = opened_bins(area_profile)
            if still:
                region_rows = summarize_tiers(area_clusters, still)
    return {
        "as_of": AS_OF.isoformat(),
        "period_start": p_start.isoformat(),
        "period_end": p_end.isoformat(),
        "reference": "f1",
        "area_band": AREA_BAND,
        "note": "도로 cluster. 1층=100. 회귀 없음. 가격 원자료는 저장하지 않음.",
        "clusters": len(clusters),
        "profile": profile,
        "f2_by_n1": summarize_f2_by_n1(clusters),
        "phase2_bins": opened,
        "phase2": area_profile,
        "phase3_bins": opened_bins(area_profile),
        "phase3": region_rows,
    }


def main() -> None:
    payload = run_ratio(get_collective_engine())
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_JSON),
                "clusters": payload["clusters"],
                "profile": [
                    {
                        "bin": r["bin"],
                        "n": r["n"],
                        "equal": r["equal"],
                        "weighted": r["weighted"],
                        "p25": r["p25"],
                        "p75": r["p75"],
                        "phase2_open": r["phase2_open"],
                    }
                    for r in payload["profile"]
                ],
                "phase2_bins": payload["phase2_bins"],
                "phase3_bins": payload["phase3_bins"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
