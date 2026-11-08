"""Read-only guest smoke for mobile + desktop free statistics. No login cookie.

Run on the VPS with API_TOKEN in the environment; API token is infrastructure
authentication only. No user JWT, local development bypass, or AI calls are used.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    headers = {"Content-Type": "application/json"}
    if os.environ.get("API_TOKEN"):
        headers["X-Api-Token"] = os.environ["API_TOKEN"]

    def call(path, params=None, body=None, expected=200):
        url = args.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(url, headers=headers, data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                status, data = response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            status, data = exc.code, json.load(exc)
        assert status == expected, (path, status, data)
        return data

    rows = call("/api/free/v2/regions", {"search": "가경동", "limit": 10})
    region = next(r for r in rows if r["sigungu_code"] == "43113" and r["eupmyeondong_name"] == "가경동")
    code = region["eupmyeondong_code"]
    print("PASS guest canonical name search")
    stats = call(f"/api/paid/upper-stats/eupmyeondong/{code}", {"window_years": 5})
    cell = next(c for c in stats["matrix"] if c["stats"]["count"] > 0)
    rolling = call("/api/paid/matrix-yearly", body={
        "region_selections": [{"scope_type": "eupmyeondong", "code": code}],
        "zone_type": cell["zone_type"], "land_category": cell["land_category"],
        "matrix_mode": "category", "rolling_bucket_count": 5,
        "rolling_matrix_period_start": stats["period_start"],
        "rolling_matrix_period_end": stats["period_end"],
        "rolling_stats_reference_date": stats["stats_reference_date"],
        "exclude_partial": False, "exclude_outlier": False,
    })
    assert len(rolling["rows"]) == 5, rolling
    print("PASS guest land 5-year basic + matrix rolling (5 buckets)")
    for prefix, list_path, key in [
        ("/api/collective", "buildings", "building_key"),
        ("/api/collective/commercial", "clusters", "cluster_key"),
    ]:
        data = call(f"{prefix}/{list_path}", {
            "addr1": region["sido_name"], "addr2": region["sigungu_name"].split()[0],
            "region_codes": [code], "region_code_level": "eupmyeondong",
            "region_addrs": [f'{region["sido_name"]}|{region["sigungu_name"]}|{region["eupmyeondong_name"]}'],
            "asset_type": "all", "window_years": 5, "page_size": 5, "sort": "count",
        })
        assert data["total"] > 0 and data["items"], data
        item_key = urllib.parse.quote(data["items"][0][key], safe="")
        series = call(f"{prefix}/{list_path}/{item_key}/stats/rolling", {"window_years": 5})
        # A newly built complex can have fewer nonempty buckets in the 5-year window.
        assert series["window_years"] == 5 and 0 < len(series["points"]) <= 5, series
        assert all(1 <= p["bucket_index"] <= 5 for p in series["points"]), series
        call(f"{prefix}/{list_path}/{item_key}/stats/rolling", {"window_years": 7}, expected=401)
        print(f"PASS guest {list_path} 5-year basic + rolling; 7-year access remains protected")
        areas = call(f"{prefix}/{list_path}/{item_key}/stats/rolling-by-area", {"window_years": 5})
        assert areas["window_years"] == 5 and areas["series"] and areas["area_rule"], areas
        assert all(1 <= p["bucket_index"] <= 5 and p["count"] > 0 for group in areas["series"] for p in group["points"]), areas
        call(f"{prefix}/{list_path}/{item_key}/stats/rolling-by-area", {"window_years": 7}, expected=401)
        print(f"PASS guest {list_path} area rolling ({len(areas['series'])} area types); 7-year access remains protected")
    call("/api/paid/analyze", body={}, expected=401)
    print("PASS paid analysis remains protected")


if __name__ == "__main__":
    main()
