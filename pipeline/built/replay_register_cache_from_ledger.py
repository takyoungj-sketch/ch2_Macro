"""Rebuild the composite enrichment register caches from building ledger v1 and compare (plan step 4).

The ledger is opened read-only. Rebuilt caches go to a scratch folder outside the repo;
the existing `_cache/` files are only read. Writes counts only (no keys, no parcels).
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from built.recover_address import CACHE, SNAPSHOTS, SUMMARY_COLS, TITLE_COLS  # noqa: E402
from built.register_ledger import connect, write_caches  # noqa: E402

SCRATCH = Path(r"C:\CH2\parcel_master\_replay_built_cache")
KINDS = {"title": TITLE_COLS, "summary": SUMMARY_COLS}


def rebuild(db: sqlite3.Connection, kind: str, snapshot: str, sidos: list[str]) -> dict[str, int]:
    out = {s: SCRATCH / f"{kind}_{s}_{snapshot}.csv" for s in sidos}
    return write_caches(db, kind, snapshot, KINDS[kind], out)["rows_kept"]


def rows_of(path: Path) -> list[tuple[str, ...]]:
    with path.open(encoding="utf-8", newline="") as f:
        return [tuple(r) for r in csv.reader(f)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    sidos = sorted({p.name.split("_")[1] for p in CACHE.glob("title_*_2026-07.csv")})
    db = connect()
    report: dict = {"sidos": sidos, "order": "source line (sidecar)", "results": {}}
    for kind in KINDS:
        for snapshot in SNAPSHOTS:
            kept = rebuild(db, kind, snapshot, sidos)
            for s in sidos:
                old = rows_of(CACHE / f"{kind}_{s}_{snapshot}.csv")
                new = rows_of(SCRATCH / f"{kind}_{s}_{snapshot}.csv")
                same_order = old == new
                same_set = same_order or sorted(old) == sorted(new)
                report["results"][f"{kind}|{s}|{snapshot}"] = {
                    "cache_rows": len(old) - 1,
                    "ledger_rows": kept[s],
                    "identical_in_order": same_order,
                    "identical_as_multiset": same_set,
                }
            print(f"{kind} {snapshot} done", flush=True)
    res = report["results"].values()
    report["summary"] = {
        "files": len(report["results"]),
        "identical_in_order": sum(r["identical_in_order"] for r in res),
        "identical_as_multiset": sum(r["identical_as_multiset"] for r in res),
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"]), flush=True)


if __name__ == "__main__":
    main()
