"""Plan step 4-A re-check for 전남광주(12) with the 29/46 → 12 bridge. Read-only; counts only.

(a) 2026-07 code-12 building parcels → land trait slim (old codes) presence.
(b) A2 land-area fallback from the slim through the bridge vs AL_D003 (same caches).
(c) 2024-09 / 2025-07 title & summary rows of 29/46 re-coded to 12 so that time_fallback
    can use them, vs the current run where those snapshots are empty for 12.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.db_utils import get_built_engine  # noqa: E402
from built.recover_address import CACHE, SUMMARY_COLS, TITLE_COLS, TX_SQL, load_land_ledger  # noqa: E402
from built.register_ledger import connect as ledger_connect, write_caches  # noqa: E402
from built.replay_enrichment_from_ledger import diff, records, run_matching  # noqa: E402
from built.replay_enrichment_land_supply import SLIM, compare_dicts, slim_land, title_keys  # noqa: E402
from built.replay_register_cache_from_ledger import SCRATCH  # noqa: E402
from parcel_master.honam_code_bridge_v1 import BRIDGE  # noqa: E402

BRIDGED = SCRATCH / "honam_bridged"


def load_bridge() -> dict[str, str]:
    db = sqlite3.connect(BRIDGE.resolve().as_uri() + "?mode=ro", uri=True)
    return dict(db.execute("SELECT new_bjd, old_bjd FROM bridge WHERE old_bjd IS NOT NULL"))


def building_land(slim: sqlite3.Connection, new_to_old: dict[str, str]) -> Counter:
    ledger = ledger_connect()
    calendar = dict(slim.execute("SELECT bit, asof FROM asof_calendar"))
    last_bit = max(calendar)
    c = Counter()
    for (pnu,) in ledger.execute(
        "SELECT pnu FROM title_observation WHERE snapshot='2026-07' AND pnu LIKE '12%'"
    ):
        old = new_to_old.get(pnu[:10])
        if old is None:
            c["held_no_bridge"] += 1
            continue
        mask = 0
        for (m,) in slim.execute("SELECT asof_mask FROM observation WHERE pnu=?", (int(old + pnu[10:]),)):
            mask |= m
        c["bridged"] += 1
        if mask >> last_bit & 1:
            c["in_last_asof"] += 1
        elif mask:
            c["other_asof_only"] += 1
        else:
            c["absent"] += 1
    c["last_asof"] = calendar[last_bit]
    return c


def bridged_caches(old_to_new: dict[str, str]) -> Counter:
    """Re-code 29/46 rows of 2024-09 and 2025-07 into scratch title_12/summary_12 files."""
    BRIDGED.mkdir(parents=True, exist_ok=True)
    db = ledger_connect()
    c = Counter()
    for kind, cols in (("title", TITLE_COLS), ("summary", SUMMARY_COLS)):
        shutil.copyfile(CACHE / f"{kind}_12_2026-07.csv", BRIDGED / f"{kind}_12_2026-07.csv")
        for snap in ("2024-09", "2025-07"):
            parts = {s: BRIDGED / f"_{kind}_{s}_{snap}.csv" for s in ("29", "46")}
            write_caches(db, kind, snap, cols, parts)
            with (BRIDGED / f"{kind}_12_{snap}.csv").open("w", encoding="utf-8", newline="") as w:
                writer = csv.writer(w)
                writer.writerow(list(cols))
                for s in ("29", "46"):
                    with parts[s].open(encoding="utf-8", newline="") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            old = row["sigungu_code"].strip() + row["bjd_code"].strip()
                            new = old_to_new.get(old) if len(old) == 10 else None
                            if new is None:
                                c[f"{kind}_{snap}_unbridged"] += 1
                                continue
                            row["sigungu_code"], row["bjd_code"] = new[:5], new[5:]
                            writer.writerow([row[k] for k in cols])
                            c[f"{kind}_{snap}_bridged"] += 1
                    parts[s].unlink()
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    new_to_old = load_bridge()
    old_to_new = {o: n for n, o in new_to_old.items()}
    slim = sqlite3.connect(SLIM.resolve().as_uri() + "?mode=ro", uri=True)
    slim.execute("PRAGMA query_only=ON")
    slim.execute("PRAGMA cache_size=-1000000")
    report: dict = {"bridge_pairs": len(new_to_old)}

    report["a_building_land"] = dict(building_land(slim, new_to_old))
    print("a", report["a_building_land"], flush=True)

    with get_built_engine().connect() as conn:
        tx = pd.read_sql(text(TX_SQL), conn, params={"sido_like": "12%", "min_year": 2019})
    al_d003 = load_land_ledger("12", False)
    keys = title_keys("12")
    from_slim = slim_land(slim, keys, new_to_old)
    res_old, _ = run_matching(tx, CACHE, "12", al_d003)
    res_slim, _ = run_matching(tx, CACHE, "12", from_slim)
    a, b = records(res_old), records(res_slim)
    report["b_land_area"] = {
        "transactions": len(tx),
        "land_dict": dict(compare_dicts(al_d003, from_slim, keys)),
        "confirmed_al_d003": len(a),
        "confirmed_slim_bridged": len(b),
        "diff": diff(a, b),
    }
    print("b", report["b_land_area"], flush=True)

    report["c_bridged_caches"] = dict(bridged_caches(old_to_new))
    res_bridged, _ = run_matching(tx, BRIDGED, "12", al_d003)
    c = records(res_bridged)
    via = Counter(res_bridged.loc[res_bridged["tier"].notna(), "snapshot_used"].astype(str))
    report["c_time_fallback"] = {
        "confirmed_current": len(a),
        "confirmed_bridged": len(c),
        "diff": diff(a, c),
        "snapshot_used_bridged": dict(via),
        "snapshot_used_current": dict(Counter(res_old.loc[res_old["tier"].notna(), "snapshot_used"].astype(str))),
    }
    print("c", report["c_time_fallback"], flush=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
