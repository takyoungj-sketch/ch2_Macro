"""Why Cheongju land transactions have no pre-contract parcel.

Read-only. A blank zone on an otherwise matching plate is counted apart from
a jimok, area, or zone that differs. Individual parcel numbers are not written.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.cheongju_land_link_probe import (  # noqa: E402
    LEDGER,
    PRICE_FROM,
    Plate,
    _group_asof,
    _later_match,
    _matches,
    area_key,
    exclusion_reason,
    latest_consistent_plate,
    load_cheongju_plates,
)
from parcel_master.trait_link_helpers import lot_matches  # noqa: E402

REPORT = ROOT / "docs" / "lab" / "cheongju_land_gap_2019_20261016.json"
FOCUS_END = "2023-12-31"


def plate_difference(group: list[Plate], jimok: str, area: str, zone: str, state: str) -> str:
    row = group[0]
    jimok_ok = row[3] == jimok
    area_ok = row[4] == area
    if jimok_ok and area_ok and zone in row[5]:
        return "matches"
    if not jimok_ok and not area_ok:
        return "jimok_and_area_changed"
    if not jimok_ok:
        return "jimok_changed"
    if not area_ok:
        return "area_changed"
    if not row[5]:
        return "zone_unmapped" if state in ("unmapped", "mixed") else "zone_blank"
    return "zone_changed"


def _older_full_match(rows: list[Plate], day: str, latest_asof: str, jimok: str, area: str, zone: str) -> bool:
    seen: set[str] = set()
    for row in rows:
        asof = row[0]
        if asof > day or asof == latest_asof or asof in seen:
            continue
        seen.add(asof)
        group = _group_asof(rows, asof)
        if group and _matches(group, jimok, area, zone):
            return True
    return False


def one_parcel_reason(
    rows: list[Plate],
    day: str,
    jimok: str,
    area: str,
    zone: str,
    states: dict[str, str],
) -> tuple[str, bool]:
    group = latest_consistent_plate(rows, day)
    if group is None:
        if any(row[0] <= day for row in rows):
            return "inconsistent_plate", _older_full_match(rows, day, "", jimok, area, zone)
        if _later_match(rows, day, jimok, area, zone):
            return "first_seen_after_contract", False
        return "only_after_contract", False
    reason = plate_difference(group, jimok, area, zone, states.get(group[0][0], "blank"))
    older = _older_full_match(rows, day, group[0][0], jimok, area, zone)
    return reason, older


def _split_candidates(
    beopjungri_code: str,
    jimok: str,
    area: str,
    zone: str,
    lot_display: object,
    day: str,
    index: dict[tuple[str, str, str], set[str]],
    plates: dict[str, list[Plate]],
) -> tuple[list[str], list[str]]:
    prior: list[str] = []
    later: list[str] = []
    for pnu in index.get((beopjungri_code, jimok, area), ()):
        if not lot_matches(lot_display, pnu, str(int(pnu[11:15]))):
            continue
        rows = plates[pnu]
        group = latest_consistent_plate(rows, day)
        if group and _matches(group, jimok, area, zone):
            prior.append(pnu)
            continue
        if _later_match(rows, day, jimok, area, zone):
            later.append(pnu)
    return prior, later


def explain_gap(
    *,
    beopjungri_code: str,
    land_category: str,
    zone_type: str,
    area_sqm: object,
    lot_display: object,
    contract_date: str,
    index: dict[tuple[str, str, str], set[str]],
    plates: dict[str, list[Plate]],
    by_bjd: dict[str, list[str]],
    zone_by_pnu: dict[str, dict[str, str]],
) -> tuple[str, str, bool]:
    """Return link status, reason, and whether an earlier pre-contract plate matched."""
    jimok = str(land_category or "").strip()
    area = area_key(area_sqm) or ""
    zone = str(zone_type)
    day = str(contract_date)[:10]
    prior, later = _split_candidates(beopjungri_code, jimok, area, zone, lot_display, day, index, plates)
    if len(prior) == 1:
        return "unique_unverified", "", False
    if len(prior) > 1:
        return "multiple_candidates", "", False
    if later:
        reasons = [
            one_parcel_reason(plates[pnu], day, jimok, area, zone, zone_by_pnu.get(pnu, {}))
            for pnu in later
        ]
        if len(reasons) == 1:
            return "no_prior_plate", reasons[0][0], reasons[0][1]
        names = {reason for reason, _older in reasons}
        if names == {"zone_blank"}:
            return "no_prior_plate", "multiple_later_zone_blank", False
        return "no_prior_plate", "multiple_later_mixed", False
    lot_pnus = [
        pnu
        for pnu in by_bjd.get(beopjungri_code, ())
        if lot_matches(lot_display, pnu, str(int(pnu[11:15])))
    ]
    if not lot_pnus:
        return "no_candidate", "lot_unmatched", False
    if len(lot_pnus) > 1:
        return "no_candidate", "lot_ambiguous", False
    pnu = lot_pnus[0]
    reason, older = one_parcel_reason(plates[pnu], day, jimok, area, zone, zone_by_pnu.get(pnu, {}))
    return "no_candidate", reason, older


def _empty_bucket() -> dict[str, dict[str, int]]:
    return defaultdict(lambda: defaultdict(int))


def summarize_gaps(rows: list[dict]) -> dict:
    def window(start: str, end: str) -> dict:
        chosen = [row for row in rows if start <= row["contract_date"] <= end]
        buckets = _empty_bucket()
        comparable = 0
        for row in chosen:
            comparable += 1
            if row["status"] not in ("no_prior_plate", "no_candidate"):
                buckets["linked"][row["status"]] += 1
                continue
            buckets[row["status"]][row["reason"]] += 1
            if row["earlier_plate_matched"]:
                buckets[row["status"]][row["reason"] + "|earlier_plate_matched"] += 1
        return {
            "contract_date_from": start,
            "contract_date_to": end,
            "comparable": comparable,
            "no_prior_plate": sum(
                count for key, count in buckets["no_prior_plate"].items() if "|" not in key
            ),
            "no_candidate": sum(
                count for key, count in buckets["no_candidate"].items() if "|" not in key
            ),
            "reasons": {name: dict(counts) for name, counts in buckets.items()},
        }

    focus = window(PRICE_FROM, FOCUS_END)
    return {
        "place": "청주시 상당·서원·흥덕·청원",
        "focus": "2019-2023 계약 중 계약 전 판에서 필지를 못 찾은 거래",
        "rule_note": "용도지역이 비어 있고 지목·면적·지번이 맞는 단일 필지만 규칙 완화 후보",
        "years_2019_2023": focus,
        "years_2024_2026": window("2024-01-01", "2026-12-31"),
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
        """
    )
    pending: list[dict] = []
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        fetched = connection.execute(sql, {"start": PRICE_FROM}).mappings().all()
    for record in fetched:
        row = dict(record)
        if exclusion_reason(row) or len(str(row["beopjungri_code"])) != 10:
            continue
        pending.append(row)
    print(f"transactions comparable={len(pending)}", flush=True)
    zone_state: dict[tuple[str, str], str] = {}
    unmapped: dict[tuple[str, str], int] = defaultdict(int)
    plates, index, ledger_rows = load_cheongju_plates(LEDGER, zone_state, unmapped)
    by_bjd: dict[str, list[str]] = defaultdict(list)
    zone_by_pnu: dict[str, dict[str, str]] = defaultdict(dict)
    for pnu in plates:
        by_bjd[pnu[:10]].append(pnu)
    for (pnu, asof), state in zone_state.items():
        zone_by_pnu[pnu][asof] = state
    explained: list[dict] = []
    for row in pending:
        status, reason, earlier = explain_gap(
            beopjungri_code=str(row["beopjungri_code"]),
            land_category=str(row["land_category"]),
            zone_type=str(row["zone_type"]),
            area_sqm=row["area_sqm"],
            lot_display=row["lot_display"],
            contract_date=str(row["contract_date"]),
            index=index,
            plates=plates,
            by_bjd=by_bjd,
            zone_by_pnu=zone_by_pnu,
        )
        explained.append(
            {
                "contract_date": str(row["contract_date"])[:10],
                "status": status,
                "reason": reason,
                "earlier_plate_matched": earlier,
            }
        )
    report = summarize_gaps(explained)
    report["ledger_rows_read"] = ledger_rows
    report["unmapped_zone_labels"] = [
        {"zone1": left, "zone2": right, "rows": count}
        for (left, right), count in sorted(unmapped.items(), key=lambda item: -item[1])[:15]
    ]
    focus = report["years_2019_2023"]["reasons"].get("no_prior_plate", {})
    report["zone_blank_single_later"] = focus.get("zone_blank", 0)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"zone_blank_single_later": report["zone_blank_single_later"]}, ensure_ascii=False), flush=True)
    return report


if __name__ == "__main__":
    run()
