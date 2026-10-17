"""National shadow of land link rule V1.

Read-only. One sigungu at a time. Writes counts only.
Does not change the rule, the national ledger, or the product database.
"""

from __future__ import annotations

import gc
import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.cheongju_land_conflict_cause_probe import conflict_signature  # noqa: E402
from parcel_master.cheongju_land_gap_probe import _split_candidates  # noqa: E402
from parcel_master.cheongju_land_label_rule_probe import (  # noqa: E402
    attach_price,
    classify_link_v1,
    normalized_plate,
)
from parcel_master.cheongju_land_link_probe import (  # noqa: E402
    LEDGER,
    _add_plate,
    exclusion_reason,
)
from parcel_master.trait_link_helpers import area_key  # noqa: E402

PROGRESS = Path(r"C:\CH2\parcel_master\land_link_v1_shadow_progress.json")
REPORT = ROOT / "docs" / "lab" / "land_link_v1_national_shadow_20261016.json"
PRICE_FROM = "2019-01-01"
CHEONGJU = ("43111", "43112", "43113", "43114")
CHEONGJU_2019_2023 = {
    "exact": 3137,
    "multiple_candidates": 381,
    "other_unmatched": 3772,
    "label_normalized": 14336,
    "label_normalized_traits_differ": 669,
    "post_contract_only": 1594,
    "no_precontract_observation": 1131,
    "clean_precontract_traits_differ": 3088,
}
SIDO_NAME = {
    "11": "서울",
    "12": "전남광주",
    "26": "부산",
    "27": "대구",
    "28": "인천",
    "29": "광주",
    "30": "대전",
    "31": "울산",
    "36": "세종",
    "41": "경기",
    "42": "강원",
    "43": "충북",
    "44": "충남",
    "45": "전북",
    "46": "전남",
    "47": "경북",
    "48": "경남",
    "50": "제주",
    "51": "강원",
    "52": "전북",
}


def _bounds(code: str) -> tuple[str, str]:
    return code + "0" * 14, f"{int(code) + 1:05d}" + "0" * 14


def _load_plates(code: str) -> tuple[dict, dict, int]:
    lo, hi = _bounds(code)
    plates: dict = defaultdict(list)
    index: dict = defaultdict(set)
    db = sqlite3.connect(f"file:{LEDGER.as_posix()}?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        cursor = db.execute(
            """
            SELECT pnu, asof, price_year, price_month, jimok_label, area,
                   zone1_label, zone2_label, price
            FROM parcel_observation
            WHERE pnu >= ? AND pnu < ?
            """,
            (lo, hi),
        )
        seen = 0
        while True:
            chunk = cursor.fetchmany(100_000)
            if not chunk:
                break
            for row in chunk:
                _add_plate(plates, index, row, prefixes=(code,))
                seen += 1
    finally:
        db.close()
    for rows in plates.values():
        rows.sort()
    return plates, index, seen


def _load_conflict(code: str, targets: set[str]) -> dict:
    lo, hi = _bounds(code)
    grouped: dict = defaultdict(list)
    if not targets:
        return grouped
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
            WHERE pnu >= ? AND pnu < ?
            """,
            (lo, hi),
        )
        while True:
            chunk = cursor.fetchmany(50_000)
            if not chunk:
                break
            for item in chunk:
                if item[0] in targets:
                    grouped[(item[0], str(item[1])[:10], str(item[2]), str(item[3]))].append(tuple(item))
    finally:
        db.close()
    return grouped


def _prepare(code: str, plates, index) -> tuple[list[dict], set[str]]:
    from sqlalchemy import text

    from db_utils import get_engine

    engine = get_engine()
    sql = text(
        """
        SELECT contract_date, beopjungri_code, land_category, zone_type,
               area_sqm, is_partial_ownership, is_cancelled, is_valid, lot_display
        FROM land_transactions
        WHERE sigungu_code = :code AND contract_date >= :start
        """
    )
    prepared: list[dict] = []
    targets: set[str] = set()
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        fetched = connection.execute(sql, {"code": code, "start": PRICE_FROM}).mappings().all()
    for record in fetched:
        row = dict(record)
        if exclusion_reason(row) or len(str(row["beopjungri_code"])) != 10:
            continue
        day = str(row["contract_date"])[:10]
        jimok = str(row["land_category"] or "").strip()
        area = area_key(row["area_sqm"]) or ""
        prior, later = _split_candidates(
            str(row["beopjungri_code"]), jimok, area, str(row["zone_type"]), row["lot_display"], day, index, plates
        )
        if len(prior) == 1:
            targets.add(prior[0])
        elif len(later) == 1:
            targets.add(later[0])
        prepared.append(
            {
                "year": day[:4],
                "day": day,
                "jimok": jimok,
                "area": area,
                "zone": str(row["zone_type"]),
                "prior": prior,
                "later": later,
            }
        )
    return prepared, targets


def _finish(prepared, plates, grouped) -> dict:
    normalized: dict = defaultdict(list)
    substantive_asofs: dict = defaultdict(set)
    for (pnu, asof, _year, _month), variants in grouped.items():
        if conflict_signature(variants)["category"] != "label_only":
            substantive_asofs[pnu].add(asof)
            continue
        plate = normalized_plate(variants)
        if plate is not None:
            normalized[pnu].append(plate)
    for rows in normalized.values():
        rows.sort()
    conflict_asofs: dict = defaultdict(list)
    for pnu, asof, _year, _month in grouped:
        conflict_asofs[pnu].append(asof)
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
        counts[kind] += 1
        by_year[row["year"]][kind] += 1
        by_year[row["year"]]["comparable"] += 1
        if price_pnu:
            price_kind = attach_price(plates[price_pnu] + normalized.get(price_pnu, []), int(row["year"]))
            price[row["year"]][price_kind] += 1
            price[row["year"]]["priced_transactions"] += 1
    return {"counts": dict(counts), "by_year": {year: dict(bucket) for year, bucket in by_year.items()}, "price": {year: dict(bucket) for year, bucket in price.items()}}


def _cheongju_check(done: dict) -> None:
    if any(code not in done for code in CHEONGJU):
        return
    totals: dict[str, int] = defaultdict(int)
    for code in CHEONGJU:
        for year, bucket in done[code]["by_year"].items():
            if not "2019" <= year <= "2023":
                continue
            for key, value in bucket.items():
                if key != "comparable":
                    totals[key] += value
    mismatched = {key: (totals[key], CHEONGJU_2019_2023[key]) for key in CHEONGJU_2019_2023 if totals[key] != CHEONGJU_2019_2023[key]}
    if mismatched:
        raise SystemExit(f"cheongju V1 mismatch {json.dumps(mismatched, ensure_ascii=False)}")
    print("cheongju V1 check ok", flush=True)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _summary(done: dict) -> dict:
    by_sido: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_sido_year: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    price_sido: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    price_sido_year: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for code, block in done.items():
        sido = code[:2]
        for key, value in block["counts"].items():
            by_sido[sido][key] += value
        comparable = sum(bucket.get("comparable", 0) for bucket in block["by_year"].values())
        by_sido[sido]["comparable"] += comparable
        for year, bucket in block["by_year"].items():
            for key, value in bucket.items():
                by_sido_year[sido][year][key] += value
        for year, bucket in block["price"].items():
            for key, value in bucket.items():
                price_sido[sido][key] += value
                price_sido_year[sido][year][key] += value
    return {
        "rule_version": "LAND_LINK_RULE_V1",
        "mode": "shadow",
        "contract_date_from": PRICE_FROM,
        "product_database_changed": False,
        "national_ledger_rewritten": False,
        "regional_rules_added": False,
        "by_sido": {
            code: {"name": SIDO_NAME.get(code, code), **counts}
            for code, counts in sorted(by_sido.items())
        },
        "by_sido_year": {
            code: {"name": SIDO_NAME.get(code, code), "years": {year: dict(bucket) for year, bucket in sorted(years.items())}}
            for code, years in sorted(by_sido_year.items())
        },
        "price_by_sido": {code: dict(counts) for code, counts in sorted(price_sido.items())},
        "price_by_sido_year": {
            code: {year: dict(bucket) for year, bucket in sorted(years.items())}
            for code, years in sorted(price_sido_year.items())
        },
    }


def run() -> None:
    from sqlalchemy import text

    from db_utils import get_engine

    engine = get_engine()
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        rows = connection.execute(
            text(
                """
                SELECT sigungu_code, COUNT(*)
                FROM land_transactions
                WHERE contract_date >= :start
                GROUP BY sigungu_code
                ORDER BY sigungu_code
                """
            ),
            {"start": PRICE_FROM},
        ).all()
    codes = [str(code) for code, _count in rows if str(code).isdigit() and len(str(code)) == 5]
    done = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {}
    print(f"sigungu={len(codes)} done={len(done)}", flush=True)
    for index, code in enumerate(codes, start=1):
        if code in done:
            continue
        started = time.perf_counter()
        plates, plate_index, ledger_rows = _load_plates(code)
        prepared, targets = _prepare(code, plates, plate_index)
        grouped = _load_conflict(code, targets)
        done[code] = _finish(prepared, plates, grouped)
        done[code]["ledger_rows"] = ledger_rows
        done[code]["transactions"] = len(prepared)
        _write(PROGRESS, done)
        if code in CHEONGJU and all(item in done for item in CHEONGJU):
            _cheongju_check(done)
        print(
            f"{index}/{len(codes)} {code} tx={len(prepared)} ledger={ledger_rows} seconds={time.perf_counter() - started:.0f}",
            flush=True,
        )
        del plates, plate_index, prepared, targets, grouped
        gc.collect()
    _write(REPORT, _summary(done))
    print(f"wrote {REPORT}", flush=True)


if __name__ == "__main__":
    run()
