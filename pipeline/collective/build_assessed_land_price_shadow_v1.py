"""Collective (residential) representative-parcel land price from land_trait_slim, as a shadow of the product mart.

Same selection as the loader (import_assessed_land_price): the representative PNU is the lot of the latest
collective_building_stats row of each building_key × asset_type. The price differs only in source: slim instead of
parcel_land_price. Rule:
  supplied   slim has a single price for the representative parcel in the latest release year (earliest month
             of that year, as in the step 5 comparison)
  held_stale latest slim year is older (parcel likely split/merged/redeveloped) — price and year kept, not supplied
  held_conflict / slim_no_price / pnu_not_in_slim — not supplied
Non-residential collective has no representative-parcel mart (D-020) and is out of scope.

Read only on the product DB (SET TRANSACTION READ ONLY), slim, bridge. Writes only the shadow SQLite and a per-key
diagnosis CSV outside the repo. The report has counts only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from built.replay_honam_bridge import load_bridge  # noqa: E402
from collective.compare_rep_parcel_supply_v1 import SLIM, VERIFY, code_variants, num, read_product, ro, slim_lookup  # noqa: E402
from parcel_master.honam_code_bridge_v1 import BRIDGE  # noqa: E402
from parcel_master.pnu import pnu_from_tx  # noqa: E402

OUT = Path(r"C:\CH2\parcel_master\shadow\collective_building_assessed_land_price_shadow_v1.sqlite")
RULE = "slim_latest_year_v1"

DDL = """
CREATE TABLE collective_building_assessed_land_price_shadow (
    building_key TEXT NOT NULL, asset_type TEXT NOT NULL, representative_pnu TEXT NOT NULL,
    state TEXT NOT NULL, use_approved INTEGER NOT NULL,
    assessed_land_price REAL, assessed_land_price_year INTEGER, assessed_land_price_month INTEGER,
    slim_via TEXT NOT NULL, source TEXT NOT NULL, rule_version TEXT NOT NULL,
    PRIMARY KEY (building_key, asset_type)
);
CREATE TABLE info (key TEXT PRIMARY KEY, value TEXT);
"""


def year_price(rows: list[tuple]) -> dict:
    priced = [(int(y), int(m), num(p)) for y, m, _, p in rows if num(p) is not None]
    if not priced:
        return {"state": "slim_no_price"}
    ly = max(y for y, _, _ in priced)
    m0 = min(m for y, m, _ in priced if y == ly)
    vals = {p for y, m, p in priced if y == ly and m == m0}
    months = {m for y, m, _ in priced if y == ly}
    return {"state": "single" if len(vals) == 1 else "held_conflict", "year": ly, "month": m0,
            "price": next(iter(vals)) if len(vals) == 1 else None, "months_in_year": len(months)}


def bridge_evidence() -> dict[str, str]:
    db = sqlite3.connect(BRIDGE.resolve().as_uri() + "?mode=ro", uri=True)
    return dict(db.execute("SELECT new_bjd, evidence FROM bridge"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--diag", type=Path, default=VERIFY / "collective_assessed_land_price_shadow_v1_diag.csv")
    args = ap.parse_args()
    t0 = time.time()
    prod = read_product()
    bridge, evidence = load_bridge(), bridge_evidence()
    incheon, incheon_new = prod["incheon_current_to_old"], prod["incheon_old_to_current"]
    slim = ro(SLIM)

    cands = []
    no_pnu = Counter()
    for r in prod["current"]:
        key = (r.building_key.strip(), r.asset_type.strip())
        p = pnu_from_tx(r.beopjungri_code, r.lot_number)
        if p:
            cands.append((key, p))
        else:
            no_pnu[key[1]] += 1

    rows_out, looked = [], {}
    for key, p in cands:
        via, rows = slim_lookup(slim, code_variants(p, bridge, incheon, incheon_new))
        yp = year_price(rows) if rows else {"state": "pnu_not_in_slim"}
        looked[key] = (p, via, yp, rows)
    latest = max(v[2]["year"] for v in looked.values() if "year" in v[2])
    for key, (p, via, yp, _) in looked.items():
        st = yp["state"]
        if st == "single":
            st = "supplied" if yp["year"] == latest else "held_stale"
        rows_out.append((key[0], key[1], p, st, int(st == "supplied"), yp.get("price"), yp.get("year"),
                         yp.get("month"), via, "land_trait_slim", RULE))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".partial")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(DDL)
    db.executemany("INSERT INTO collective_building_assessed_land_price_shadow VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   sorted(rows_out))
    db.executemany("INSERT INTO info VALUES (?,?)", [("rule_version", RULE), ("latest_year", str(latest)),
                                                     ("built_on", time.strftime("%Y-%m-%d"))])
    db.commit()
    db.close()
    OUT.unlink(missing_ok=True)
    tmp.rename(OUT)

    mart = {(r.building_key.strip(), r.asset_type.strip()): r for r in prod["mart"]}
    shadow = {(r[0], r[1]): r for r in rows_out}
    cmp_: dict = defaultdict(Counter)
    states: dict = defaultdict(Counter)
    for r in rows_out:
        states[r[1]][r[3]] += 1
        states[r[1]][f"year_{r[6]}" if r[6] else "year_none"] += 1
    diag_rows = []
    for key in sorted(set(mart) | set(shadow)):
        a = key[1]
        m, s = mart.get(key), shadow.get(key)
        if m is None:
            cmp_[a]["new_" + s[3]] += 1
            continue
        if s is None:
            cmp_[a]["mart_only_no_current_pnu"] += 1
            continue
        mp, sp = float(m.assessed_land_price), s[5]
        same_pnu = m.representative_pnu.strip() == s[2]
        cmp_[a]["rep_pnu_" + ("same" if same_pnu else "changed")] += 1
        if s[3] != "supplied":
            cls = "not_supplied_" + s[3]
        elif int(m.assessed_land_price_year) != s[6]:
            cls = "different_year"
        elif abs(mp - sp) < 0.5:
            cls = "same"
        else:
            cls = "different_price"
        cmp_[a][cls] += 1
        if cls != "same":
            p, via, yp, rows = looked[key]
            reason = ""
            if cls == "different_price":
                yr = {(int(y), int(mo), num(v)) for y, mo, _, v in rows if num(v) is not None and int(y) == s[6]}
                if any(abs(v - mp) < 0.5 for _, _, v in yr):
                    reason = "mart_price_is_other_month_of_same_year"
                elif not same_pnu:
                    reason = "mart_rep_pnu_differs_from_current"
                else:
                    reason = "slim_and_parcel_land_price_disagree"
            elif s[3] == "pnu_not_in_slim":
                reason = "bridge_" + (evidence.get(p[:10]) or "no_row") if p[:2] == "12" else "not_in_slim"
            cmp_["reasons"][f"{cls}:{reason}"] += 1
            diag_rows.append([key[0], a, m.representative_pnu.strip(), p, mp, int(m.assessed_land_price_year),
                              s[3], sp, s[6], s[7], via, reason,
                              ";".join(f"{y}-{mo}:{v}" for y, mo, _, v in sorted(rows))])
    with open(args.diag, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["building_key", "asset_type", "mart_pnu", "current_pnu", "mart_price", "mart_year", "shadow_state",
                    "shadow_price", "shadow_year", "shadow_month", "slim_via", "reason", "slim_rows"])
        w.writerows(diag_rows)

    supplied = sum(c["supplied"] for c in states.values())
    report = {
        "plan_step": "5 (collective) — slim price shadow, product mart untouched",
        "rule": RULE, "latest_year": latest,
        "shadow_file": "outside repo (C:\\CH2\\parcel_master\\shadow)", "diag_file": "outside repo (verification)",
        "candidates": len(cands), "stats_keys_without_pnu": dict(no_pnu),
        "mart_rows": len(mart), "shadow_supplied": supplied,
        "shadow_state_by_asset": {a: dict(sorted(c.items())) for a, c in sorted(states.items())},
        "vs_mart": {a: dict(sorted(c.items())) for a, c in sorted(cmp_.items())},
        "seconds": round(time.time() - t0, 1),
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("latest_year", "candidates", "mart_rows", "shadow_supplied", "vs_mart")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
