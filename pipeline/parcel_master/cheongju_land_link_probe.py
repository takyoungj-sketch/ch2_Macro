"""Cheongju land-transaction link probe against the national trait ledger.

Read-only on the product database. Counts unverified single candidates,
multiple candidates, and transactions whose only matches are plates after
the contract date. A single candidate is not a confirmed match.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from constants import LAND_CATEGORY_COMPACT_MAP, ZONE_TYPE_COMPACT_MAP
from parcel_master.trait_link_helpers import area_key, lot_matches

LEDGER = Path(r"C:\CH2\parcel_master\land_trait_observations.sqlite")
REPORT = ROOT / "docs" / "lab" / "cheongju_land_link_probe_20261016.json"
PRICE_REPORT = ROOT / "docs" / "lab" / "cheongju_land_price_link_2019_20261016.json"
REFERENCE_REPORT = ROOT / "docs" / "lab" / "cheongju_land_price_reference_year_2019_20261016.json"
FIRST_ASOF = "2017-10-17"
PRICE_FROM = "2019-01-01"
CHEONGJU = ("43111", "43112", "43113", "43114")
SUPPORTED_ZONES = set(ZONE_TYPE_COMPACT_MAP.values())

# asof, year, month, jimok, area, zones, price
Plate = tuple[str, int, int, str, str, frozenset[str], str]


def compact_jimok(label: str) -> str:
    text = (label or "").strip()
    return LAND_CATEGORY_COMPACT_MAP.get(text, text)


def compact_zones(zone1: str, zone2: str) -> frozenset[str]:
    found = set()
    for label in (zone1, zone2):
        compact = ZONE_TYPE_COMPACT_MAP.get((label or "").strip())
        if compact:
            found.add(compact)
    return frozenset(found)


def zone_source(zone1: str, zone2: str) -> str:
    """blank: both labels empty. unmapped: text present but not a known zone code. mapped: known code."""
    labels = [str(zone1 or "").strip(), str(zone2 or "").strip()]
    present = [label for label in labels if label]
    if not present:
        return "blank"
    if compact_zones(zone1, zone2):
        return "mapped"
    return "unmapped"


def synthetic_lot(pnu: str) -> str:
    return str(int(pnu[11:15]))


def _group_asof(rows: list[Plate], asof: str) -> list[Plate] | None:
    group = [row for row in rows if row[0] == asof]
    attrs = {(row[3], row[4], row[5]) for row in group}
    if len(attrs) != 1:
        return None
    return group


def latest_consistent_plate(rows: list[Plate], day: str) -> list[Plate] | None:
    chosen = None
    for row in rows:
        if row[0] <= day:
            chosen = row[0]
        else:
            break
    if chosen is None:
        return None
    return _group_asof(rows, chosen)


def _matches(group: list[Plate], jimok: str, area: str, zone: str) -> bool:
    row = group[0]
    return row[3] == jimok and row[4] == area and zone in row[5]


def _later_match(rows: list[Plate], day: str, jimok: str, area: str, zone: str) -> bool:
    seen: set[str] = set()
    for row in rows:
        if row[0] <= day or row[0] in seen:
            continue
        seen.add(row[0])
        group = _group_asof(rows, row[0])
        if group and _matches(group, jimok, area, zone):
            return True
    return False


def classify_link(
    *,
    beopjungri_code: str,
    land_category: str,
    zone_type: str,
    area_sqm: object,
    lot_display: object,
    contract_date: str,
    index: dict[tuple[str, str, str], set[str]],
    plates: dict[str, list[Plate]],
) -> dict:
    """Return the link status for one comparable transaction."""
    jimok = str(land_category or "").strip()
    area = area_key(area_sqm)
    day = str(contract_date)[:10]
    prior: list[str] = []
    later: list[str] = []
    chosen: list[Plate] | None = None
    for pnu in index.get((str(beopjungri_code), jimok, area or ""), ()):
        if area is None or not lot_matches(lot_display, pnu, synthetic_lot(pnu)):
            continue
        rows = plates[pnu]
        group = latest_consistent_plate(rows, day)
        if group and _matches(group, jimok, area, str(zone_type)):
            prior.append(pnu)
            chosen = group
            continue
        if _later_match(rows, day, jimok, area, str(zone_type)):
            later.append(pnu)
    if len(prior) == 1 and chosen is not None:
        contract_year = int(day[:4])
        priced = [row for row in chosen if row[1] <= contract_year]
        picked = max(priced, key=lambda row: (row[1], row[2])) if priced else None
        return {
            "status": "unique_unverified",
            "candidate_count": 1,
            "later_count": len(later),
            "pnu": prior[0],
            "trait_asof": chosen[0][0],
            "price_year": "" if picked is None else str(picked[1]),
            "price": "" if picked is None else picked[6],
            "price_on_or_before_contract_year": picked is not None,
        }
    if len(prior) > 1:
        return {
            "status": "multiple_candidates",
            "candidate_count": len(prior),
            "later_count": len(later),
            "trait_asof": "",
            "price_year": "",
            "price": "",
            "price_on_or_before_contract_year": False,
        }
    if later:
        return {
            "status": "no_prior_plate",
            "candidate_count": 0,
            "later_count": len(later),
            "trait_asof": "",
            "price_year": "",
            "price": "",
            "price_on_or_before_contract_year": False,
        }
    return {
        "status": "no_candidate",
        "candidate_count": 0,
        "later_count": 0,
        "trait_asof": "",
        "price_year": "",
        "price": "",
        "price_on_or_before_contract_year": False,
    }


def _prices_for_year(rows: list[Plate], year: int) -> tuple[str, str, str]:
    found: list[tuple[str, str]] = []
    for row in rows:
        if row[1] != year:
            continue
        amount = str(row[6] or "").strip()
        if not amount:
            continue
        found.append((row[0], amount))
    if not found:
        return "missing", "", ""
    amounts = {amount for _, amount in found}
    if len(amounts) != 1:
        return "conflict", "", ""
    return "value", amounts.pop(), min(asof for asof, _ in found)


def reference_year_price(rows: list[Plate], contract_year: int, contract_day: str) -> dict:
    """Official price by reference year, independent of the plate's publication date.

    The same reference year wins. The previous year is only a labeled fallback.
    A conflicting amount for the chosen year is not replaced by an older year.
    """
    for year, rule in ((contract_year, "same_year"), (contract_year - 1, "previous_year")):
        status, amount, asof = _prices_for_year(rows, year)
        if status == "missing":
            continue
        if status == "conflict":
            return {
                "price_rule": "conflict",
                "reference_year": str(year),
                "reference_price": "",
                "reference_asof": "",
                "reference_after_contract": False,
            }
        return {
            "price_rule": rule,
            "reference_year": str(year),
            "reference_price": amount,
            "reference_asof": asof,
            "reference_after_contract": asof > contract_day,
        }
    return {
        "price_rule": "price_missing",
        "reference_year": "",
        "reference_price": "",
        "reference_asof": "",
        "reference_after_contract": False,
    }


def exclusion_reason(row: dict) -> str:
    if row.get("is_cancelled") is True:
        return "cancelled"
    if row.get("is_valid") is False:
        return "invalid"
    if row.get("is_partial_ownership") is True:
        return "partial"
    if str(row.get("zone_type") or "") not in SUPPORTED_ZONES:
        return "unsupported_zone"
    lot = str(row.get("lot_display") or "").removeprefix("산").strip()
    if not re.fullmatch(r"[0-9*]+", lot):
        return "unsupported_lot"
    if area_key(row.get("area_sqm")) is None:
        return "missing_area"
    return ""


def _remember_zone(zone_state: dict[tuple[str, str], str], pnu: str, asof: str, state: str) -> None:
    key = (pnu, asof)
    previous = zone_state.get(key)
    if previous is None or previous == state:
        zone_state[key] = state
    else:
        zone_state[key] = "mixed"


def _add_plate(
    plates: dict[str, list[Plate]],
    index: dict[tuple[str, str, str], set[str]],
    row: tuple,
    zone_state: dict[tuple[str, str], str] | None = None,
    unmapped: dict[tuple[str, str], int] | None = None,
    prefixes: tuple[str, ...] | None = None,
) -> None:
    pnu, asof, year_text, month_text, jimok_label, area, zone1, zone2, price = row
    allowed = CHEONGJU if prefixes is None else prefixes
    if len(pnu) != 19 or pnu[:5] not in allowed:
        return
    jimok = compact_jimok(jimok_label)
    area_text = area_key(area)
    if not jimok or area_text is None:
        return
    try:
        year = int(year_text)
        month = int(month_text)
    except (TypeError, ValueError):
        return
    plate: Plate = (
        str(asof)[:10],
        year,
        month,
        jimok,
        area_text,
        compact_zones(zone1, zone2),
        str(price or ""),
    )
    plates[pnu].append(plate)
    index[(pnu[:10], jimok, area_text)].add(pnu)
    if zone_state is not None:
        state = zone_source(zone1, zone2)
        _remember_zone(zone_state, pnu, plate[0], state)
        if state == "unmapped" and unmapped is not None:
            unmapped[(str(zone1 or "").strip(), str(zone2 or "").strip())] += 1


def load_cheongju_plates(
    db_path: Path,
    zone_state: dict[tuple[str, str], str] | None = None,
    unmapped: dict[tuple[str, str], int] | None = None,
) -> tuple[dict[str, list[Plate]], dict[tuple[str, str, str], set[str]], int]:
    plates: dict[str, list[Plate]] = defaultdict(list)
    index: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    db = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        cursor = db.execute(
            """
            SELECT pnu, asof, price_year, price_month, jimok_label, area,
                   zone1_label, zone2_label, price
            FROM parcel_observation
            WHERE pnu >= '4311100000000000000' AND pnu < '4311500000000000000'
            """
        )
        seen = 0
        while True:
            chunk = cursor.fetchmany(100_000)
            if not chunk:
                break
            for row in chunk:
                _add_plate(plates, index, row, zone_state, unmapped)
                seen += 1
            if seen % 500_000 == 0:
                print(f"ledger rows={seen} parcels={len(plates)}", flush=True)
    finally:
        db.close()
    for rows in plates.values():
        rows.sort()
    print(f"ledger rows={seen} parcels={len(plates)}", flush=True)
    return plates, index, seen


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def official_price_summary(results: list[dict]) -> dict:
    """Price attachment for contracts from 2019, when the 7-year window can be analyzed.

    A price is attached only for one prior plate. The year is the latest official
    price year on that plate that is not after the contract year. Same year means
    that year's price was already on a plate dated on or before the contract.
    """
    window = [row for row in results if str(row.get("contract_date") or "")[:10] >= PRICE_FROM]
    by_status: dict[str, int] = defaultdict(int)
    lag_counts: dict[str, int] = defaultdict(int)
    by_year: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_month: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in window:
        by_status[row["status"]] += 1
        day = str(row["contract_date"])[:10]
        year = day[:4]
        month = day[5:7]
        bucket = by_year[year]
        month_bucket = by_month[month]
        bucket["comparable"] += 1
        month_bucket["comparable"] += 1
        price_year = str(row.get("price_year") or "")
        price = str(row.get("price") or "")
        attached = (
            row["status"] == "unique_unverified"
            and bool(price_year)
            and bool(price)
            and row.get("price_on_or_before_contract_year") is True
        )
        if not attached:
            bucket["no_price"] += 1
            month_bucket["no_price"] += 1
            continue
        lag = int(year) - int(price_year)
        if lag < 0:
            bucket["no_price"] += 1
            month_bucket["no_price"] += 1
            continue
        label = "same_year" if lag == 0 else "previous_year" if lag == 1 else "two_or_more_years_behind"
        lag_counts[label] += 1
        bucket[label] += 1
        month_bucket[label] += 1
        bucket["attached"] += 1
        month_bucket["attached"] += 1
    comparable = len(window)
    attached_total = sum(lag_counts.values())
    return {
        "contract_date_from": PRICE_FROM,
        "why_2019": "토지 7년 롤링창으로 통계가 가능한 첫 해",
        "rule": "후보가 하나인 거래만. 계약일 이전 판에서 계약연도 이하인 가장 늦은 공시지가",
        "comparable": comparable,
        "attached": attached_total,
        "attached_share": None if comparable == 0 else round(attached_total / comparable, 4),
        "same_year": lag_counts["same_year"],
        "previous_year": lag_counts["previous_year"],
        "two_or_more_years_behind": lag_counts["two_or_more_years_behind"],
        "same_year_share_of_comparable": None if comparable == 0 else round(lag_counts["same_year"] / comparable, 4),
        "previous_year_share_of_comparable": None if comparable == 0 else round(lag_counts["previous_year"] / comparable, 4),
        "same_year_share_of_attached": None if attached_total == 0 else round(lag_counts["same_year"] / attached_total, 4),
        "link_counts": {
            "unique_unverified": by_status["unique_unverified"],
            "multiple_candidates": by_status["multiple_candidates"],
            "no_prior_plate": by_status["no_prior_plate"],
            "no_candidate": by_status["no_candidate"],
        },
        "by_contract_year": {year: dict(by_year[year]) for year in sorted(by_year)},
        "by_contract_month": {month: dict(by_month[month]) for month in sorted(by_month)},
        "unique_is_not_success": True,
    }


def _share(count: int, total: int) -> float | None:
    if total == 0:
        return None
    return round(count / total, 4)


def reference_price_summary(results: list[dict]) -> dict:
    """2019+ contracts. Traits stay pre-contract. Price uses the reference year."""
    window = [row for row in results if str(row.get("contract_date") or "")[:10] >= PRICE_FROM]
    counts: dict[str, int] = defaultdict(int)
    by_year: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in window:
        year = str(row["contract_date"])[:4]
        bucket = by_year[year]
        bucket["comparable"] += 1
        link = row["status"]
        if link == "multiple_candidates":
            key = "multiple_candidates"
        elif link == "no_prior_plate":
            key = "no_prior_plate"
        elif link == "no_candidate":
            key = "no_candidate"
        elif link == "unique_unverified":
            key = str(row.get("price_rule") or "price_missing")
            if row.get("reference_after_contract") is True and key == "same_year":
                counts["same_year_from_later_plate"] += 1
                bucket["same_year_from_later_plate"] += 1
        else:
            key = "price_missing"
        counts[key] += 1
        bucket[key] += 1
    comparable = len(window)
    parcel_not_found = counts["no_prior_plate"] + counts["no_candidate"]
    keys = (
        "same_year",
        "previous_year",
        "price_missing",
        "conflict",
        "no_prior_plate",
        "no_candidate",
        "multiple_candidates",
    )
    return {
        "contract_date_from": PRICE_FROM,
        "rule": "필지는 계약일 이전 판. 공시지가는 계약연도와 같은 기준연도, 없으면 직전 연도만",
        "as_of_available_report": str(PRICE_REPORT),
        "comparable": comparable,
        "same_year": counts["same_year"],
        "previous_year_fallback": counts["previous_year"],
        "parcel_found_price_missing": counts["price_missing"],
        "price_conflict": counts["conflict"],
        "parcel_not_found": parcel_not_found,
        "parcel_not_found_no_prior_plate": counts["no_prior_plate"],
        "parcel_not_found_no_candidate": counts["no_candidate"],
        "multiple_candidates": counts["multiple_candidates"],
        "same_year_from_later_plate": counts["same_year_from_later_plate"],
        "shares_of_comparable": {key: _share(counts[key], comparable) for key in keys},
        "shares": {
            "same_year": _share(counts["same_year"], comparable),
            "previous_year_fallback": _share(counts["previous_year"], comparable),
            "parcel_found_price_missing": _share(counts["price_missing"], comparable),
            "price_conflict": _share(counts["conflict"], comparable),
            "parcel_not_found": _share(parcel_not_found, comparable),
            "multiple_candidates": _share(counts["multiple_candidates"], comparable),
        },
        "by_contract_year": {year: dict(by_year[year]) for year in sorted(by_year)},
        "unique_is_not_success": True,
        "product_database_changed": False,
    }


def summarize(results: list[dict], exclusions: dict[str, int], ledger_rows: int, parcels: int) -> dict:
    comparable = [row for row in results if not str(row["status"]).startswith("excluded_")]
    counts: dict[str, int] = defaultdict(int)
    areas: dict[str, list[float]] = defaultdict(list)
    prices: dict[str, list[float]] = defaultdict(list)
    for row in comparable:
        counts[row["status"]] += 1
        if row.get("area_sqm") is not None:
            areas[row["status"]].append(float(row["area_sqm"]))
        if row.get("unit_price_per_sqm") is not None:
            prices[row["status"]].append(float(row["unit_price_per_sqm"]))
    return {
        "run_date": date.today().isoformat(),
        "scope": {
            "place": "청주시 상당·서원·흥덕·청원",
            "sigungu_codes": list(CHEONGJU),
            "contract_date_from": FIRST_ASOF,
            "ledger": str(LEDGER),
            "match": "법정동, 지목, 면적(소수 1자리), 산 여부, 본번 마스킹, 용도지역",
            "plate": "계약일 이전 데이터기준일자 중 가장 늦은 판",
            "price_year": "그 판에서 계약연도 이전인 기준연도 중 가장 늦은 연도",
            "verification": "unverified",
        },
        "ledger_rows_read": ledger_rows,
        "ledger_parcels": parcels,
        "transaction_rows": len(results) + sum(exclusions.values()),
        "excluded": exclusions,
        "comparable": len(comparable),
        "counts": {
            "unique_unverified": counts["unique_unverified"],
            "multiple_candidates": counts["multiple_candidates"],
            "no_prior_plate": counts["no_prior_plate"],
            "no_candidate": counts["no_candidate"],
        },
        "median_area_sqm": {key: _median(values) for key, values in areas.items()},
        "median_unit_price_per_sqm": {key: _median(values) for key, values in prices.items()},
        "unique_is_not_success": True,
        "product_database_changed": False,
    }


def run() -> dict:
    from sqlalchemy import text

    from db_utils import get_engine

    print("loading transactions", flush=True)
    engine = get_engine()
    sql = text(
        """
        SELECT transaction_hash, contract_date, contract_year, beopjungri_code,
               land_category, zone_type, area_sqm, unit_price_per_sqm,
               is_partial_ownership, is_cancelled, is_valid, lot_display
        FROM land_transactions
        WHERE sigungu_code IN ('43111','43112','43113','43114')
          AND contract_date >= :start
        """
    )
    pending: list[dict] = []
    exclusions: dict[str, int] = defaultdict(int)
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        fetched = connection.execute(sql, {"start": FIRST_ASOF}).mappings().all()
    for record in fetched:
        row = dict(record)
        reason = exclusion_reason(row)
        if reason:
            exclusions[reason] += 1
            continue
        if len(str(row["beopjungri_code"])) != 10:
            exclusions["unexpected_beopjungri_length"] += 1
            continue
        pending.append(row)
    print(f"transactions comparable={len(pending)} excluded={sum(exclusions.values())}", flush=True)
    print("loading cheongju plates", flush=True)
    plates, index, ledger_rows = load_cheongju_plates(LEDGER)
    results: list[dict] = []
    for row in pending:
        outcome = classify_link(
            beopjungri_code=str(row["beopjungri_code"]),
            land_category=str(row["land_category"]),
            zone_type=str(row["zone_type"]),
            area_sqm=row["area_sqm"],
            lot_display=row["lot_display"],
            contract_date=str(row["contract_date"]),
            index=index,
            plates=plates,
        )
        pnu = outcome.pop("pnu", "")
        outcome["contract_date"] = str(row["contract_date"])[:10]
        if outcome["status"] == "unique_unverified" and pnu:
            outcome.update(
                reference_year_price(
                    plates[pnu],
                    int(outcome["contract_date"][:4]),
                    outcome["contract_date"],
                )
            )
        outcome["area_sqm"] = float(row["area_sqm"])
        price = row["unit_price_per_sqm"]
        outcome["unit_price_per_sqm"] = None if price is None else float(price)
        results.append(outcome)
        if len(results) % 20_000 == 0:
            print(f"classified={len(results)}", flush=True)
    report = summarize(results, dict(exclusions), ledger_rows, len(plates))
    report["transaction_rows"] = len(results) + sum(exclusions.values())
    comparable = report["comparable"]
    report["shares_of_comparable"] = {
        key: (None if comparable == 0 else round(value / comparable, 4))
        for key, value in report["counts"].items()
    }
    missing_price_year = sum(
        1
        for row in results
        if row["status"] == "unique_unverified" and not row["price_on_or_before_contract_year"]
    )
    report["unique_unverified_without_price_year"] = missing_price_year
    price_summary = official_price_summary(results)
    report["official_price_from_2019"] = {
        key: price_summary[key]
        for key in (
            "comparable",
            "attached",
            "attached_share",
            "same_year",
            "previous_year",
            "two_or_more_years_behind",
            "same_year_share_of_comparable",
            "previous_year_share_of_comparable",
        )
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    PRICE_REPORT.write_text(json.dumps(price_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    reference_summary = reference_price_summary(results)
    REFERENCE_REPORT.write_text(json.dumps(reference_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False), flush=True)
    print(json.dumps(reference_summary["shares"], ensure_ascii=False), flush=True)
    return report


if __name__ == "__main__":
    run()
