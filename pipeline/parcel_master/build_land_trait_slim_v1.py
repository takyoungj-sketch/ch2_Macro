"""Build the land trait slim layer v1 from the frozen national ledger.

The ledger is opened read-only. The slim file is a separate SQLite database.
One slim row = one parcel, price year, price month and one set of codes, area and
price, with a bitmask of every ledger asof where that exact set was observed.
Clean rows and conflict rows are folded together; the national conflict gauge
found that every conflict key differs in labels only.
No individual parcel is printed or written to the report.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = Path(r"C:\CH2\parcel_master\land_trait_observations.sqlite")
SLIM = Path(r"C:\CH2\parcel_master\land_trait_slim_v1.sqlite")
LOAD_REPORT = ROOT / "docs" / "lab" / "land_trait_national_slim_20261010.json"
FREEZE = ROOT / "docs" / "lab" / "land_trait_ledger_v1_freeze_20261017.json"
REPORT = ROOT / "docs" / "lab" / "land_trait_slim_v1_build_20261017.json"
VERSION = "LAND_TRAIT_SLIM_V1"
FIELDS = ("jimok", "zone1", "zone2", "use", "height", "shape", "road")
PREFIXES = [f"{n:02d}" for n in range(10, 60)]

SELECT = """
SELECT pnu, asof, price_year, price_month,
       jimok_code, area, zone1_code, zone2_code, use_code, height_code, shape_code, road_code, price,
       jimok_label, zone1_label, zone2_label, use_label, height_label, shape_label, road_label
FROM {table} WHERE pnu >= ? AND pnu < ?
"""

DDL = """
CREATE TABLE IF NOT EXISTS asof_calendar (
    bit INTEGER PRIMARY KEY,
    asof TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS observation (
    pnu INTEGER NOT NULL,
    price_year TEXT NOT NULL,
    price_month TEXT NOT NULL,
    asof_mask INTEGER NOT NULL,
    conflict_mask INTEGER NOT NULL,
    jimok_code TEXT NOT NULL,
    area TEXT NOT NULL,
    zone1_code TEXT NOT NULL,
    zone2_code TEXT NOT NULL,
    use_code TEXT NOT NULL,
    height_code TEXT NOT NULL,
    shape_code TEXT NOT NULL,
    road_code TEXT NOT NULL,
    price TEXT NOT NULL,
    PRIMARY KEY (pnu, price_year, price_month, asof_mask)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS code_dictionary (
    field TEXT NOT NULL,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    label_rows INTEGER NOT NULL,
    is_standard INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (field, code, label)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS build_progress (
    prefix TEXT PRIMARY KEY,
    ledger_clean_rows INTEGER NOT NULL,
    ledger_conflict_rows INTEGER NOT NULL,
    observation_keys INTEGER NOT NULL,
    conflict_keys INTEGER NOT NULL,
    slim_rows INTEGER NOT NULL,
    pnus INTEGER NOT NULL,
    semantic_conflicts INTEGER NOT NULL,
    seconds REAL NOT NULL,
    labels_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS build_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

INSERT = "INSERT INTO observation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"


def _bounds(prefix: str) -> tuple[str, str]:
    width = len(prefix)
    return prefix + "0" * (19 - width), f"{int(prefix) + 1:0{width}d}" + "0" * (19 - width)


def _ledger() -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{LEDGER.as_posix()}?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    db.execute("PRAGMA cache_size=-1000000")
    return db


def _slim() -> sqlite3.Connection:
    db = sqlite3.connect(SLIM)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA cache_size=-2000000")
    db.executescript(DDL)
    return db


def _asofs() -> list[str]:
    return list(json.loads(LOAD_REPORT.read_text(encoding="utf-8"))["asofs"])


def _stream(db: sqlite3.Connection, table: str, prefix: str):
    cursor = db.execute(SELECT.format(table=table), _bounds(prefix))
    while True:
        chunk = cursor.fetchmany(200_000)
        if not chunk:
            return
        yield from chunk


def _merged(db_clean: sqlite3.Connection, db_conflict: sqlite3.Connection, prefix: str):
    """Yield (pnu, rows) with clean and conflict rows of one parcel together."""
    clean = _stream(db_clean, "parcel_observation", prefix)
    conflict = _stream(db_conflict, "observation_conflict", prefix)
    a = next(clean, None)
    b = next(conflict, None)
    while a is not None or b is not None:
        pnu = min(x[0] for x in (a, b) if x is not None)
        rows: list[tuple[tuple, bool]] = []
        while a is not None and a[0] == pnu:
            rows.append((a, False))
            a = next(clean, None)
        while b is not None and b[0] == pnu:
            rows.append((b, True))
            b = next(conflict, None)
        yield pnu, rows


def _fold(rows: list[tuple[tuple, bool]], bits: dict[str, int], labels: Counter, counts: Counter) -> list[tuple]:
    by_key: dict[tuple, tuple[tuple, bool]] = {}
    for row, is_conflict in rows:
        for field, code, label in zip(FIELDS, (row[4], row[6], row[7], row[8], row[9], row[10], row[11]), row[13:20]):
            labels[(field, str(code or ""), str(label or "").strip())] += 1
        if is_conflict:
            counts["ledger_conflict_rows"] += 1
        else:
            counts["ledger_clean_rows"] += 1
        key = (row[1], row[2], row[3])
        values = row[4:13]
        seen = by_key.get(key)
        if seen is None:
            by_key[key] = (values, is_conflict)
        elif seen[0] != values:
            counts["semantic_conflicts"] += 1
        elif not is_conflict and seen[1]:
            by_key[key] = (values, False)
    masks: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    for (asof, year, month), (values, is_conflict) in by_key.items():
        bit = 1 << bits[str(asof)[:10]]
        entry = masks[(str(year), str(month), values)]
        entry[0] |= bit
        if is_conflict:
            entry[1] |= bit
            counts["conflict_keys"] += 1
        counts["observation_keys"] += 1
    out = []
    for (year, month, values), (mask, cmask) in masks.items():
        jimok, area, z1, z2, use, height, shape, road, price = (str(v if v is not None else "") for v in values)
        out.append((year, month, mask, cmask, jimok, area, z1, z2, use, height, shape, road, price))
    return out


def build(limit_prefixes: list[str] | None) -> None:
    asofs = _asofs()
    bits = {asof: i for i, asof in enumerate(asofs)}
    slim = _slim()
    slim.executemany("INSERT OR IGNORE INTO asof_calendar VALUES (?, ?)", list(enumerate(asofs)))
    slim.commit()
    done = {r[0] for r in slim.execute("SELECT prefix FROM build_progress")}
    db_clean = _ledger()
    db_conflict = _ledger()
    try:
        for prefix in limit_prefixes or PREFIXES:
            if prefix in done:
                continue
            started = time.time()
            lo, hi = _bounds(prefix)
            slim.execute("DELETE FROM observation WHERE pnu >= ? AND pnu < ?", (int(lo), int(hi)))
            labels: Counter = Counter()
            counts: Counter = Counter()
            batch: list[tuple] = []
            pnus = 0
            slim_rows = 0
            for pnu, rows in _merged(db_clean, db_conflict, prefix):
                pnus += 1
                pnu_int = int(pnu)
                for item in sorted(_fold(rows, bits, labels, counts)):
                    batch.append((pnu_int, *item))
                if len(batch) >= 200_000:
                    slim.executemany(INSERT, batch)
                    slim_rows += len(batch)
                    batch.clear()
                if pnus % 1_000_000 == 0:
                    print(f"{prefix} pnus={pnus} slim_rows={slim_rows}", flush=True)
            if batch:
                slim.executemany(INSERT, batch)
                slim_rows += len(batch)
            label_rows = [[f, c, lab, n] for (f, c, lab), n in labels.items()]
            slim.execute(
                "INSERT OR REPLACE INTO build_progress VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    prefix,
                    counts["ledger_clean_rows"],
                    counts["ledger_conflict_rows"],
                    counts["observation_keys"],
                    counts["conflict_keys"],
                    slim_rows,
                    pnus,
                    counts["semantic_conflicts"],
                    round(time.time() - started, 1),
                    json.dumps(label_rows, ensure_ascii=False),
                ),
            )
            slim.commit()
            if pnus:
                print(
                    f"prefix {prefix} pnus={pnus} clean={counts['ledger_clean_rows']} "
                    f"conflict={counts['ledger_conflict_rows']} keys={counts['observation_keys']} "
                    f"slim_rows={slim_rows} semantic={counts['semantic_conflicts']} "
                    f"seconds={time.time() - started:.0f}",
                    flush=True,
                )
    finally:
        db_clean.close()
        db_conflict.close()
        slim.close()


def finish() -> None:
    slim = _slim()
    try:
        progress = slim.execute("SELECT * FROM build_progress ORDER BY prefix").fetchall()
        labels: Counter = Counter()
        totals: Counter = Counter()
        for row in progress:
            totals["ledger_clean_rows"] += row[1]
            totals["ledger_conflict_rows"] += row[2]
            totals["observation_keys"] += row[3]
            totals["conflict_keys"] += row[4]
            totals["slim_rows"] += row[5]
            totals["pnus"] += row[6]
            totals["semantic_conflicts"] += row[7]
            totals["seconds"] += row[8]
            for field, code, label, n in json.loads(row[9]):
                labels[(field, code, label)] += n
        slim.execute("DELETE FROM code_dictionary")
        slim.executemany(
            "INSERT INTO code_dictionary (field, code, label, label_rows) VALUES (?,?,?,?)",
            [(f, c, lab, n) for (f, c, lab), n in labels.items()],
        )
        best: dict[tuple[str, str], tuple[int, str]] = {}
        for (field, code, label), n in labels.items():
            if not label:
                continue
            if (field, code) not in best or n > best[(field, code)][0]:
                best[(field, code)] = (n, label)
        slim.executemany(
            "UPDATE code_dictionary SET is_standard = 1 WHERE field = ? AND code = ? AND label = ?",
            [(f, c, lab) for (f, c), (_, lab) in best.items()],
        )
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        info = {
            "version": VERSION,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "ledger_sha256": freeze["ledger"]["sha256"],
            "ledger_bytes": freeze["ledger"]["bytes"],
        }
        slim.executemany("INSERT OR REPLACE INTO build_info VALUES (?, ?)", list(info.items()))
        slim.commit()
        dictionary = defaultdict(lambda: {"codes": 0, "codes_with_multiple_labels": 0})
        per_code = defaultdict(set)
        for (field, code, label) in labels:
            if label:
                per_code[(field, code)].add(label)
            else:
                per_code.setdefault((field, code), set())
        for (field, _), names in per_code.items():
            dictionary[field]["codes"] += 1
            if len(names) > 1:
                dictionary[field]["codes_with_multiple_labels"] += 1
        load = json.loads(LOAD_REPORT.read_text(encoding="utf-8"))
        report = {
            "version": VERSION,
            "slim_file": str(SLIM),
            "slim_bytes": SLIM.stat().st_size,
            "ledger_sha256": info["ledger_sha256"],
            "prefixes_done": len(progress),
            "totals": dict(totals),
            "checks": {
                "ledger_clean_rows_match_load_report": totals["ledger_clean_rows"] == load["stored_observations"],
                "ledger_conflict_rows_match_load_report": totals["ledger_conflict_rows"] == load["conflict_variants"],
                "conflict_keys_match_load_report": totals["conflict_keys"] == load["conflict_keys"],
                "observation_keys_equal_clean_plus_conflict_keys": totals["observation_keys"]
                == load["stored_observations"] + load["conflict_keys"],
                "semantic_conflicts_zero": totals["semantic_conflicts"] == 0,
            },
            "dictionary": dict(dictionary),
            "finished_at": info["built_at"],
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {REPORT}", flush=True)
    finally:
        slim.close()


def verify(prefixes: list[str]) -> dict:
    """Every ledger observation in the prefixes must come back unchanged from slim."""
    asofs = _asofs()
    bits = {asof: i for i, asof in enumerate(asofs)}
    slim = sqlite3.connect(f"file:{SLIM.as_posix()}?mode=ro", uri=True)
    db = _ledger()
    result = {"prefixes": prefixes, "ledger_keys": 0, "missing": 0, "ambiguous": 0, "different": 0, "slim_bits_unmatched": 0}
    try:
        for prefix in prefixes:
            lo, hi = _bounds(prefix)
            index: dict[tuple, list[list]] = defaultdict(list)
            for row in slim.execute(
                "SELECT pnu, price_year, price_month, asof_mask, jimok_code, area, zone1_code, zone2_code, "
                "use_code, height_code, shape_code, road_code, price FROM observation WHERE pnu >= ? AND pnu < ?",
                (int(lo), int(hi)),
            ):
                index[(row[0], row[1], row[2])].append([row[3], tuple(row[4:13]), 0])
            seen: set[tuple] = set()
            for table in ("parcel_observation", "observation_conflict"):
                for row in _stream(db, table, prefix):
                    key = (row[0], row[1], row[2], row[3])
                    if table == "observation_conflict" and key in seen:
                        continue
                    seen.add(key)
                    result["ledger_keys"] += 1
                    bit = 1 << bits[str(row[1])[:10]]
                    values = tuple(str(v if v is not None else "") for v in row[4:13])
                    hits = [e for e in index.get((int(row[0]), str(row[2]), str(row[3])), []) if e[0] & bit]
                    if not hits:
                        result["missing"] += 1
                    elif len(hits) > 1:
                        result["ambiguous"] += 1
                    elif hits[0][1] != values:
                        result["different"] += 1
                    else:
                        hits[0][2] |= bit
            for entries in index.values():
                for mask, _, matched in entries:
                    if mask != matched:
                        result["slim_bits_unmatched"] += 1
            print(f"verify {prefix} {json.dumps(result)}", flush=True)
    finally:
        slim.close()
        db.close()
    result["ok"] = not (result["missing"] or result["ambiguous"] or result["different"] or result["slim_bits_unmatched"])
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefixes", help="comma separated pnu prefixes; default all two-digit sido prefixes")
    ap.add_argument("--finish", action="store_true")
    ap.add_argument("--verify", help="comma separated sigungu prefixes to check without loss")
    ap.add_argument("--verify-out")
    ap.add_argument("--slim", help="slim file path; default the v1 location")
    args = ap.parse_args()
    if args.slim:
        global SLIM
        SLIM = Path(args.slim)
    if args.verify:
        out = verify([p.strip() for p in args.verify.split(",") if p.strip()])
        if args.verify_out:
            Path(args.verify_out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out), flush=True)
        return
    if args.finish:
        finish()
        return
    prefixes = [p.strip() for p in args.prefixes.split(",")] if args.prefixes else None
    build(prefixes)


if __name__ == "__main__":
    main()
