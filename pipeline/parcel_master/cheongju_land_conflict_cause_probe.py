"""Why pre-contract Cheongju conflict rows disagree.

Read-only. Describes which fields differ and which source ZIPs first
carried each variant. Does not choose a plate. Filename dates are not
treated as an official correction order. Parcel numbers are not written.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.cheongju_land_gap_probe import _split_candidates  # noqa: E402
from parcel_master.cheongju_land_link_probe import (  # noqa: E402
    LEDGER,
    PRICE_FROM,
    exclusion_reason,
    load_cheongju_plates,
)
from parcel_master.trait_link_helpers import area_key  # noqa: E402

REPORT = ROOT / "docs" / "lab" / "cheongju_land_conflict_cause_2019_20261016.json"
FOCUS_END = "2023-12-31"
FILE_DAY = re.compile(r"(20\d{2})(\d{2})(\d{2})")

# Indexes into a conflict row after pnu, asof, year, month, source_file.
CODE_FIELDS = {
    "jimok": 5,
    "area": 7,
    "zone1": 8,
    "zone2": 10,
    "use": 12,
    "height": 14,
    "shape": 16,
    "road": 18,
    "price": 20,
}
LABEL_FIELDS = {
    "jimok_label": 6,
    "zone1_label": 9,
    "zone2_label": 11,
    "use_label": 13,
    "height_label": 15,
    "shape_label": 17,
    "road_label": 19,
}


def _same_number(values: set[str]) -> bool:
    parsed: list[Decimal] = []
    for value in values:
        try:
            parsed.append(Decimal(value))
        except InvalidOperation:
            return False
    return len(set(parsed)) == 1


def conflict_signature(variants: list[tuple]) -> dict:
    """Describe one pnu-asof-year-month group. Does not pick a variant."""
    differing = []
    for name, index in CODE_FIELDS.items():
        if len({str(row[index]) for row in variants}) > 1:
            differing.append(name)
    label_differing = []
    for name, index in LABEL_FIELDS.items():
        if len({str(row[index]) for row in variants}) > 1:
            label_differing.append(name)
    semantic = set(differing)
    if semantic == {"area"} and _same_number({str(row[7]) for row in variants}):
        category = "area_format_only"
    elif semantic == {"price"} and _same_number({str(row[20]) for row in variants}):
        category = "price_format_only"
    elif semantic == {"price"}:
        category = "price_only"
    elif semantic <= {"zone1", "zone2"} and semantic:
        category = "zone_only"
    elif semantic == {"jimok"}:
        category = "jimok_only"
    elif semantic == {"area"}:
        category = "area_only"
    elif len(semantic) == 1:
        category = f"{next(iter(semantic))}_only"
    elif len(semantic) > 1:
        category = "multiple"
    elif label_differing:
        category = "label_only"
    else:
        category = "no_stored_difference"
    files = {str(row[4]) for row in variants}
    label_values = {
        name: sorted({str(row[index]) for row in variants})
        for name, index in LABEL_FIELDS.items()
        if name in label_differing
    }
    return {
        "category": category,
        "fields": sorted(differing),
        "label_fields": sorted(label_differing),
        "label_values": label_values,
        "variants": len(variants),
        "files": files,
        "same_zip": len(files) == 1,
    }


def file_pattern(files: set[str]) -> str:
    kinds = set()
    for name in files:
        if re.match(r"AL_4311[1-4]_", name):
            kinds.add("sigungu_2019")
        elif name.startswith("AL_43_D195_"):
            kinds.add("chungbuk")
        else:
            kinds.add("other")
    return "+".join(sorted(kinds))


def filename_day(name: str) -> str:
    match = FILE_DAY.search(name)
    if match is None:
        return ""
    return "-".join(match.groups())


def _empty() -> dict[str, int]:
    return defaultdict(int)


def summarize_conflicts(transactions: list[dict], other_presence: dict[str, int]) -> dict:
    keys = _empty()
    same_zip = _empty()
    cross_zip = _empty()
    three_or_more = _empty()
    by_year = defaultdict(_empty)
    by_asof = defaultdict(_empty)
    by_tx_year = defaultdict(_empty)
    pairs: Counter[tuple[str, ...]] = Counter()
    patterns: Counter[str] = Counter()
    label_fields = _empty()
    label_blank = _empty()
    label_both_text = _empty()
    label_pairs: dict[str, Counter[tuple[str, ...]]] = defaultdict(Counter)
    filename_dates_differ = 0
    cross_zip_keys = 0
    for row in transactions:
        by_tx_year[row["contract_year"]][row["transaction_category"]] += 1
        by_tx_year[row["contract_year"]]["transactions"] += 1
        for key in row["keys"]:
            category = key["category"]
            keys[category] += 1
            bucket = same_zip if key["same_zip"] else cross_zip
            bucket[category] += 1
            if key["variants"] >= 3:
                three_or_more[category] += 1
            by_year[key["asof"][:4]][category] += 1
            by_year[key["asof"][:4]]["keys"] += 1
            by_asof[key["asof"]][category] += 1
            by_asof[key["asof"]]["keys"] += 1
            patterns[file_pattern(key["files"])] += 1
            for field, values in key["label_values"].items():
                label_fields[field] += 1
                blank = sum(1 for value in values if value == "")
                if blank and blank < len(values):
                    label_blank[field] += 1
                elif blank == 0 and len(values) > 1:
                    label_both_text[field] += 1
                label_pairs[field][tuple(values)] += 1
            if not key["same_zip"]:
                cross_zip_keys += 1
                days = {filename_day(name) for name in key["files"]}
                if len(days - {""}) > 1:
                    filename_dates_differ += 1
                pairs[tuple(sorted(key["files"]))] += 1
    key_total = sum(keys.values())
    return {
        "place": "청주시 상당·서원·흥덕·청원",
        "scope": "2019-2023 계약. 필지가 하나이고 계약 전 행이 충돌 테이블에만 있는 거래",
        "selection_rule": "판을 고르지 않음. 파일명 날짜는 정정판 순서가 아님",
        "source_file_meaning": "각 속성 조합을 처음 실은 ZIP. 이후 ZIP의 같은 조합은 다시 기록되지 않음",
        "transactions": len(transactions),
        "conflict_keys": key_total,
        "key_categories": dict(keys),
        "same_zip": dict(same_zip),
        "different_zip": dict(cross_zip),
        "variants_3_or_more": dict(three_or_more),
        "different_zip_keys": cross_zip_keys,
        "different_zip_filename_dates_differ": filename_dates_differ,
        "file_patterns": dict(patterns),
        "label_fields": dict(label_fields),
        "label_blank_versus_text": dict(label_blank),
        "label_both_nonempty": dict(label_both_text),
        "top_label_pairs": {
            field: [
                {"values": list(values), "keys": count}
                for values, count in counter.most_common(8)
            ]
            for field, counter in sorted(label_pairs.items())
        },
        "by_contract_year": {year: dict(by_tx_year[year]) for year in sorted(by_tx_year)},
        "by_asof_year": {year: dict(by_year[year]) for year in sorted(by_year)},
        "top_asofs": [
            {"asof": asof, **counts}
            for asof, counts in sorted(by_asof.items(), key=lambda item: -item[1]["keys"])[:12]
        ],
        "top_file_pairs": [
            {"files": list(files), "keys": count}
            for files, count in pairs.most_common(20)
        ],
        "other_unlinked_presence": other_presence,
        "product_database_changed": False,
    }


def run() -> dict:
    from sqlalchemy import text

    from db_utils import get_engine

    print("loading transactions", flush=True)
    engine = get_engine()
    sql = text(
        """
        SELECT contract_date, beopjungri_code, land_category, zone_type,
               area_sqm, is_partial_ownership, is_cancelled, is_valid, lot_display
        FROM land_transactions
        WHERE sigungu_code IN ('43111','43112','43113','43114')
          AND contract_date >= :start AND contract_date <= :end
        """
    )
    pending: list[dict] = []
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        fetched = connection.execute(sql, {"start": PRICE_FROM, "end": FOCUS_END}).mappings().all()
    for record in fetched:
        row = dict(record)
        if exclusion_reason(row) or len(str(row["beopjungri_code"])) != 10:
            continue
        pending.append(row)
    plates, index, _ledger_rows = load_cheongju_plates(LEDGER)
    cases: list[tuple[str, str]] = []
    for row in pending:
        day = str(row["contract_date"])[:10]
        jimok = str(row["land_category"] or "").strip()
        area = area_key(row["area_sqm"]) or ""
        prior, later = _split_candidates(
            str(row["beopjungri_code"]),
            jimok,
            area,
            str(row["zone_type"]),
            row["lot_display"],
            day,
            index,
            plates,
        )
        if prior or len(later) != 1:
            continue
        pnu = later[0]
        if any(plate[0] <= day for plate in plates[pnu]):
            continue
        if not any(plate[0] > day for plate in plates[pnu]):
            continue
        cases.append((pnu, day))
    targets = {pnu for pnu, _day in cases}
    print(f"first_seen={len(cases)} pnus={len(targets)}", flush=True)
    grouped: dict[tuple[str, str, str, str], list[tuple]] = defaultdict(list)
    db = sqlite3.connect(f"file:{LEDGER.as_posix()}?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        cursor = db.execute(
            """
            SELECT pnu, asof, price_year, price_month, source_file,
                   jimok_code, jimok_label, area,
                   zone1_code, zone1_label, zone2_code, zone2_label,
                   use_code, use_label, height_code, height_label,
                   shape_code, shape_label, road_code, road_label, price
            FROM observation_conflict
            WHERE pnu >= '4311100000000000000' AND pnu < '4311500000000000000'
            """
        )
        seen = 0
        kept = 0
        while True:
            chunk = cursor.fetchmany(50_000)
            if not chunk:
                break
            for row in chunk:
                seen += 1
                if row[0] not in targets:
                    continue
                grouped[(row[0], str(row[1])[:10], str(row[2]), str(row[3]))].append(tuple(row))
                kept += 1
            if seen % 500_000 == 0:
                print(f"conflict rows={seen} kept={kept}", flush=True)
    finally:
        db.close()
    print(f"conflict rows={seen} kept={kept} keys={len(grouped)}", flush=True)
    by_pnu: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for (pnu, asof, _year, _month), variants in grouped.items():
        signature = conflict_signature(variants)
        signature["asof"] = asof
        signature["files"] = signature["files"]
        by_pnu[pnu].append((asof, signature))
    transactions = []
    other = _empty()
    for pnu, day in cases:
        usable = [item[1] for item in by_pnu.get(pnu, ()) if item[0] <= day]
        if not usable:
            later = [item[0] for item in by_pnu.get(pnu, ())]
            other["conflict_only_after_contract" if later else "absent_before_contract"] += 1
            continue
        categories = {item["category"] for item in usable}
        label = next(iter(categories)) if len(categories) == 1 else "mixed_keys"
        transactions.append(
            {
                "contract_year": day[:4],
                "transaction_category": label,
                "keys": usable,
            }
        )
    report = summarize_conflicts(transactions, dict(other))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["key_categories"], ensure_ascii=False), flush=True)
    return report


if __name__ == "__main__":
    run()
