#!/usr/bin/env python3
"""반전세→전세환산 vs 실제 전세 P50. 동일기간 + 시계열 hold-out (서울 기본)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import (  # noqa: E402
    default_as_of_month,
    parse_as_of_month,
    period_bounds_for_window,
    _anchor_n_calendar_years_before,
)
from rent.build_conversion_rates import _fetch_rows, _group_region  # noqa: E402
from rent.conversion import (  # noqa: E402
    METHOD_KEYS,
    candidate_rates,
    errors_vs_jeonse,
    region_gate,
)
from rent.db_utils import get_rent_engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _metrics_block(obs, cand: dict) -> dict:
    out = {}
    for method, key in METHOD_KEYS.items():
        out[method] = errors_vs_jeonse(obs, cand.get(key))
    return out


def _eval_split(engine, *, p_start: date, p_end: date, addr1: str, level: str) -> list[dict]:
    rows = _fetch_rows(engine, p_start=p_start, p_end=p_end, addr1=addr1)
    regions = _group_region(rows, with_dong=(level == "dong"))
    out = []
    for (a1, a2, a3, at), obs in sorted(regions.items()):
        ok, nb, nj, nm = region_gate(obs, level="sigungu" if level == "sigungu" else "dong")
        if not ok:
            continue
        cand = candidate_rates(obs)
        out.append(
            {
                "addr1": a1,
                "addr2": a2,
                "addr3": a3,
                "asset_type": at,
                "n_buildings": nb,
                "n_jeonse": nj,
                "n_mixed": nm,
                "rates": {k: cand.get(v) for k, v in METHOD_KEYS.items()},
                "errors": _metrics_block(obs, cand),
            }
        )
    return out


def _holdout(engine, *, as_of: date, window_years: int, addr1: str, level: str) -> list[dict]:
    ps, pe = period_bounds_for_window(as_of, window_years)
    train_end = _anchor_n_calendar_years_before(pe, 1)
    if train_end <= ps:
        return []
    train_rows = _fetch_rows(engine, p_start=ps, p_end=train_end, addr1=addr1)
    test_rows = _fetch_rows(engine, p_start=train_end, p_end=pe, addr1=addr1)
    train = _group_region(train_rows, with_dong=(level == "dong"))
    test = _group_region(test_rows, with_dong=(level == "dong"))
    out = []
    for key, train_obs in sorted(train.items()):
        ok, *_ = region_gate(train_obs, level="sigungu" if level == "sigungu" else "dong")
        if not ok or key not in test:
            continue
        cand = candidate_rates(train_obs)
        a1, a2, a3, at = key
        out.append(
            {
                "addr1": a1,
                "addr2": a2,
                "addr3": a3,
                "asset_type": at,
                "train_n": len(train_obs),
                "test_n": len(test[key]),
                "rates": {k: cand.get(v) for k, v in METHOD_KEYS.items()},
                "errors": _metrics_block(test[key], cand),
            }
        )
    return out


def _summarize(cells: list[dict]) -> dict:
    methods = list(METHOD_KEYS)
    summary = {}
    for m in methods:
        maes, mapes, meds = [], [], []
        for c in cells:
            e = (c.get("errors") or {}).get(m) or {}
            if e.get("mae") is not None:
                maes.append(e["mae"])
            if e.get("mape") is not None:
                mapes.append(e["mape"])
            if e.get("median_ae") is not None:
                meds.append(e["median_ae"])
        summary[m] = {
            "cells": len(maes),
            "mae_median": _med(maes),
            "mape_median": _med(mapes),
            "median_ae_median": _med(meds),
        }
    return summary


def _med(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--addr1", default="서울특별시")
    p.add_argument("--windows", default="3,5,7")
    p.add_argument("--out", default="pipeline/rent/_seoul_conversion_validate.json")
    args = p.parse_args()
    as_of = default_as_of_month()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    engine = get_rent_engine()
    report: dict = {"as_of": as_of.isoformat(), "addr1": args.addr1, "windows": {}}
    for w in windows:
        ps, pe = period_bounds_for_window(as_of, w)
        log.info("in-sample w%s %s..%s", w, ps, pe)
        ins_s = _eval_split(engine, p_start=ps, p_end=pe, addr1=args.addr1, level="sigungu")
        ins_d = _eval_split(engine, p_start=ps, p_end=pe, addr1=args.addr1, level="dong")
        log.info("hold-out w%s", w)
        ho_s = _holdout(engine, as_of=as_of, window_years=w, addr1=args.addr1, level="sigungu")
        ho_d = _holdout(engine, as_of=as_of, window_years=w, addr1=args.addr1, level="dong")
        report["windows"][str(w)] = {
            "period": [ps.isoformat(), pe.isoformat()],
            "in_sample_sigungu": {"summary": _summarize(ins_s), "n_cells": len(ins_s)},
            "in_sample_dong": {"summary": _summarize(ins_d), "n_cells": len(ins_d)},
            "holdout_sigungu": {"summary": _summarize(ho_s), "n_cells": len(ho_s)},
            "holdout_dong": {"summary": _summarize(ho_d), "n_cells": len(ho_d)},
        }
        log.info("w%s in-sample sigungu cells=%s dong=%s", w, len(ins_s), len(ins_d))
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("wrote %s", path)


if __name__ == "__main__":
    main()
