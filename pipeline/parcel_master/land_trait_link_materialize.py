"""Write land-trait link rows for the transaction list.

Uses the locked history layer and link rule V1. Does not change either rule.
Does not rewrite the national ledger. Inserts into land_transaction_trait_link only.
Individual parcels are not written to the progress file or the lab report.
"""

from __future__ import annotations

import gc
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from sqlalchemy import text

from db_utils import get_engine
from parcel_master.cheongju_land_conflict_cause_probe import conflict_signature
from parcel_master.cheongju_land_gap_probe import _split_candidates
from parcel_master.cheongju_land_label_rule_probe import (
    attach_price_detail,
    classify_link_v1,
    normalized_plate,
)
from parcel_master.cheongju_land_link_probe import exclusion_reason, latest_consistent_plate
from parcel_master.code_history_link_shadow import _merge, _prefixes_for, load_pairs
from parcel_master.land_code_history_layer import resolve_beopjungri
from parcel_master.national_land_link_shadow import (
    CHEONGJU,
    CHEONGJU_2019_2023,
    PRICE_FROM,
    SIDO_NAME,
    _load_conflict,
    _load_plates,
    _write,
)
from parcel_master.trait_link_helpers import area_key

PROGRESS = Path(r"C:\CH2\parcel_master\land_trait_link_progress.json")
REPORT = ROOT / "docs" / "lab" / "land_trait_link_materialize_20261016.json"
DDL = ROOT / "db" / "073_land_transaction_trait_link.sql"
RULE_VERSION = "LAND_CODE_HISTORY_LAYER_V1+LAND_LINK_RULE_V1"
CHEONGJU_PRICE_LOCK = {
    "same_year": 17181,
    "previous_year": 3,
    "price_missing": 21,
    "price_conflict": 268,
}
INSERT = text(
    """
    INSERT INTO land_transaction_trait_link (
        transaction_hash, link_status, price_status, official_price_won, price_year,
        trait_asof, ledger_beopjungri_code, code_resolution, unverified, rule_version
    ) VALUES (
        :transaction_hash, :link_status, :price_status, :official_price_won, :price_year,
        :trait_asof, :ledger_beopjungri_code, :code_resolution, TRUE, :rule_version
    )
    ON CONFLICT (transaction_hash) DO NOTHING
    """
)


def _statements(sql: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            statement = "\n".join(buf).strip()
            if statement:
                parts.append(statement)
            buf = []
    return parts


def ensure_table(engine) -> None:
    statements = _statements(DDL.read_text(encoding="utf-8"))
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _conflict_views(grouped):
    """Same grouping as national_land_link_shadow._finish."""
    normalized = defaultdict(list)
    substantive_asofs = defaultdict(set)
    for (pnu, asof, _year, _month), variants in grouped.items():
        if conflict_signature(variants)["category"] != "label_only":
            substantive_asofs[pnu].add(asof)
            continue
        plate = normalized_plate(variants)
        if plate is not None:
            normalized[pnu].append(plate)
    for rows in normalized.values():
        rows.sort()
    conflict_asofs = defaultdict(list)
    for pnu, asof, _year, _month in grouped:
        conflict_asofs[pnu].append(asof)
    return normalized, conflict_asofs, substantive_asofs


def _trait_asof(kind: str, price_pnu: str, day: str, plates, normalized) -> str | None:
    if not price_pnu or kind not in {"exact", "label_normalized"}:
        return None
    rows = list(plates.get(price_pnu, ()))
    if kind == "label_normalized":
        rows.extend(normalized.get(price_pnu, ()))
        rows.sort()
    group = latest_consistent_plate(rows, day)
    if not group:
        return None
    return str(group[0][0])[:10]


def _load_transactions(engine, code: str) -> list[dict]:
    sql = text(
        """
        SELECT transaction_hash, contract_date, beopjungri_code, land_category, zone_type,
               area_sqm, is_partial_ownership, is_cancelled, is_valid, lot_display
        FROM land_transactions
        WHERE sigungu_code = :code AND contract_date >= :start
        """
    )
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        fetched = connection.execute(sql, {"code": code, "start": PRICE_FROM}).mappings().all()
    return [dict(row) for row in fetched]


def _classify(code: str, plates, index, pairs, fetched: list[dict]) -> tuple[list[dict], dict]:
    prepared = []
    targets: set[str] = set()
    skipped_hash = 0
    for row in fetched:
        if exclusion_reason(row) or len(str(row["beopjungri_code"]).strip()) != 10:
            continue
        digest = str(row["transaction_hash"] or "").strip()
        if len(digest) != 64:
            skipped_hash += 1
            continue
        day = str(row["contract_date"])[:10]
        original = str(row["beopjungri_code"]).strip()
        resolved, reason = resolve_beopjungri(original, day, pairs)
        jimok = str(row["land_category"] or "").strip()
        area = area_key(row["area_sqm"]) or ""
        zone = str(row["zone_type"])
        prior, later = _split_candidates(
            resolved, jimok, area, zone, row["lot_display"], day, index, plates
        )
        if len(prior) == 1:
            targets.add(prior[0])
        elif len(later) == 1:
            targets.add(later[0])
        prepared.append(
            {
                "transaction_hash": digest,
                "year": day[:4],
                "day": day,
                "jimok": jimok,
                "area": area,
                "zone": zone,
                "prior": prior,
                "later": later,
                "ledger_beopjungri_code": resolved,
                "code_resolution": reason,
            }
        )
    grouped = defaultdict(list)
    for prefix in _prefixes_for(code, pairs):
        for key, variants in _load_conflict(prefix, targets).items():
            grouped[key].extend(variants)
    normalized, conflict_asofs, substantive_asofs = _conflict_views(grouped)
    records: list[dict] = []
    counts: dict[str, int] = defaultdict(int)
    by_year: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    price: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in prepared:
        kind, price_pnu = classify_link_v1(
            day=row["day"],
            jimok=row["jimok"],
            area=row["area"],
            zone=row["zone"],
            prior=row["prior"],
            later=row["later"],
            plates=plates,
            normalized=normalized,
            conflict_asofs=conflict_asofs,
            substantive_asofs=substantive_asofs,
        )
        if price_pnu:
            price_status, amount, price_year = attach_price_detail(
                plates[price_pnu] + normalized.get(price_pnu, []), int(row["year"])
            )
        else:
            price_status, amount, price_year = "none", None, None
        counts[kind] += 1
        by_year[row["year"]][kind] += 1
        by_year[row["year"]]["comparable"] += 1
        if price_pnu:
            price[row["year"]][price_status] += 1
        records.append(
            {
                "transaction_hash": row["transaction_hash"],
                "link_status": kind,
                "price_status": price_status,
                "official_price_won": amount,
                "price_year": price_year,
                "trait_asof": _trait_asof(kind, price_pnu, row["day"], plates, normalized),
                "ledger_beopjungri_code": row["ledger_beopjungri_code"],
                "code_resolution": row["code_resolution"],
                "rule_version": RULE_VERSION,
            }
        )
    summary = {
        "transactions": len(prepared),
        "skipped_hash": skipped_hash,
        "counts": dict(counts),
        "by_year": {year: dict(bucket) for year, bucket in by_year.items()},
        "price": {year: dict(bucket) for year, bucket in price.items()},
    }
    return records, summary


def _cheongju_check(blocks: dict) -> None:
    totals: dict[str, int] = defaultdict(int)
    price_totals: dict[str, int] = defaultdict(int)
    for code in CHEONGJU:
        for year, bucket in blocks[code]["by_year"].items():
            if not "2019" <= year <= "2023":
                continue
            for key, value in bucket.items():
                if key != "comparable":
                    totals[key] += value
        for year, bucket in blocks[code]["price"].items():
            if not "2019" <= year <= "2023":
                continue
            for key, value in bucket.items():
                price_totals[key] += value
    mismatched = {
        key: (totals.get(key, 0), expected)
        for key, expected in CHEONGJU_2019_2023.items()
        if totals.get(key, 0) != expected
    }
    price_mismatch = {
        key: (price_totals.get(key, 0), expected)
        for key, expected in CHEONGJU_PRICE_LOCK.items()
        if price_totals.get(key, 0) != expected
    }
    if totals.get("true_conflict", 0) != 0:
        mismatched["true_conflict"] = (totals.get("true_conflict", 0), 0)
    if mismatched or price_mismatch:
        raise SystemExit(
            "cheongju V1 mismatch "
            + json.dumps({"link": mismatched, "price": price_mismatch}, ensure_ascii=False)
        )
    print("cheongju V1 check ok", flush=True)


def _insert(engine, records: list[dict]) -> None:
    if not records:
        return
    with engine.begin() as connection:
        for start in range(0, len(records), 2000):
            connection.execute(INSERT, records[start : start + 2000])


def _sigungu_codes(engine) -> list[str]:
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        rows = connection.execute(
            text(
                """
                SELECT sigungu_code
                FROM land_transactions
                WHERE contract_date >= :start
                GROUP BY sigungu_code
                ORDER BY sigungu_code
                """
            ),
            {"start": PRICE_FROM},
        ).all()
    codes = [str(code).strip() for (code,) in rows if len(str(code).strip()) == 5]
    return [code for code in CHEONGJU if code in codes] + [code for code in codes if code not in CHEONGJU]


def _summary(done: dict) -> dict:
    by_sido: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    price_sido: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    transactions = 0
    for code, block in done.items():
        sido = str(code)[:2]
        transactions += int(block.get("transactions") or 0)
        for key, value in block.get("counts", {}).items():
            by_sido[sido][key] += int(value)
        comparable = sum(bucket.get("comparable", 0) for bucket in block.get("by_year", {}).values())
        by_sido[sido]["comparable"] += comparable
        for bucket in block.get("price", {}).values():
            for key, value in bucket.items():
                price_sido[sido][key] += int(value)
    return {
        "rule_version": RULE_VERSION,
        "mode": "product_list_link",
        "contract_date_from": PRICE_FROM,
        "product_table": "land_transaction_trait_link",
        "product_source_updated": False,
        "national_ledger_rewritten": False,
        "regional_exceptions_added": False,
        "cheongju_v1_check": True,
        "transactions": transactions,
        "by_sido": {
            code: {"name": SIDO_NAME.get(code, code), **counts}
            for code, counts in sorted(by_sido.items())
        },
        "price_by_sido": {code: dict(counts) for code, counts in sorted(price_sido.items())},
    }


def run() -> None:
    engine = get_engine()
    try:
        ensure_table(engine)
        print("table ready", flush=True)
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            pairs = load_pairs(connection)
        codes = _sigungu_codes(engine)
        done = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {}
        print(f"pairs={len(pairs)} sigungu={len(codes)} done={len(done)}", flush=True)
        pending: dict[str, tuple[list[dict], dict]] = {}
        for index, code in enumerate(codes, start=1):
            if code in done:
                continue
            started = time.perf_counter()
            plates: dict = defaultdict(list)
            plate_index: dict = defaultdict(set)
            ledger_rows = 0
            for prefix in _prefixes_for(code, pairs):
                extra_plates, extra_index, seen = _load_plates(prefix)
                _merge(plates, plate_index, extra_plates, extra_index)
                ledger_rows += seen
                del extra_plates, extra_index
            for rows_for_pnu in plates.values():
                rows_for_pnu.sort()
            fetched = _load_transactions(engine, code)
            records, summary = _classify(code, plates, plate_index, pairs, fetched)
            summary["ledger_rows"] = ledger_rows
            del plates, plate_index, fetched
            gc.collect()
            if code in CHEONGJU:
                pending[code] = (records, summary)
                ready = {item: done[item] for item in CHEONGJU if item in done}
                ready.update({item: pending[item][1] for item in pending})
                if any(item not in ready for item in CHEONGJU):
                    print(
                        f"{index}/{len(codes)} {code} held-for-check tx={summary['transactions']} "
                        f"seconds={time.perf_counter() - started:.0f}",
                        flush=True,
                    )
                    continue
                _cheongju_check(ready)
                for item in CHEONGJU:
                    if item in done:
                        continue
                    item_records, item_summary = pending[item]
                    _insert(engine, item_records)
                    done[item] = item_summary
                pending.clear()
                _write(PROGRESS, done)
                print(
                    f"{index}/{len(codes)} {code} cheongju-written seconds={time.perf_counter() - started:.0f}",
                    flush=True,
                )
                continue
            _insert(engine, records)
            done[code] = summary
            _write(PROGRESS, done)
            print(
                f"{index}/{len(codes)} {code} tx={summary['transactions']} ledger={ledger_rows} "
                f"seconds={time.perf_counter() - started:.0f}",
                flush=True,
            )
            del records
            gc.collect()
        if any(code not in done for code in CHEONGJU):
            raise SystemExit("cheongju rows were not written")
        _write(REPORT, _summary(done))
        print(f"wrote {REPORT}", flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    run()
