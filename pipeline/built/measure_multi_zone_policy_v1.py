"""D-078 (multi-zone policy): how many composite transactions the regression would use, and how many are multi-zone.

Policy: the first zone of the land trait source is the representative categorical regressor even when a parcel has
two zones; the contract-year observation comes first and anything else follows the existing missing-value rule
(adjacent-year observations are not used, as before). The second zone and the multi-zone flag are kept apart.

Counts come from a national engine v1 version (zone2 is kept there; the step 7 table has no zone2). The version is
built once in the test folder outside the repo and reused. Read only on every source; counts only in the report.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.link_engine_v1 import ALL_SNAPSHOTS, ENGINE_RULE, Defn, compute, counts, ledger_universe, write_version  # noqa: E402

VERSION = Path(r"C:\CH2\parcel_master\versions_test\built") / f"N_full_{ENGINE_RULE.rsplit('+', 1)[-1]}.sqlite"
DEFN = Defn(ALL_SNAPSHOTS, None, "2026Q3")


def build(workers: int) -> dict:
    t0 = time.time()
    u = ledger_universe()
    h, v, d, st = compute(u, DEFN, workers=workers)
    write_version(VERSION, h, v, d, {"version_id": "N_full", "parent": "", "defn": DEFN.to_dict(),
                                     "rule_version": ENGINE_RULE, "built_by": "full"})
    return {"seconds": round(time.time() - t0, 1), "keys": len(u), "link_state": counts(h), "bytes": VERSION.stat().st_size}


def share(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 3) if whole else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    built = build(args.workers) if not VERSION.exists() else {"reused": True, "bytes": VERSION.stat().st_size}
    u = ledger_universe().set_index("transaction_hash")
    db = sqlite3.connect(VERSION.resolve().as_uri() + "?mode=ro", uri=True)
    link = dict(db.execute("SELECT target_key, link_state FROM ledger_link_header_v1"))
    zone, approved = {}, set()
    for k, s, t, ua in db.execute("SELECT target_key, value_state, timing, use_approved FROM ledger_link_value_v1 "
                                  "WHERE variable = 'zone_contract_year'"):
        zone[k] = (s, t)
        if ua:
            approved.add(k)
    multi = {k for (k,) in db.execute(
        "SELECT target_key FROM ledger_link_value_v1 WHERE variable = 'zone2_contract_year' AND value_state = 'confirmed'")}
    held = db.execute("SELECT COUNT(*) FROM ledger_link_header_v1 WHERE hold_flags LIKE '%multi_zone%'").fetchone()[0]
    rule = dict(db.execute("SELECT k, v FROM version_info")).get("rule_version")
    db.close()

    groups: dict = defaultdict(Counter)
    for k, state in link.items():
        if k not in u.index:
            continue
        r = u.loc[k]
        if state != "linked":
            cls = "not_applicable" if state == "not_applicable" else "unlinked"
        else:
            zs, timing = zone.get(k, (None, None))
            if zs == "confirmed" and timing == "contract_year":
                cls = "included_multi" if k in multi else "included_single"
                if k not in approved:
                    groups["check"]["included_not_use_approved"] += 1
            elif zs == "confirmed":
                cls = "adjacent_year_excluded_multi" if k in multi else "adjacent_year_excluded"
            else:
                cls = "zone_missing"
        for g in ("all", f"asset:{r['asset_type']}", f"sido:{r['sido']}", f"year:{int(r['contract_year'])}"):
            groups[g][cls] += 1

    check = {"rule_version": rule, "multi_zone_hold_flags": held,
             "included_not_use_approved": groups.pop("check", Counter())["included_not_use_approved"]}
    out = {}
    for g, c in sorted(groups.items()):
        inc = c["included_single"] + c["included_multi"]
        linked = sum(v for k, v in c.items() if k not in ("not_applicable", "unlinked"))
        out[g] = {**dict(sorted(c.items())), "included": inc, "linked": linked,
                  "multi_share_of_included_pct": share(c["included_multi"], inc),
                  "included_share_of_linked_pct": share(inc, linked)}
    rep = {"decision": "D-078", "population": "built_transactions 2019+ (engine v1, editions 2024-09·2025-07·2026-07, all slim releases)",
           "rule": "included = zone_contract_year confirmed at contract-year base; multi = zone2 present at that base; "
                   "adjacent-year observations stay excluded (existing missing-value rule)",
           "version": built, "check": check, "groups": out}
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"check": check, **{g: out[g] for g in out if g == "all" or g.startswith("asset:")}},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
