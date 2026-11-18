"""HTTP smoke checks for the local land app. No ingestion or ledger mutation.

Normal API reads may populate the application's analysis caches.
Run with backend/.venv/Scripts/python.exe -B scripts/local/check-land.py.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default="2026-09-01")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    session = requests.Session()
    base = "http://127.0.0.1:5173/api"
    results: list[dict] = []

    def call(name: str, path: str, *, body=None, params=None):
        started = time.perf_counter()
        row = {"name": name, "path": path}
        try:
            response = session.request(
                "POST" if body is not None else "GET", base + path,
                json=body, params=params, timeout=45,
            )
            row["status"] = response.status_code
            response.raise_for_status()
            data = response.json()
            row["ok"] = True
            if isinstance(data, dict):
                for key in ("as_of_month", "period_start", "period_end", "window_years", "max_as_of_month"):
                    if key in data:
                        row[key] = data[key]
                if isinstance(data.get("total"), dict):
                    row["count"] = data["total"].get("count")
                elif "total" in data:
                    row["count"] = data["total"]
                for key in ("items", "matrix", "points", "series", "neighbor_codes"):
                    if isinstance(data.get(key), list):
                        row[key + "_length"] = len(data[key])
                if "feature_collection" in data:
                    row["features_length"] = len(data["feature_collection"].get("features", []))
            elif isinstance(data, list):
                row["items_length"] = len(data)
            return data
        except Exception as exc:
            row.update(ok=False, error=str(exc))
            return None
        finally:
            row["seconds"] = round(time.perf_counter() - started, 3)
            results.append(row)
            print(json.dumps(row, ensure_ascii=True), flush=True)

    def check(name: str, condition: bool):
        results.append({"name": name, "ok": bool(condition)})

    call("regions", "/free/v2/regions", params={"search": "복대동", "limit": 10})
    meta = call("meta", "/free/v2/meta/as-of")
    check("latest_snapshot", meta is not None and meta.get("max_as_of_month") == args.as_of)
    default = call("default_as_of", "/free/v2/stats/4311311400", params={"window_years": 5})
    check("default_matches_latest", default is not None and default.get("as_of_month") == args.as_of)
    samples = {}
    for code in ("4311311400", "4311210200"):
        for window in (3, 5, 7):
            for mode in ("category", "group"):
                data = call(f"basic_{code}_{window}_{mode}", f"/free/v2/stats/{code}",
                            params={"window_years": window, "matrix_mode": mode, "as_of_month": args.as_of})
                if data:
                    samples[code, window, mode] = data
    first = samples.get(("4311311400", 5, "category"))
    second = samples.get(("4311210200", 5, "category"))
    bulk = call("bulk", "/free/v2/stats/bulk", body={
        "region_codes": ["4311311400", "4311210200"], "window_years": 5, "as_of_month": args.as_of,
    })
    if first and second and bulk:
        check("bulk_count_equals_single_sum", bulk["total"]["count"] == first["total"]["count"] + second["total"]["count"])
    paid_body = {"region_codes": ["4311311400"], "year_from": 2022, "year_to": 2026}
    paid = call("paid", "/paid/analyze", body=paid_body)
    filtered = call("paid_area_filter", "/paid/analyze", body={**paid_body, "area_sqm_min": 100, "area_sqm_max": 500})
    if paid and filtered:
        check("filter_does_not_increase_count", filtered["total"]["count"] <= paid["total"]["count"])
    if first and first.get("matrix"):
        cell = max(first["matrix"], key=lambda item: item["stats"]["count"])
        body = {
            "region_codes": ["4311311400"], "zone_type": cell["zone_type"], "land_category": cell["land_category"],
            "rolling_matrix_period_start": first["period_start"],
            "rolling_matrix_period_end": first["period_end"], "rolling_bucket_count": 5,
            "rolling_stats_reference_date": first["stats_reference_date"],
        }
        transactions = call("transactions", "/paid/matrix-cell-transactions", body={**body, "limit": 25})
        if transactions:
            check("cell_count_matches_transactions", transactions["total"] == cell["stats"]["count"])
            ids = [item["id"] for item in transactions["items"]]
            check("transaction_page_has_unique_ids", len(ids) == len(set(ids)))
            dates = [item.get("contract_date") for item in transactions["items"]]
            check("transactions_within_period", all(date and first["period_start"] <= date <= first["period_end"] for date in dates))
        call("rolling_trend", "/paid/matrix-yearly", body=body)
        call("histogram", "/paid/matrix-cell-histogram", body={**body, "bin_count": 20})
        call("long_term", "/paid/long-term-trend", body={
            "region_codes": ["4311311400"], "zone_type": cell["zone_type"], "land_category": cell["land_category"],
            "year_from": 2021, "year_to": 2026,
        })
    call("upper_stats", "/paid/upper-stats/sigungu/43113", params={"window_years": 5, "as_of_month": args.as_of})
    call("map_config", "/map/config")
    neighbors = call("map_neighbors", "/map/neighbors", params={"level": "eupmyeondong", "codes": "43113114"})
    if neighbors is not None:
        check("map_has_neighbors", bool(neighbors.get("neighbor_codes")) and neighbors.get("graph_ready") is True)
    boundaries = call("map_boundaries", "/map/boundaries", params={
        "level": "beopjungri", "context_sigungu_code": "43113", "selected": "4311311400",
    })
    if boundaries is not None:
        check("map_has_geometry", bool(boundaries.get("feature_collection", {}).get("features")))
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "as_of": args.as_of, "checks": results}
    report["passed"] = sum(row["ok"] for row in results)
    report["failed"] = len(results) - report["passed"]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SUMMARY passed={report['passed']} failed={report['failed']}")
    raise SystemExit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()
