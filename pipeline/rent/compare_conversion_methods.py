#!/usr/bin/env python3
"""서울 5년 4후보 r 비교 요약 — 채택 근거 리포트."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("coverage_json", default="pipeline/rent/_seoul_5y_coverage.json", nargs="?")
    args = p.parse_args()
    data = json.loads(Path(args.coverage_json).read_text(encoding="utf-8"))
    regions = [r for r in data.get("regions", []) if r.get("gate_passed")]
    if not regions:
        print("no gate-passed regions")
        return

    def spread(key: str) -> dict:
        vals = [float(r[key]) for r in regions if r.get(key) is not None]
        diffs = []
        for r in regions:
            a, b = r.get("r_ols_origin"), r.get(key)
            if a is not None and b is not None:
                diffs.append(abs(float(a) - float(b)))
        return {
            "median": statistics.median(vals),
            "p25": statistics.quantiles(vals, n=4)[0],
            "p75": statistics.quantiles(vals, n=4)[2],
            "mad_vs_ols": statistics.median(diffs) if diffs else None,
        }

    print("Seoul 5y gate-passed regions:", len(regions))
    for key in ("r_mean_simple", "r_mean_weighted", "r_ols_origin", "r_ols_weighted"):
        print(key, spread(key))
    print("\nAdopted: mean_simple (default) — hold-out MAPE vs jeonse P50; 4 columns kept.")


if __name__ == "__main__":
    main()
