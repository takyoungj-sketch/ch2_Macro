"""Close the Cheongju land link rule after checking code-to-label pairs.

A conflict key whose codes, area, and official price agree is one observation.
Labels are not part of the key. An empty label is not a second meaning.
Display names come from the code dictionary. Raw labels stay on the source row.
This probe does not rewrite the national ledger and does not pick a ZIP.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.cheongju_land_conflict_cause_probe import conflict_signature  # noqa: E402
from parcel_master.cheongju_land_gap_probe import _split_candidates  # noqa: E402
from parcel_master.cheongju_land_link_probe import (  # noqa: E402
    LEDGER,
    PRICE_FROM,
    Plate,
    _matches,
    compact_jimok,
    compact_zones,
    exclusion_reason,
    latest_consistent_plate,
    load_cheongju_plates,
)
from parcel_master.trait_link_helpers import area_key  # noqa: E402

REPORT = ROOT / "docs" / "lab" / "cheongju_land_label_rule_2019_20261016.json"
PRICE_REPORT = ROOT / "docs" / "lab" / "cheongju_land_price_final_2019_20261016.json"
DICTIONARY = ROOT / "docs" / "lab" / "cheongju_trait_code_dictionary_20261004.json"
FOCUS_END = "2023-12-31"
SHAPE_CODE = 16
SHAPE_LABEL = 17
LABEL_OF = {
    "use": (12, 13),
    "height": (14, 15),
    "shape": (16, 17),
    "road": (18, 19),
}


def _norm(text: str) -> str:
    return text.replace(" ", "")


def load_dictionary() -> dict[str, dict[str, str]]:
    raw = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    return {
        field: {_norm(code): _norm(label) for code, label in names.items()}
        for field, names in raw.items()
    }


def dictionary_name(code: str, official: dict[str, str]) -> str | None:
    text = _norm(code)
    if text in official:
        return official[text]
    if text.isdigit() and str(int(text)) in official:
        return official[str(int(text))]
    return None


def label_pair_status(code: str, labels: set[str], official: dict[str, str]) -> str:
    """Classify one code against the names attached to it. Does not choose a ZIP."""
    present = {_norm(label) for label in labels if _norm(label)}
    name = dictionary_name(code, official)
    if not present:
        return "blank"
    if name is None:
        return "code_not_in_dictionary"
    if present == {name}:
        return "official_name"
    if name in present:
        return "official_plus_alias"
    return "name_not_in_dictionary"


def normalized_plate(variants: list[tuple]) -> Plate | None:
    """One plate when codes, area, and price agree. None when those values differ."""
    signature = conflict_signature(variants)
    if signature["category"] != "label_only":
        return None
    row = variants[0]
    jimok_names = {_norm(str(item[6])) for item in variants if _norm(str(item[6]))}
    zone1_names = {_norm(str(item[9])) for item in variants if _norm(str(item[9]))}
    zone2_names = {_norm(str(item[11])) for item in variants if _norm(str(item[11]))}
    if len(jimok_names) > 1 or len(zone1_names) > 1 or len(zone2_names) > 1:
        return None
    area = area_key(row[7])
    if area is None:
        return None
    jimok = compact_jimok(next(iter(jimok_names)) if jimok_names else "")
    zones = compact_zones(
        next(iter(zone1_names)) if zone1_names else "",
        next(iter(zone2_names)) if zone2_names else "",
    )
    return (
        str(row[1])[:10],
        int(row[2]),
        int(row[3]),
        jimok,
        area,
        zones,
        str(row[20]),
    )


def classify_link_v1(
    *,
    day: str,
    jimok: str,
    area: str,
    zone: str,
    prior: list[str],
    later: list[str],
    plates: dict[str, list[Plate]],
    normalized: dict[str, list[Plate]],
    conflict_asofs: dict[str, list[str]],
    substantive_asofs: dict[str, set[str]],
) -> tuple[str, str]:
    """Return the V1 link status and the parcel used for price, if any."""
    if len(prior) == 1:
        return "exact", prior[0]
    if len(prior) > 1:
        return "multiple_candidates", ""
    if len(later) == 1:
        pnu = later[0]
        clean_pre = any(plate[0] <= day for plate in plates[pnu])
        combined = sorted(plates[pnu] + normalized.get(pnu, []))
        group = latest_consistent_plate(combined, day)
        pre = [asof for asof in conflict_asofs.get(pnu, ()) if asof <= day]
        matched = bool(group and _matches(group, jimok, area, zone))
        if clean_pre:
            return "clean_precontract_traits_differ", ""
        if matched:
            return "label_normalized", pnu
        if any(asof <= day for asof in substantive_asofs.get(pnu, ())):
            return "true_conflict", ""
        if pre:
            return "label_normalized_traits_differ", ""
        if conflict_asofs.get(pnu):
            return "post_contract_only", ""
        return "no_precontract_observation", ""
    return "other_unmatched", ""


def attach_price_detail(
    rows: list[Plate], contract_year: int
) -> tuple[str, Decimal | None, int | None]:
    """Same reference year, then the previous year. Equal numbers are one price.

    The amount is returned only when one price is chosen. A conflict does not
    fall through to another year.
    """
    for year, label in ((contract_year, "same_year"), (contract_year - 1, "previous_year")):
        amounts: set[Decimal] = set()
        broken = False
        for row in rows:
            if row[1] != year:
                continue
            text = str(row[6] or "").strip()
            if not text:
                continue
            try:
                amounts.add(Decimal(text))
            except InvalidOperation:
                broken = True
        if broken or len(amounts) > 1:
            return "price_conflict", None, None
        if len(amounts) == 1:
            return label, next(iter(amounts)), year
    return "price_missing", None, None


def attach_price(rows: list[Plate], contract_year: int) -> str:
    """Status half of attach_price_detail. Callers that only count keep this."""
    return attach_price_detail(rows, contract_year)[0]


def audit_shape(variants: list[tuple], official: dict[str, str]) -> dict | None:
    labels = {str(item[SHAPE_LABEL]) for item in variants}
    present = {_norm(label) for label in labels if _norm(label)}
    if len(present) < 2:
        return None
    codes = {str(item[SHAPE_CODE]) for item in variants}
    by_label: dict[str, set[str]] = defaultdict(set)
    for item in variants:
        by_label[_norm(str(item[SHAPE_LABEL]))].add(str(item[4]))
    code = next(iter(codes)) if len(codes) == 1 else ""
    return {
        "codes": len(codes),
        "code": code,
        "status": label_pair_status(code, labels, official) if len(codes) == 1 else "multiple_codes",
        "dictionary_name": dictionary_name(code, official) or "",
        "labels": sorted(present),
        "files_by_label": {label: sorted(files) for label, files in by_label.items()},
    }


def run() -> dict:
    from sqlalchemy import text

    from db_utils import get_engine

    dictionary = load_dictionary()
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
    plates, index, _rows = load_cheongju_plates(LEDGER)
    prepared: list[dict] = []
    targets: set[str] = set()
    for row in pending:
        day = str(row["contract_date"])[:10]
        jimok = str(row["land_category"] or "").strip()
        area = area_key(row["area_sqm"]) or ""
        zone = str(row["zone_type"])
        prior, later = _split_candidates(
            str(row["beopjungri_code"]), jimok, area, zone, row["lot_display"], day, index, plates
        )
        if len(prior) == 1:
            targets.add(prior[0])
        elif len(later) == 1:
            targets.add(later[0])
        prepared.append(
            {
                "day": day,
                "year": day[:4],
                "bjd": str(row["beopjungri_code"]),
                "jimok": jimok,
                "area": area,
                "zone": zone,
                "lot": row["lot_display"],
                "prior": len(prior),
                "prior_pnu": prior[0] if len(prior) == 1 else "",
                "later": later,
            }
        )
    print(f"comparable={len(prepared)} recovery_pnu={len(targets)}", flush=True)
    grouped: dict[tuple, list[tuple]] = defaultdict(list)
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
        while True:
            chunk = cursor.fetchmany(50_000)
            if not chunk:
                break
            for item in chunk:
                seen += 1
                if item[0] in targets:
                    grouped[(item[0], str(item[1])[:10], str(item[2]), str(item[3]))].append(tuple(item))
            if seen % 1_000_000 == 0:
                print(f"conflict rows={seen}", flush=True)
    finally:
        db.close()
    print(f"conflict rows={seen} keys={len(grouped)}", flush=True)
    normalized: dict[str, list[Plate]] = defaultdict(list)
    substantive_asofs: dict[str, set[str]] = defaultdict(set)
    field_status: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    shape_alias: dict[tuple, dict] = {}
    substantive = 0
    label_keys = 0
    for (pnu, asof, _year, _month), variants in grouped.items():
        signature = conflict_signature(variants)
        if signature["category"] != "label_only":
            substantive += 1
            substantive_asofs[pnu].add(asof)
            continue
        label_keys += 1
        plate = normalized_plate(variants)
        if plate is not None:
            normalized[pnu].append(plate)
        for field, (code_index, label_index) in LABEL_OF.items():
            status = label_pair_status(
                str(variants[0][code_index]),
                {str(item[label_index]) for item in variants},
                dictionary[field],
            )
            field_status[field][status] += 1
        shape = audit_shape(variants, dictionary["shape"])
        if shape is None:
            continue
        key = (shape["code"], tuple(shape["labels"]), shape["status"])
        bucket = shape_alias.setdefault(
            key,
            {
                "code": shape["code"],
                "dictionary_name": shape["dictionary_name"],
                "labels": shape["labels"],
                "status": shape["status"],
                "keys": 0,
                "files_by_label": {label: set() for label in shape["labels"]},
            },
        )
        bucket["keys"] += 1
        for label, files in shape["files_by_label"].items():
            if label in bucket["files_by_label"]:
                bucket["files_by_label"][label].update(files)
    for rows in normalized.values():
        rows.sort()
    conflict_asofs: dict[str, list[str]] = defaultdict(list)
    for pnu, asof, _year, _month in grouped:
        conflict_asofs[pnu].append(asof)
    counts: dict[str, int] = defaultdict(int)
    by_year: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    price_counts: dict[str, int] = defaultdict(int)
    price_by_year: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    price_by_kind: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in prepared:
        kind, price_pnu = classify_link_v1(
            day=row["day"],
            jimok=row["jimok"],
            area=row["area"],
            zone=row["zone"],
            prior=[row["prior_pnu"]] if row["prior"] == 1 else [""] * row["prior"],
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
            price_counts[price_kind] += 1
            price_by_year[row["year"]][price_kind] += 1
            price_by_year[row["year"]]["priced_transactions"] += 1
            price_by_kind[kind][price_kind] += 1
    shape_rows = []
    for bucket in shape_alias.values():
        shape_rows.append(
            {
                "code": bucket["code"],
                "dictionary_name": bucket["dictionary_name"],
                "labels": bucket["labels"],
                "status": bucket["status"],
                "keys": bucket["keys"],
                "files_by_label": {label: sorted(files) for label, files in bucket["files_by_label"].items()},
            }
        )
    shape_rows.sort(key=lambda item: -item["keys"])
    report = {
        "place": "청주시 상당·서원·흥덕·청원",
        "contract_years": "2019-2023",
        "cheongju_land_link_rule": "closed",
        "rule": {
            "match_on": "코드, 면적, 공시지가",
            "labels": "키와 충돌 판정에 쓰지 않음. 원문 명칭과 출처 ZIP은 보존",
            "display_name": "코드사전. 나중 ZIP 문자열로 원장을 덮지 않음",
            "real_conflict": "코드 또는 면적·공시지가가 다를 때만",
            "alias": "같은 코드에 빈칸이 아닌 명칭이 둘이면 label_alias. 표시명은 사전",
            "unobserved": "계약 전 관측 없음과 계약 후에만 있는 행은 메우지 않음",
        },
        "comparable": len(prepared),
        "counts": dict(counts),
        "by_contract_year": {year: dict(by_year[year]) for year in sorted(by_year)},
        "conflict_keys_on_recovery_parcels": {"label_only": label_keys, "substantive": substantive},
        "code_name_status": {field: dict(statuses) for field, statuses in sorted(field_status.items())},
        "shape_both_nonempty": shape_rows,
        "product_database_changed": False,
        "national_ledger_rewritten": False,
        "official_price": {
            "rule_version": "LAND_LINK_RULE_V1",
            "population": "exact + label_normalized",
            "population_count": price_counts["same_year"] + price_counts["previous_year"] + price_counts["price_missing"] + price_counts["price_conflict"],
            "same_year": price_counts["same_year"],
            "previous_year_fallback": price_counts["previous_year"],
            "price_missing": price_counts["price_missing"],
            "price_conflict": price_counts["price_conflict"],
            "by_contract_year": {year: dict(price_by_year[year]) for year in sorted(price_by_year)},
            "by_link_kind": {kind: dict(price_by_kind[kind]) for kind in sorted(price_by_kind)},
        },
    }
    PRICE_REPORT.write_text(json.dumps(report["official_price"], ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False), flush=True)
    return report


if __name__ == "__main__":
    run()
