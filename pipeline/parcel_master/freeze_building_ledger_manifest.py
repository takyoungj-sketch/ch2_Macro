"""Write the freeze manifest for building ledger v1 (read-only; counts and hashes only)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.build_building_ledger_v1 import DEFAULT_DB, RULE  # noqa: E402
from parcel_master.freeze_land_trait_ledger_manifest import _mtime, sha256_file  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--backup", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    started = time.time()
    db = sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    sources = [
        dict(zip(("kind", "snapshot", "file", "bytes", "sha256", "rows", "loaded_rows", "scope"), r))
        for r in db.execute(
            "SELECT kind,snapshot,file,bytes,sha256,rows,loaded_rows,scope FROM source_file ORDER BY kind,snapshot"
        )
    ]
    counts = {
        t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("title_version", "title_observation", "summary_version", "summary_observation")
    }
    schema = {
        r[0]: r[1]
        for r in db.execute("SELECT name, sql FROM sqlite_master WHERE type IN ('table','index') AND sql IS NOT NULL")
    }
    db.close()
    print("hashing ledger", flush=True)
    ledger = {"path": str(args.db), "bytes": args.db.stat().st_size, "mtime_utc": _mtime(args.db),
              "sha256": sha256_file(args.db)}
    manifest = {
        "name": "BUILDING_LEDGER_V1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "rule": RULE,
        "sources": sources,
        "table_counts": counts,
        "schema_sql": schema,
        "ledger": ledger,
    }
    if args.backup:
        print("hashing backup", flush=True)
        manifest["backup"] = {"path": str(args.backup), "bytes": args.backup.stat().st_size,
                              "sha256": sha256_file(args.backup)}
        manifest["backup"]["matches"] = (
            manifest["backup"]["sha256"] == ledger["sha256"] and manifest["backup"]["bytes"] == ledger["bytes"]
        )
    manifest["elapsed_seconds"] = round(time.time() - started, 1)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out} seconds={manifest['elapsed_seconds']}", flush=True)


if __name__ == "__main__":
    main()
