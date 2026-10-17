"""Combine the locked history layer with the national V1 shadow.

Read-only. Does not query the ledger or the product database.
Sidos 12, 51 and 52 come from the history-layer shadow.
Every other sido keeps the V1 national shadow.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NATIONAL = ROOT / "docs" / "lab" / "land_link_v1_national_shadow_20261016.json"
HISTORY = ROOT / "docs" / "lab" / "land_link_code_history_shadow_20261016.json"
REPORT = ROOT / "docs" / "lab" / "land_link_product_shadow_20261016.json"
REPLACED = ("12", "51", "52")
LINK_KEYS = (
    "exact",
    "label_normalized",
    "true_conflict",
    "no_precontract_observation",
    "post_contract_only",
    "clean_precontract_traits_differ",
    "label_normalized_traits_differ",
    "multiple_candidates",
    "other_unmatched",
    "comparable",
)
PRICE_KEYS = ("same_year", "previous_year", "price_conflict", "price_missing", "priced_transactions")


def _sum(blocks: list[dict], keys: tuple[str, ...]) -> dict[str, int]:
    totals = {key: 0 for key in keys}
    for block in blocks:
        for key in keys:
            totals[key] += int(block.get(key, 0))
    return totals


def _rate(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


def main() -> None:
    national = json.loads(NATIONAL.read_text(encoding="utf-8"))
    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    by_sido = dict(national["by_sido"])
    by_sido_year = dict(national["by_sido_year"])
    price_by_sido = dict(national["price_by_sido"])
    price_by_sido_year = dict(national["price_by_sido_year"])
    for code in REPLACED:
        by_sido[code] = history["by_sido"][code]
        by_sido_year[code] = history["by_sido_year"][code]
        price_by_sido[code] = history["price_by_sido"][code]
        price_by_sido_year[code] = history["price_by_sido_year"][code]
    link = _sum(list(by_sido.values()), LINK_KEYS)
    price = _sum(list(price_by_sido.values()), PRICE_KEYS)
    comparable = link["comparable"]
    priced = price["priced_transactions"]
    identified = link["exact"] + link["label_normalized"]
    report = {
        "mode": "product_connection_shadow",
        "rules": ["LAND_CODE_HISTORY_LAYER_V1", "LAND_LINK_RULE_V1"],
        "contract_date_from": "2019-01-01",
        "product_database_changed": False,
        "national_ledger_rewritten": False,
        "regional_exceptions_added": False,
        "replaced_sido": list(REPLACED),
        "sources": {
            "v1_national": NATIONAL.name,
            "history_layer": HISTORY.name,
        },
        "national": {
            **link,
            "identified": identified,
            "exact_rate": _rate(link["exact"], comparable),
            "label_normalized_rate": _rate(link["label_normalized"], comparable),
            "identified_rate": _rate(identified, comparable),
            "true_conflict_rate": _rate(link["true_conflict"], comparable),
            "no_precontract_observation_rate": _rate(link["no_precontract_observation"], comparable),
            "post_contract_only_rate": _rate(link["post_contract_only"], comparable),
        },
        "price_national": {
            **price,
            "same_year_rate_of_priced": _rate(price["same_year"], priced),
            "previous_year_rate_of_priced": _rate(price["previous_year"], priced),
            "price_conflict_rate_of_priced": _rate(price["price_conflict"], priced),
            "price_missing_rate_of_priced": _rate(price["price_missing"], priced),
        },
        "by_sido": {code: by_sido[code] for code in sorted(by_sido)},
        "by_sido_year": {code: by_sido_year[code] for code in sorted(by_sido_year)},
        "price_by_sido": {code: price_by_sido[code] for code in sorted(price_by_sido)},
        "price_by_sido_year": {code: price_by_sido_year[code] for code in sorted(price_by_sido_year)},
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"national": report["national"], "price_national": report["price_national"]}, ensure_ascii=False, indent=2))
    print(REPORT)


if __name__ == "__main__":
    main()
