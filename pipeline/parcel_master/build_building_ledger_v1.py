"""National building register ledger v1 (plan step 3).

Raw title (표제부) and summary (총괄표제부) lines are kept byte-for-byte.
One version row per distinct (management key, raw line); one observation row per
(snapshot, management key). Parcel numbers are derived with the Cheongju v2.1 identity
rule; land type codes other than 0/1 are held, never converted. Region codes are kept
as written in each snapshot (no code history mapping here).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.building_ledger_v1_gauge import summary_path  # noqa: E402
from parcel_master.paths import SNAPSHOTS, title_path  # noqa: E402

DEFAULT_DB = Path(r"C:\CH2\parcel_master\building_ledger_v1.sqlite")
RULE = "building-ledger-v1 / cheongju-source-identity-v2.1 (national)"
KINDS = {"title": (title_path, 8), "summary": (summary_path, 10)}
BATCH = 50_000


def identity(sg: str, bd: str, gb: str, bun: str, ji: str) -> tuple[str | None, str]:
    sg, bd, gb, bun, ji = (v.strip() for v in (sg, bd, gb, bun, ji))
    if not re.fullmatch(r"[0-9]{5}", sg):
        return None, "invalid_district"
    if re.fullmatch(r"[0-9]{1,5}", bd):
        bjd = sg + bd.zfill(5)
    elif re.fullmatch(r"[0-9]{10}", bd) and bd.startswith(sg):
        bjd = bd
    else:
        return None, "invalid_bjd"
    if gb not in ("0", "1"):
        return None, "unknown_land_type"
    if not re.fullmatch(r"[0-9]{1,4}", bun):
        return None, "invalid_main_lot"
    if not re.fullmatch(r"[0-9]{1,4}", ji):
        return None, "invalid_sub_lot"
    return bjd + ("2" if gb == "1" else "1") + bun.zfill(4) + ji.zfill(4), "canonical_address"


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA synchronous=OFF")
    db.execute("PRAGMA cache_size=-2000000")
    db.execute("PRAGMA temp_store=MEMORY")
    for kind in KINDS:
        db.executescript(f"""
        CREATE TABLE IF NOT EXISTS {kind}_version(
            pk TEXT NOT NULL, raw_hash BLOB NOT NULL, raw BLOB NOT NULL,
            PRIMARY KEY(pk, raw_hash)) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS {kind}_observation(
            snapshot TEXT NOT NULL, pk TEXT NOT NULL, raw_hash BLOB NOT NULL,
            column_count INTEGER NOT NULL, identity_status TEXT NOT NULL, pnu TEXT,
            PRIMARY KEY(snapshot, pk)) WITHOUT ROWID;
        """)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS source_file(
        kind TEXT NOT NULL, snapshot TEXT NOT NULL, file TEXT NOT NULL, bytes INTEGER NOT NULL,
        sha256 TEXT NOT NULL, rows INTEGER NOT NULL, loaded_rows INTEGER NOT NULL,
        scope TEXT NOT NULL, stats TEXT NOT NULL, loaded_at TEXT NOT NULL,
        PRIMARY KEY(kind, snapshot));
    CREATE TABLE IF NOT EXISTS build_info(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    return db


def load(db: sqlite3.Connection, kind: str, snapshot: str, sigungu: set[str] | None) -> dict:
    path_of, sg_idx = KINDS[kind]
    path = path_of(snapshot)
    scope = "national" if not sigungu else ",".join(sorted(sigungu))
    done = db.execute(
        "SELECT scope FROM source_file WHERE kind=? AND snapshot=?", (kind, snapshot)
    ).fetchone()
    if done:
        if done[0] != scope:
            raise ValueError(f"{kind} {snapshot} already loaded with another scope")
        print(f"skip {kind} {snapshot} (loaded)", flush=True)
        return {}
    sha = hashlib.sha256()
    rows = loaded = 0
    status = Counter()
    cols = Counter()
    zero_main_lot = 0
    versions: list[tuple] = []
    observations: list[tuple] = []
    started = time.time()

    def flush() -> None:
        db.executemany(f"INSERT OR IGNORE INTO {kind}_version VALUES(?,?,?)", versions)
        db.executemany(f"INSERT INTO {kind}_observation VALUES(?,?,?,?,?,?)", observations)
        versions.clear()
        observations.clear()

    with db, path.open("rb") as stream:
        for line in stream:
            rows += 1
            sha.update(line)
            raw = line.rstrip(b"\r\n")
            parts = (raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw).split(b"|")
            fields = [p.decode("ascii", "replace") for p in parts[sg_idx:sg_idx + 5]]
            if sigungu and fields[0].strip() not in sigungu:
                continue
            pk = parts[0].decode("ascii").strip()
            if not pk:
                raise ValueError("Empty management key")
            pnu, st = identity(*fields)
            if pnu and pnu[11:15] == "0000":
                zero_main_lot += 1
            h = hashlib.blake2b(raw, digest_size=16).digest()
            versions.append((pk, h, raw))
            observations.append((snapshot, pk, h, len(parts), st, pnu))
            status[st] += 1
            cols[len(parts)] += 1
            loaded += 1
            if len(observations) >= BATCH:
                flush()
            if rows % 1_000_000 == 0:
                print(f"{kind} {snapshot} rows={rows:,} loaded={loaded:,} {time.time() - started:.0f}s", flush=True)
        flush()
        stats = {
            "identity_status": dict(status.most_common()),
            "column_counts": dict(cols),
            "canonical_with_zero_main_lot": zero_main_lot,
            "seconds": round(time.time() - started, 1),
        }
        db.execute(
            "INSERT INTO source_file VALUES(?,?,?,?,?,?,?,?,?,datetime('now'))",
            (kind, snapshot, f"{path.parent.name}/{path.name}", path.stat().st_size,
             sha.hexdigest(), rows, loaded, scope, json.dumps(stats, ensure_ascii=False)),
        )
    print(f"done {kind} {snapshot} rows={rows:,} loaded={loaded:,} {stats['seconds']}s", flush=True)
    return stats


def finish(db: sqlite3.Connection) -> dict:
    with db:
        db.execute("CREATE INDEX IF NOT EXISTS title_observation_pnu ON title_observation(pnu) WHERE pnu IS NOT NULL")
        db.execute("CREATE INDEX IF NOT EXISTS summary_observation_pnu ON summary_observation(pnu) WHERE pnu IS NOT NULL")
        db.execute("INSERT OR REPLACE INTO build_info VALUES('rule', ?)", (RULE,))
    report: dict = {"rule": RULE, "sources": [], "tables": {}}
    for row in db.execute("SELECT kind,snapshot,file,bytes,sha256,rows,loaded_rows,scope,stats FROM source_file ORDER BY kind,snapshot"):
        report["sources"].append({
            "kind": row[0], "snapshot": row[1], "file": row[2], "bytes": row[3], "sha256": row[4],
            "rows": row[5], "loaded_rows": row[6], "scope": row[7], "stats": json.loads(row[8]),
        })
    for kind in KINDS:
        report["tables"][kind] = {
            "versions": db.execute(f"SELECT COUNT(*) FROM {kind}_version").fetchone()[0],
            "observations": db.execute(f"SELECT COUNT(*) FROM {kind}_observation").fetchone()[0],
            "buildings": db.execute(f"SELECT COUNT(DISTINCT pk) FROM {kind}_version").fetchone()[0],
            "orphan_observations": db.execute(
                f"SELECT COUNT(*) FROM {kind}_observation o LEFT JOIN {kind}_version v USING(pk, raw_hash) WHERE v.pk IS NULL"
            ).fetchone()[0],
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--sigungu", default="", help="comma list for a trial load")
    parser.add_argument("--kinds", default="title,summary")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    sigungu = {s.strip() for s in args.sigungu.split(",") if s.strip()} or None
    db = connect(args.db)
    for kind in args.kinds.split(","):
        for snapshot in sorted(SNAPSHOTS):
            load(db, kind, snapshot, sigungu)
    report = finish(db)
    report["db_bytes"] = args.db.stat().st_size
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.report}", flush=True)
    db.close()


if __name__ == "__main__":
    main()
