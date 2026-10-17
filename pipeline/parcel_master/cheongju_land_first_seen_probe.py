"""Where the pre-contract row went for parcels first stored after the contract.

Read-only. The 2019-2023 Cheongju cases whose only trait match is a later plate
are checked against the clean table, the conflict table, and the load-time
parcel filter. Parcel numbers are not written out.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.attribute_ledger import parcel_hold  # noqa: E402
from parcel_master.cheongju_land_gap_probe import _split_candidates  # noqa: E402
from parcel_master.cheongju_land_link_probe import (  # noqa: E402
    LEDGER,
    PRICE_FROM,
    exclusion_reason,
    load_cheongju_plates,
)
from parcel_master.trait_link_helpers import area_key  # noqa: E402

REPORT = ROOT / "docs" / "lab" / "cheongju_land_first_seen_2019_20261016.json"
FOCUS_END = "2023-12-31"


def classify_presence(pnu: str, day: str, clean_asofs: list[str], conflict_asofs: list[str]) -> str:
    held = parcel_hold(pnu)
    if held:
        return held
    if any(asof <= day for asof in clean_asofs):
        return "clean_precontract"
    if any(asof <= day for asof in conflict_asofs):
        return "conflict_precontract"
    if conflict_asofs:
        return "conflict_only_after_contract"
    return "absent_before_contract"


def _conflict_asofs(db_path: Path, targets: set[str]) -> dict[str, list[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    db = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        cursor = db.execute(
            """
            SELECT pnu, asof FROM observation_conflict
            WHERE pnu >= '4311100000000000000' AND pnu < '4311500000000000000'
            """
        )
        seen = 0
        while True:
            chunk = cursor.fetchmany(100_000)
            if not chunk:
                break
            for pnu, asof in chunk:
                seen += 1
                if pnu in targets:
                    found[pnu].add(str(asof)[:10])
            if seen % 500_000 == 0:
                print(f"conflict rows={seen} hit_pnu={len(found)}", flush=True)
    finally:
        db.close()
    print(f"conflict rows={seen} hit_pnu={len(found)}", flush=True)
    return {pnu: sorted(days) for pnu, days in found.items()}


def summarize(rows: list[dict]) -> dict:
    counts: dict[str, int] = defaultdict(int)
    by_year: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    pnus: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        kind = row["presence"]
        counts[kind] += 1
        by_year[row["contract_year"]][kind] += 1
        by_year[row["contract_year"]]["transactions"] += 1
        pnus[kind].add(row["pnu"])
    total = len(rows)
    absent = counts["absent_before_contract"] + counts["conflict_only_after_contract"]
    return {
        "place": "청주시 상당·서원·흥덕·청원",
        "scope": "2019-2023 계약. 필지가 하나이고 그 필지의 첫 정상 관측이 계약일 이후",
        "transactions": total,
        "distinct_pnu": len(set().union(*pnus.values()) if pnus else set()),
        "clean_precontract": counts["clean_precontract"],
        "conflict_precontract": counts["conflict_precontract"],
        "conflict_only_after_contract": counts["conflict_only_after_contract"],
        "absent_before_contract": counts["absent_before_contract"],
        "held_invalid_land_type": counts["invalid_land_type"],
        "held_invalid_pnu": counts["invalid_pnu"],
        "held_zero_main_lot": counts["noncanonical_zero_main_lot"],
        "no_precontract_source_row": absent,
        "shares": {
            "conflict_precontract": round(counts["conflict_precontract"] / total, 4) if total else None,
            "absent_or_conflict_only_later": round(absent / total, 4) if total else None,
        },
        "distinct_pnu_by_presence": {kind: len(values) for kind, values in sorted(pnus.items())},
        "by_contract_year": {year: dict(by_year[year]) for year in sorted(by_year)},
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
          AND contract_date >= :start
          AND contract_date <= :end
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
    print(f"transactions comparable={len(pending)}", flush=True)
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
        clean = plates[pnu]
        if any(plate[0] <= day for plate in clean):
            continue
        if not any(plate[0] > day for plate in clean):
            continue
        cases.append((pnu, day))
    print(f"first_seen_transactions={len(cases)} distinct_pnu={len({pnu for pnu, _day in cases})}", flush=True)
    conflicts = _conflict_asofs(LEDGER, {pnu for pnu, _day in cases})
    classified = [
        {
            "pnu": pnu,
            "contract_year": day[:4],
            "presence": classify_presence(pnu, day, [plate[0] for plate in plates[pnu]], conflicts.get(pnu, [])),
        }
        for pnu, day in cases
    ]
    report = summarize(classified)
    report["expected_transactions_from_gap"] = 17730
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("transactions", "conflict_precontract", "absent_before_contract", "conflict_only_after_contract")}, ensure_ascii=False), flush=True)
    return report


if __name__ == "__main__":
    run()
