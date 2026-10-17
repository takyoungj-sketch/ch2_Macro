"""Shadow V1 after a 1:1 legal-dong normalization. Read-only.

Covers only the three reissue sidos. Does not change V1, the product
database, or the national ledger. Pairs that are not 1:1 are held.
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
from parcel_master.cheongju_land_gap_probe import _split_candidates
from parcel_master.cheongju_land_link_probe import exclusion_reason
from parcel_master.land_code_history_layer import (
    HONAM_EFFECTIVE,
    PREFIX_GENERATIONS,
    add_pair,
    prefix_previous,
    resolve_beopjungri,
)
from parcel_master.national_land_link_shadow import (
    PRICE_FROM,
    SIDO_NAME,
    _finish,
    _load_conflict,
    _load_plates,
    _summary,
    _write,
)
from parcel_master.trait_link_helpers import area_key

PROGRESS = Path(r"C:\CH2\parcel_master\land_link_code_history_shadow_progress.json")
REPORT = ROOT / "docs" / "lab" / "land_link_code_history_shadow_20261016.json"
TARGET_SIDO = ("12", "51", "52")


def load_pairs(connection) -> dict[str, tuple[str, str]]:
    pairs: dict[str, tuple[str, str]] = {}
    owners: dict[str, str] = {}
    for current_sido, old_sido, effective in PREFIX_GENERATIONS:
        rows = connection.execute(
            text(
                """
                SELECT beopjungri_code
                FROM region_codes
                WHERE sido_code = :sido
                """
            ),
            {"sido": current_sido},
        ).all()
        for (code,) in rows:
            current = str(code).strip()
            add_pair(pairs, owners, current, prefix_previous(current, old_sido), effective)
    rows = connection.execute(
        text(
            """
            WITH old AS (
                SELECT sido_code, sigungu_name, eupmyeondong_name, beopjungri_name, beopjungri_code
                FROM region_codes
                WHERE sido_code IN ('29', '46')
            ),
            neu AS (
                SELECT sigungu_name, eupmyeondong_name, beopjungri_name, beopjungri_code
                FROM region_codes
                WHERE sido_code = '12'
            )
            SELECT n.beopjungri_code, o.beopjungri_code
            FROM neu n
            JOIN old o
              ON o.sigungu_name = n.sigungu_name
             AND o.eupmyeondong_name = n.eupmyeondong_name
             AND o.beopjungri_name = n.beopjungri_name
            """
        )
    ).all()
    for current, previous in rows:
        add_pair(pairs, owners, str(current), str(previous), HONAM_EFFECTIVE)
    return pairs


def _merge(plates, index, extra_plates, extra_index) -> None:
    for pnu, rows in extra_plates.items():
        plates[pnu].extend(rows)
    for key, pnus in extra_index.items():
        index[key].update(pnus)


def _prepare(code: str, plates, index, pairs: dict[str, tuple[str, str]]):
    engine = get_engine()
    sql = text(
        """
        SELECT contract_date, beopjungri_code, land_category, zone_type,
               area_sqm, is_partial_ownership, is_cancelled, is_valid, lot_display
        FROM land_transactions
        WHERE sigungu_code = :code AND contract_date >= :start
        """
    )
    prepared = []
    targets: set[str] = set()
    resolve_counts: dict[str, int] = defaultdict(int)
    mislink = defaultdict(int)
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        fetched = connection.execute(sql, {"code": code, "start": PRICE_FROM}).mappings().all()
    for record in fetched:
        row = dict(record)
        if exclusion_reason(row) or len(str(row["beopjungri_code"]).strip()) != 10:
            continue
        day = str(row["contract_date"])[:10]
        original = str(row["beopjungri_code"]).strip()
        resolved, reason = resolve_beopjungri(original, day, pairs)
        resolve_counts[reason] += 1
        jimok = str(row["land_category"] or "").strip()
        area = area_key(row["area_sqm"]) or ""
        zone = str(row["zone_type"])
        prior, later = _split_candidates(resolved, jimok, area, zone, row["lot_display"], day, index, plates)
        if len(prior) == 1:
            targets.add(prior[0])
        elif len(later) == 1:
            targets.add(later[0])
        linked = prior[0] if len(prior) == 1 else (later[0] if len(later) == 1 else "")
        if reason == "reissued_1to1" and linked:
            other_prior, other_later = _split_candidates(original, jimok, area, zone, row["lot_display"], day, index, plates)
            other_tails = {pnu[10:] for pnu in other_prior + other_later}
            if not other_tails:
                mislink["other_generation_absent"] += 1
            elif linked[10:] in other_tails:
                mislink["same_parcel"] += 1
            else:
                mislink["lot_tail_mismatch"] += 1
        prepared.append(
            {
                "year": day[:4],
                "day": day,
                "jimok": jimok,
                "area": area,
                "zone": zone,
                "prior": prior,
                "later": later,
            }
        )
    return prepared, targets, dict(resolve_counts), dict(mislink)


def _prefixes_for(code: str, pairs: dict[str, tuple[str, str]]) -> list[str]:
    found = {code}
    for current, (previous, _effective) in pairs.items():
        if current[:5] == code:
            found.add(previous[:5])
    return sorted(found)


def run() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        pairs = load_pairs(connection)
        rows = connection.execute(
            text(
                """
                SELECT sigungu_code
                FROM land_transactions
                WHERE contract_date >= :start
                  AND LEFT(sigungu_code, 2) IN ('12', '51', '52')
                GROUP BY sigungu_code
                ORDER BY sigungu_code
                """
            ),
            {"start": PRICE_FROM},
        ).all()
    codes = [str(code).strip() for (code,) in rows if len(str(code).strip()) == 5]
    done = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {}
    print(f"pairs={len(pairs)} sigungu={len(codes)} done={len(done)}", flush=True)
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
        prepared, targets, resolve_counts, mislink = _prepare(code, plates, plate_index, pairs)
        grouped: dict = defaultdict(list)
        for prefix in _prefixes_for(code, pairs):
            for key, variants in _load_conflict(prefix, targets).items():
                grouped[key].extend(variants)
        done[code] = _finish(prepared, plates, grouped)
        done[code]["ledger_rows"] = ledger_rows
        done[code]["transactions"] = len(prepared)
        done[code]["resolve"] = resolve_counts
        done[code]["mislink"] = mislink
        _write(PROGRESS, done)
        print(
            f"{index}/{len(codes)} {code} tx={len(prepared)} ledger={ledger_rows} "
            f"resolve={resolve_counts} mislink={mislink} seconds={time.perf_counter() - started:.0f}",
            flush=True,
        )
        del plates, plate_index, prepared, targets, grouped
        gc.collect()
    summary = _summary(done)
    summary["layer"] = "legal_dong_history_1to1"
    summary["v1_changed"] = False
    summary["product_database_changed"] = False
    summary["region_code_history_rows_used"] = 0
    summary["candidate_pairs"] = len(pairs)
    summary["effective"] = {"51": "2023-06-11", "52": "2024-01-18", "12": HONAM_EFFECTIVE}
    summary["sido"] = list(TARGET_SIDO)
    resolve_sido: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    mislink_sido: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for code, block in done.items():
        for key, value in block.get("resolve", {}).items():
            resolve_sido[code[:2]][key] += value
        for key, value in block.get("mislink", {}).items():
            mislink_sido[code[:2]][key] += value
    summary["resolve_by_sido"] = {code: {"name": SIDO_NAME.get(code, code), **counts} for code, counts in sorted(resolve_sido.items())}
    summary["mislink_by_sido"] = {code: dict(counts) for code, counts in sorted(mislink_sido.items())}
    _write(REPORT, summary)
    print(f"wrote {REPORT}", flush=True)


if __name__ == "__main__":
    run()
