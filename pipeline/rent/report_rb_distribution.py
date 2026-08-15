#!/usr/bin/env python3
"""서울 건물 r_b 분포 — 평균·중앙값·MAD. 방법을 바꾸지 않고 안정성만 본다."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, period_bounds_for_window  # noqa: E402
from rent.build_conversion_rates import _fetch_rows, _group_region  # noqa: E402
from rent.conversion import R_MAX_PCT, R_MIN_PCT, region_gate  # noqa: E402
from rent.db_utils import get_rent_engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _clip_rs(obs) -> list[float]:
    out: list[float] = []
    for o in obs:
        r = o.r_building
        if r is None or not np.isfinite(r):
            continue
        if r < R_MIN_PCT or r > R_MAX_PCT:
            continue
        out.append(float(r))
    return out


def _mad(vals: list[float], med: float) -> float:
    return float(np.median(np.abs(np.asarray(vals) - med)))


def _band(mad: float, mean_med_gap: float) -> str:
    if mad < 0.8 and mean_med_gap <= 0.5:
        return "stable"
    if mad < 1.5 and mean_med_gap <= 1.0:
        return "mild"
    return "unstable"


def _cell(obs, *, a1, a2, a3, at, window_years, level: str) -> dict | None:
    ok, nb, nj, nm = region_gate(obs, level=level)
    if not ok:
        return None
    rs = _clip_rs(obs)
    if len(rs) < 2:
        return None
    arr = np.asarray(rs, dtype=float)
    mean = float(np.mean(arr))
    med = float(np.median(arr))
    mad = _mad(rs, med)
    gap = abs(mean - med)
    return {
        "addr1": a1,
        "addr2": a2,
        "addr3": a3,
        "asset_type": at,
        "window_years": window_years,
        "level": level,
        "n": len(rs),
        "n_jeonse": nj,
        "n_mixed": nm,
        "mean": round(mean, 4),
        "median": round(med, 4),
        "mad": round(mad, 4),
        "min": round(float(np.min(arr)), 4),
        "max": round(float(np.max(arr)), 4),
        "mean_minus_median": round(mean - med, 4),
        "band": _band(mad, gap),
    }


def _tally(rows: list[dict]) -> dict:
    bands = {"stable": 0, "mild": 0, "unstable": 0}
    for r in rows:
        bands[r["band"]] = bands.get(r["band"], 0) + 1
    n = len(rows) or 1
    return {k: {"n": v, "pct": round(100.0 * v / n, 1)} for k, v in bands.items()}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--addr1", default="서울특별시")
    p.add_argument("--windows", default="3,5,7")
    p.add_argument("--out", default="pipeline/rent/_seoul_rb_distribution.json")
    args = p.parse_args()
    as_of = default_as_of_month()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    engine = get_rent_engine()
    cells: list[dict] = []
    for w in windows:
        ps, pe = period_bounds_for_window(as_of, w)
        log.info("r_b dist w%s %s..%s", w, ps, pe)
        rows = _fetch_rows(engine, p_start=ps, p_end=pe, addr1=args.addr1)
        for with_dong, level in ((False, "sigungu"), (True, "dong")):
            regions = _group_region(rows, with_dong=with_dong)
            for (a1, a2, a3, at), obs in regions.items():
                rec = _cell(obs, a1=a1, a2=a2, a3=a3, at=at, window_years=w, level=level)
                if rec:
                    cells.append(rec)
    sig = [c for c in cells if c["level"] == "sigungu"]
    dong = [c for c in cells if c["level"] == "dong"]
    report = {
        "as_of": as_of.isoformat(),
        "addr1": args.addr1,
        "n_cells": len(cells),
        "bands": {"sigungu": _tally(sig), "dong": _tally(dong), "all": _tally(cells)},
        "cells": cells,
    }
    path = Path(args.out)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("wrote %s cells=%s bands=%s", path, len(cells), report["bands"])


if __name__ == "__main__":
    main()
