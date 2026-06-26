import json
import os
import ssl
import urllib.parse
import urllib.request

BASE = os.environ.get("COLLECTIVE_BASE", "http://127.0.0.1:8000/api/collective")
TOKEN = os.environ.get("API_TOKEN", "")


def get(path: str) -> dict:
    req = urllib.request.Request(
        BASE + path,
        headers={"X-Api-Token": TOKEN} if TOKEN else {},
    )
    with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=30) as r:
        return json.load(r)


def main() -> None:
    items = get("/buildings?search=" + urllib.parse.quote("광진") + "&asset_type=officetel&limit=10").get("items", [])
    row = next((x for x in items if "캠퍼스" in x.get("display_name", "")), items[0] if items else None)
    if not row:
        print("no building")
        return
    key = row["building_key"]
    print("building", row["display_name"], key, "n=", row.get("count"))

    rolling = get(f"/buildings/{urllib.parse.quote(key, safe='')}/stats/rolling?window_years=5")
    print("rolling points", len(rolling.get("points", [])), "source", rolling.get("data_source"))

    tx = get(f"/buildings/{urllib.parse.quote(key, safe='')}/transactions?page=1&page_size=5")
    print("tx total", tx.get("total"), "items", len(tx.get("items", [])))

    yearly = get(f"/buildings/{urllib.parse.quote(key, safe='')}/stats/by-year")
    ys = [p["year"] for p in yearly.get("points", [])]
    print("yearly", min(ys) if ys else None, "-", max(ys) if ys else None, "n=", len(ys), "source", yearly.get("data_source"))


if __name__ == "__main__":
    main()
