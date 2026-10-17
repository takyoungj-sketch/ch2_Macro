"""Write the freeze manifest for land trait ledger v1.

Reads the source ZIPs, the national ledger (read-only) and the link result table.
Writes nothing except the manifest JSON. No individual parcel is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from sqlalchemy import text

from db_utils import get_engine

SOURCE_DIR = ROOT / "raw" / "raw addition" / "토지특성정보CSV(브이월드)"
LEDGER = Path(r"C:\CH2\parcel_master\land_trait_observations.sqlite")
LOAD_REPORT = ROOT / "docs" / "lab" / "land_trait_national_slim_20261010.json"
LINK_REPORT = ROOT / "docs" / "lab" / "land_trait_link_materialize_20261016.json"
RULE_VERSION = "LAND_CODE_HISTORY_LAYER_V1+LAND_LINK_RULE_V1"
CHUNK = 8 * 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def source_files(with_hash: bool) -> list[dict]:
    out = []
    for p in sorted(SOURCE_DIR.glob("*.zip")):
        row = {"name": p.name, "bytes": p.stat().st_size, "mtime_utc": _mtime(p)}
        if with_hash:
            row["sha256"] = sha256_file(p)
        out.append(row)
        print(f"source {len(out)} {p.name}", flush=True)
    return out


def ledger_info(with_hash: bool) -> dict:
    db = sqlite3.connect(f"file:{LEDGER.as_posix()}?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        page_size = db.execute("PRAGMA page_size").fetchone()[0]
        page_count = db.execute("PRAGMA page_count").fetchone()[0]
        schema = {
            r[0]: r[1]
            for r in db.execute("SELECT name, sql FROM sqlite_master WHERE type IN ('table','index') AND sql IS NOT NULL")
        }
    finally:
        db.close()
    info = {
        "path": str(LEDGER),
        "bytes": LEDGER.stat().st_size,
        "mtime_utc": _mtime(LEDGER),
        "page_size": page_size,
        "page_count": page_count,
        "tables": tables,
        "schema_sql": schema,
    }
    if with_hash:
        print("hashing ledger", flush=True)
        info["sha256"] = sha256_file(LEDGER)
    return info


def link_counts() -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM land_transaction_trait_link")).scalar()
        rules = conn.execute(
            text("SELECT rule_version, count(*) FROM land_transaction_trait_link GROUP BY 1 ORDER BY 1")
        ).all()
        status = conn.execute(
            text(
                "SELECT link_status, coalesce(price_status, ''), count(*) "
                "FROM land_transaction_trait_link GROUP BY 1, 2 ORDER BY 1, 2"
            )
        ).all()
    by_status: dict[str, dict[str, int]] = {}
    for link, price, n in status:
        by_status.setdefault(link, {})[price or "none"] = int(n)
    return {
        "table": "land_transaction_trait_link",
        "rows": int(total),
        "by_rule_version": {r: int(n) for r, n in rules},
        "by_link_and_price_status": by_status,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-hash", action="store_true")
    args = ap.parse_args()
    started = time.time()
    with_hash = not args.no_hash
    manifest = {
        "name": "LAND_TRAIT_LEDGER_V1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "rule_version": RULE_VERSION,
        "load_report": json.loads(LOAD_REPORT.read_text(encoding="utf-8")),
        "link_report_file": LINK_REPORT.relative_to(ROOT).as_posix(),
        "link_result": link_counts(),
        "source_dir": str(SOURCE_DIR),
        "source_files": source_files(with_hash),
        "ledger": ledger_info(with_hash),
    }
    manifest["source_count"] = len(manifest["source_files"])
    manifest["source_bytes"] = sum(f["bytes"] for f in manifest["source_files"])
    manifest["elapsed_seconds"] = round(time.time() - started, 1)
    out = Path(args.out)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out} sources={manifest['source_count']} seconds={manifest['elapsed_seconds']}", flush=True)


if __name__ == "__main__":
    main()
