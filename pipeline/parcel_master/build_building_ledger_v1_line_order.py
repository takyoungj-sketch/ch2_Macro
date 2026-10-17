"""Sidecar for building ledger v1: original line number of each (kind, snapshot, management key).

The composite enrichment rule takes the first land area / building it meets, so source line
order is part of its input. The frozen ledger does not hold it; this sidecar does.
Verifies each line's raw hash against the ledger observation. Ledger opened read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.build_building_ledger_v1 import DEFAULT_DB, KINDS  # noqa: E402
from parcel_master.paths import SNAPSHOTS  # noqa: E402

DEFAULT_SIDECAR = Path(r"C:\CH2\parcel_master\building_ledger_v1_line_order.sqlite")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, default=DEFAULT_DB)
    ap.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    ledger = sqlite3.connect(args.ledger.resolve().as_uri() + "?mode=ro", uri=True)
    ledger.execute("PRAGMA query_only=ON")
    side = sqlite3.connect(args.sidecar)
    side.execute("PRAGMA synchronous=OFF")
    side.execute(
        "CREATE TABLE IF NOT EXISTS line_order(kind TEXT NOT NULL, snapshot TEXT NOT NULL, line_no INTEGER NOT NULL,"
        " pk TEXT NOT NULL, raw_hash BLOB NOT NULL, PRIMARY KEY(kind, snapshot, line_no)) WITHOUT ROWID"
    )
    side.execute("CREATE TABLE IF NOT EXISTS done(kind TEXT, snapshot TEXT, sha256 TEXT, rows INTEGER, hash_mismatch INTEGER,"
                 " PRIMARY KEY(kind, snapshot))")
    report = {}
    for kind, (path_of, _) in KINDS.items():
        for snapshot in sorted(SNAPSHOTS):
            if side.execute("SELECT 1 FROM done WHERE kind=? AND snapshot=?", (kind, snapshot)).fetchone():
                continue
            expected = dict(
                ledger.execute(f"SELECT pk, raw_hash FROM {kind}_observation WHERE snapshot=?", (snapshot,))
            )
            sha = hashlib.sha256()
            batch = []
            mismatch = 0
            n = 0
            with side, path_of(snapshot).open("rb") as stream:
                for n, line in enumerate(stream, 1):
                    sha.update(line)
                    raw = line.rstrip(b"\r\n")
                    parts = (raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw).split(b"|", 1)
                    pk = parts[0].decode("ascii").strip()
                    h = hashlib.blake2b(raw, digest_size=16).digest()
                    if expected.get(pk) != h:
                        mismatch += 1
                    batch.append((kind, snapshot, n, pk, h))
                    if len(batch) >= 100_000:
                        side.executemany("INSERT INTO line_order VALUES(?,?,?,?,?)", batch)
                        batch.clear()
                side.executemany("INSERT INTO line_order VALUES(?,?,?,?,?)", batch)
                side.execute("INSERT INTO done VALUES(?,?,?,?,?)", (kind, snapshot, sha.hexdigest(), n, mismatch))
            report[f"{kind}|{snapshot}"] = {"rows": n, "ledger_rows": len(expected), "hash_mismatch": mismatch,
                                            "sha256": sha.hexdigest()}
            print(kind, snapshot, report[f"{kind}|{snapshot}"], flush=True)
    for kind, snapshot, sha, rows, mm in side.execute("SELECT * FROM done ORDER BY 1, 2"):
        report.setdefault(f"{kind}|{snapshot}", {"rows": rows, "hash_mismatch": mm, "sha256": sha})
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
