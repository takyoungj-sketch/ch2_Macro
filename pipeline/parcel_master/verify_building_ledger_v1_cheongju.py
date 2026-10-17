"""Replay the frozen Cheongju v2 (4,000 management keys) against building ledger v1.

Counts only; no management key or parcel number is written.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "data" / "research" / "cheongju_ledger" / "building_source_staging_v2_full.sqlite"

FIELD_INDEX = {
    "raw_sigungu": 8, "ledger_kind": 2, "ledger_type": 4, "main_aux_code": 23, "main_aux_label": 24,
    "lot_label": 5, "special_land_label": 13, "block": 14, "lot_block": 15, "related_lot_count": 16,
    "auxiliary_building_count": 47, "raw_gross_area": 28, "raw_title_area": 25,
}


def ro(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    return db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    v2 = ro(V2)
    ledger = ro(args.db)
    relation = {(s, p): pnu for s, p, pnu in v2.execute("SELECT snapshot,pk,pnu FROM canonical_address_relation")}
    result = Counter()
    field_mismatch = Counter()
    v2_status = Counter()
    rows = v2.execute(
        "SELECT o.snapshot,o.pk,o.identity_status,v.raw_payload FROM title_observation o JOIN source_version v ON v.id=o.version"
    ).fetchall()
    for snapshot, pk, status, payload in rows:
        v2_status[(snapshot, status)] += 1
        got = ledger.execute(
            "SELECT o.identity_status,o.pnu,o.column_count,v.raw FROM title_observation o "
            "JOIN title_version v USING(pk,raw_hash) WHERE o.snapshot=? AND o.pk=?",
            (snapshot, pk),
        ).fetchone()
        if got is None:
            result["missing_in_ledger"] += 1
            continue
        l_status, l_pnu, l_cols, raw = got
        result["status_match" if l_status == status else "status_mismatch"] += 1
        result["pnu_match" if l_pnu == relation.get((snapshot, pk)) else "pnu_mismatch"] += 1
        parts = raw.decode("utf-8-sig").split("|")
        expected = json.loads(payload)
        if expected.get("raw_column_count") != l_cols:
            field_mismatch["raw_column_count"] += 1
        if expected.get("raw_identity_fields") != parts[8:13]:
            field_mismatch["raw_identity_fields"] += 1
        for key, idx in FIELD_INDEX.items():
            if key in expected and expected[key] != parts[idx]:
                field_mismatch[key] += 1
    report = {
        "v2_observations": len(rows),
        "v2_canonical_relations": len(relation),
        "v2_status_by_snapshot": {f"{s}|{st}": n for (s, st), n in sorted(v2_status.items())},
        "replay": dict(result),
        "raw_field_mismatch": dict(field_mismatch),
        "pass": (
            result["missing_in_ledger"] == 0 and result["status_mismatch"] == 0
            and result["pnu_mismatch"] == 0 and not field_mismatch
        ),
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
