"""Plan step 4-A: 광주·전남(29/46) → 전남광주(12) legal-dong bridge, checked two ways.

1. Name pairs from the land code history layer V1 (region_codes name match, 1:1 only).
2. Observed pairs from building ledger v1: the same management key with an old-code parcel
   in 2025-07 and a new-code parcel in 2026-07.
The bridge keeps each pair's evidence level and holds anything that is not 1:1 or disagrees.
Writes a derived sqlite outside the repo plus a counts-only report. Read-only on the
ledger and the database.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from sqlalchemy import text  # noqa: E402

from db_utils import get_engine  # noqa: E402
from parcel_master.build_building_ledger_v1 import DEFAULT_DB  # noqa: E402
from parcel_master.code_history_link_shadow import load_pairs  # noqa: E402

BRIDGE = Path(r"C:\CH2\parcel_master\honam_code_bridge_v1.sqlite")


def observed_pairs(ledger: sqlite3.Connection) -> tuple[dict[tuple[str, str], Counter], Counter]:
    pairs: dict[tuple[str, str], Counter] = defaultdict(Counter)
    totals = Counter()
    for kind in ("title", "summary"):
        sql = f"""
        SELECT a.pnu, b.pnu FROM {kind}_observation a
        JOIN {kind}_observation b ON b.pk = a.pk AND b.snapshot = '2026-07'
        WHERE a.snapshot = '2025-07' AND a.pnu IS NOT NULL AND b.pnu IS NOT NULL
          AND substr(a.pnu, 1, 2) IN ('29', '46')
        """
        for old, new in ledger.execute(sql):
            totals[f"{kind}_pairs"] += 1
            if not new.startswith("12"):
                totals[f"{kind}_new_not_12"] += 1
                continue
            c = pairs[(new[:10], old[:10])]
            c[kind] += 1
            c["tail_equal" if new[10:] == old[10:] else "tail_differ"] += 1
    return pairs, totals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--min-buildings", type=int, default=1)
    args = ap.parse_args()
    ledger = sqlite3.connect(DEFAULT_DB.resolve().as_uri() + "?mode=ro", uri=True)
    ledger.execute("PRAGMA query_only=ON")
    with get_engine().connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        name = {cur: prev for cur, (prev, _eff) in load_pairs(conn).items() if cur.startswith("12")}
        current_12 = {
            str(r[0]).strip() for r in conn.execute(text("SELECT beopjungri_code FROM region_codes WHERE sido_code = '12'"))
        }
    obs, totals = observed_pairs(ledger)

    by_new: dict[str, dict[str, Counter]] = defaultdict(dict)
    by_old: dict[str, set[str]] = defaultdict(set)
    for (new, old), c in obs.items():
        if c["tail_equal"] >= args.min_buildings:
            by_new[new][old] = c
            by_old[old].add(new)

    rows = []
    status = Counter()
    for new in sorted(current_12 | set(by_new) | set(name)):
        olds = by_new.get(new, {})
        name_old = name.get(new)
        tail_eq = sum(c["tail_equal"] for c in olds.values())
        tail_diff = sum(obs[(new, o)]["tail_differ"] for o in olds)
        if len(olds) > 1 or any(len(by_old[o]) > 1 for o in olds):
            level, chosen = "held_not_1to1", None
        elif olds:
            (obs_old,) = olds
            if name_old is None:
                level, chosen = "observed_only", obs_old
            elif name_old == obs_old:
                level, chosen = "observed_and_name", obs_old
            else:
                level, chosen = "held_disagree", None
        elif name_old is not None:
            level, chosen = "name_only", name_old
        else:
            level, chosen = "no_evidence", None
        status[level] += 1
        rows.append((new, chosen, name_old, ",".join(sorted(olds)), tail_eq, tail_diff, level))

    BRIDGE.unlink(missing_ok=True)
    out = sqlite3.connect(BRIDGE)
    out.execute(
        "CREATE TABLE bridge(new_bjd TEXT PRIMARY KEY, old_bjd TEXT, name_old_bjd TEXT, observed_old_bjd TEXT,"
        " buildings_tail_equal INTEGER, buildings_tail_differ INTEGER, evidence TEXT NOT NULL)"
    )
    out.executemany("INSERT INTO bridge VALUES(?,?,?,?,?,?,?)", rows)
    out.execute("CREATE TABLE info(key TEXT PRIMARY KEY, value TEXT)")
    out.execute("INSERT INTO info VALUES('effective', '2026-07-01')")
    out.commit()
    out.close()

    usable = [r for r in rows if r[1]]
    report = {
        "bridge_file": str(BRIDGE),
        "region_codes_12": len(current_12),
        "name_pairs_12": len(name),
        "observed_building_pairs": dict(totals),
        "observed_bjd_pairs": len(obs),
        "observed_tail_equal_buildings": sum(c["tail_equal"] for c in obs.values()),
        "observed_tail_differ_buildings": sum(c["tail_differ"] for c in obs.values()),
        "evidence": dict(status),
        "usable_pairs": len(usable),
        "usable_buildings_covered": sum(r[4] for r in usable),
        "held_buildings": sum(r[4] for r in rows if not r[1]),
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
