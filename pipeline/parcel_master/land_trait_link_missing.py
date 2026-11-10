"""Read only the PNU ranges a V1 transaction mask can match."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from contextlib import closing
from functools import lru_cache
from itertools import groupby

from sqlalchemy import text

from parcel_master import land_trait_link_materialize as v1
from parcel_master.cheongju_land_link_probe import _add_plate
from parcel_master.code_history_link_shadow import _prefixes_for
from parcel_master.national_land_link_shadow import LEDGER
from parcel_master.trait_link_helpers import lot_matches

FETCH = text("""
    SELECT t.transaction_hash, t.contract_date, t.beopjungri_code, t.sigungu_code,
           t.land_category, t.zone_type, t.area_sqm, t.is_partial_ownership,
           t.is_cancelled, t.is_valid, t.lot_display
    FROM land_transactions t
    WHERE t.contract_date >= :start AND t.contract_date < :stop
      AND NOT EXISTS (SELECT 1 FROM land_transaction_trait_link l
                      WHERE l.transaction_hash = t.transaction_hash)
      AND (:since IS NULL OR t.created_at >= CAST(:since AS timestamptz))
    ORDER BY t.sigungu_code
""")


@lru_cache(maxsize=4096)
def _lot_ranges(mask: str) -> tuple[tuple[int, int], ...]:
    kind = "2" if mask.startswith("산") else "1"
    pnu = "0" * 10 + kind + "0" * 8
    candidates = (main for main in range(10_000) if lot_matches(mask, pnu, str(main)))
    ranges = []
    for _, items in groupby(enumerate(candidates), lambda item: item[1] - item[0]):
        group = list(items)
        ranges.append((group[0][1], group[-1][1] + 1))
    return tuple(ranges)


def _ranges(code, rows, pairs):
    prefixes = set(_prefixes_for(code, pairs))
    found = defaultdict(set)
    for row in rows:
        if v1.exclusion_reason(row):
            continue
        bjd, _ = v1.resolve_beopjungri(str(row["beopjungri_code"]).strip(),
                                        str(row["contract_date"])[:10], pairs)
        if len(bjd) != 10 or not bjd.isascii() or not bjd.isdigit() or bjd[:5] not in prefixes:
            continue
        mask = str(row["lot_display"]).strip()
        kind = "2" if mask.startswith("산") else "1"
        found[bjd + kind].update(_lot_ranges(mask))
    for prefix, ranges in sorted(found.items()):
        base = int(prefix + "0" * 8)
        low = high = 0
        for start, stop in sorted(ranges):
            if start > high:
                if low < high:
                    yield f"{base + low * 10000:019d}", f"{base + high * 10000:019d}"
                low = start
            high = max(high, stop)
        if low < high:
            yield f"{base + low * 10000:019d}", f"{base + high * 10000:019d}"


def _conflicts(db, prefix, targets):
    grouped = defaultdict(list)
    keys = sorted(pnu for pnu in targets if pnu.startswith(prefix))
    for start in range(0, len(keys), 500):
        chunk = keys[start:start + 500]
        markers = ",".join("?" for _ in chunk)
        for item in db.execute(f"""
            SELECT pnu, asof, price_year, price_month, source_file,
                   jimok_code, jimok_label, area, zone1_code, zone1_label,
                   zone2_code, zone2_label, use_code, use_label, height_code, height_label,
                   shape_code, shape_label, road_code, road_label, price
            FROM observation_conflict WHERE pnu IN ({markers})
            ORDER BY pnu, asof, attr_hash
        """, chunk):
            grouped[(item[0], str(item[1])[:10], str(item[2]), str(item[3]))].append(item)
    return grouped


def classify(code, rows, pairs, db):
    plates = defaultdict(list)
    index = defaultdict(set)
    for low, high in _ranges(code, rows, pairs):
        for row in db.execute("""
            SELECT pnu, asof, price_year, price_month, jimok_label, area, zone1_label, zone2_label, price
            FROM parcel_observation WHERE pnu >= ? AND pnu < ?
        """, (low, high)):
            _add_plate(plates, index, row, prefixes=(row[0][:5],))
    for entries in plates.values():
        entries.sort()
    return v1._classify(code, plates, index, pairs, rows,
                        conflict_loader=lambda prefix, targets: _conflicts(db, prefix, targets))[0]


def missing_records(engine, start, stop, since=None):
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        pairs = v1.load_pairs(conn)
        rows = [dict(row) for row in conn.execute(
            FETCH, {"start": start, "stop": stop, "since": since}
        ).mappings()]
    records = []
    with closing(sqlite3.connect(LEDGER.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        groups = groupby(rows, lambda row: str(row["sigungu_code"] or "").strip())
        for code, group in groups:
            batch = list(group)
            if len(code) == 5 and code.isdigit():
                records.extend(classify(code, batch, pairs, db))
    return rows, records
