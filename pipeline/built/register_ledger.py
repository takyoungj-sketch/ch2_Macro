"""Register caches from building ledger v1 instead of rescanning the raw TXT files.

Rows come out in original source line order (sidecar), so the caches are identical to the
raw scan and the first-come rules in `recover_address` give the same results.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Any

LEDGER = Path(r"C:\CH2\parcel_master\building_ledger_v1.sqlite")
SIDECAR = Path(r"C:\CH2\parcel_master\building_ledger_v1_line_order.sqlite")


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(LEDGER.resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    db.execute("ATTACH DATABASE ? AS side", (SIDECAR.resolve().as_uri() + "?mode=ro",))
    return db


def write_caches(
    db: sqlite3.Connection, kind: str, snapshot: str, cols: dict[str, int], out_by_sido: dict[str, Path]
) -> dict[str, Any]:
    """Same output as `_scan_pipe_file_multi`, read from the ledger in source line order."""
    if not db.execute("SELECT 1 FROM side.done WHERE kind=? AND snapshot=?", (kind, snapshot)).fetchone():
        raise ValueError(f"{kind} {snapshot} is not in the building ledger line order sidecar")
    need = max(cols.values())
    sg = cols["sigungu_code"]
    files: dict[str, Any] = {}
    writers: dict[str, Any] = {}
    kept = {s: 0 for s in out_by_sido}
    total = bad = 0
    try:
        for sido, path in out_by_sido.items():
            path.parent.mkdir(exist_ok=True)
            files[sido] = path.open("w", encoding="utf-8", newline="")
            writers[sido] = csv.writer(files[sido])
            writers[sido].writerow(list(cols))
        for (raw,) in db.execute(
            f"SELECT v.raw FROM side.line_order l JOIN {kind}_version v ON v.pk=l.pk AND v.raw_hash=l.raw_hash"
            " WHERE l.kind=? AND l.snapshot=? ORDER BY l.line_no",
            (kind, snapshot),
        ):
            total += 1
            parts = raw.decode("utf-8-sig", errors="replace").split("|")
            if len(parts) <= need:
                bad += 1
                continue
            w = writers.get(parts[sg][:2])
            if w is None:
                continue
            w.writerow([parts[i] for i in cols.values()])
            kept[parts[sg][:2]] += 1
    finally:
        for f in files.values():
            f.close()
    return {"src": f"building_ledger_v1:{kind}:{snapshot}", "rows_read": total, "rows_short": bad, "rows_kept": kept}
