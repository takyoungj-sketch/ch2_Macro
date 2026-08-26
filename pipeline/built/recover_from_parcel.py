# -*- coding: utf-8 -*-
"""복합 매칭 — parcel_master SQL 읽기. 원본 파일 스캔 없음.

A1/A2 · time_fallback 규칙은 recover_address.match_all 과 같다.
쓰기는 built_transaction_enrichment (ON CONFLICT DO NOTHING).
게이트 통과 전에 원본 경로를 끄지 않는다.

  python -m built.recover_from_parcel --sido 43
  python -m built.recover_from_parcel --sido 43 --apply-enrichment
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from built.db_utils import get_built_engine  # noqa: E402
from built.enrichment_rows import apply_enrichment_rows, to_enrichment_records  # noqa: E402
from built.recover_address import (  # noqa: E402
    TX_SQL,
    lot_str,
    match_all,
    order_zone_labels,
    to_f,
    to_i,
)
from built.snapshot_policy import apply_snapshot_policy, policy_coverage  # noqa: E402
from parcel_master.db_utils import get_parcel_engine  # noqa: E402
from parcel_master.paths import SNAPSHOTS as PM_SNAPS  # noqa: E402
from parcel_master.zone import ZONE_COARSE_LABELS  # noqa: E402

PRIMARY = "2026-07"
SNAPSHOTS = list(PM_SNAPS)
CACHE = Path(__file__).parent / "_cache"

BLD_SQL = """
SELECT b.pnu, b.beopjungri_code,
       SUBSTRING(b.pnu FROM 12 FOR 4) AS bun,
       SUBSTRING(b.pnu FROM 16 FOR 4) AS ji,
       b.gross_area, b.title_land_area, b.structure_name,
       b.floors_above, b.approve_date,
       p.land_area AS parcel_land, p.land_area_source
FROM building b
LEFT JOIN parcel p ON p.pnu = b.pnu
WHERE b.sido_code = :sido AND b.snapshot = :snap
"""

ZONE_SQL = """
SELECT pnu, zone_label, is_coarse, COALESCE(n_hits, 1) AS n_hits
FROM parcel_zone
WHERE pnu LIKE :pfx
"""

EXISTING_SQL = """
SELECT e.transaction_hash, e.match_tier
FROM built_transaction_enrichment e
JOIN built_transactions t ON t.transaction_hash = e.transaction_hash
WHERE t.sigungu_code LIKE :sido_like
  AND t.contract_year >= :min_year
  AND t.is_valid AND t.gross_area > 0
  AND t.is_partial_ownership IS NOT TRUE
"""

# D-050 고정 분모: 지분거래 포함 2019+ (665,030). TX_SQL 매칭 우주와 다름.
UNIVERSE_COUNT_SQL = """
SELECT COUNT(*) FROM built_transactions
WHERE is_valid AND gross_area > 0 AND contract_year >= :min_year
"""


def load_parcels_from_db(sido: str, snapshot: str) -> tuple[dict, dict, int]:
    """recover_address.build_parcels 와 같은 키. 총괄표제부는 parcel overlay 로 대체."""
    eng = get_parcel_engine()
    with eng.connect() as conn:
        rows = conn.execute(text(BLD_SQL), {"sido": sido, "snap": snapshot}).mappings().all()
    parcels: dict[tuple, dict] = {}
    for r in rows:
        bun = to_i(r["bun"])
        if bun is None:
            continue
        bjd = str(r["beopjungri_code"] or "").strip()
        if len(bjd) != 10:
            continue
        key = (bjd, bun, to_i(r["ji"]) or 0)
        p = parcels.setdefault(
            key, {"land": math.nan, "land_src": None, "b": [], "pnu": str(r["pnu"] or "")}
        )
        if not p.get("pnu") and r["pnu"]:
            p["pnu"] = str(r["pnu"])
        p["b"].append(
            {
                "gross": to_f(r["gross_area"]),
                "struct": str(r["structure_name"] or "").strip(),
                "floors": to_i(r["floors_above"]),
                "approve": to_i(str(r["approve_date"] or "")[:4]),
                "use": "",
                "road": "",
                "addr": "",
                "addr_road_full": "",
            }
        )
        if p["land_src"] is None:
            a = to_f(r["title_land_area"])
            if not math.isnan(a):
                p["land"], p["land_src"] = a, "title"
            else:
                a = to_f(r["parcel_land"])
                if not math.isnan(a):
                    src = str(r["land_area_source"] or "") or "land_ledger"
                    p["land"], p["land_src"] = (
                        a,
                        src if src in {"title", "summary", "land_ledger"} else "land_ledger",
                    )
    idx: dict[str, list[tuple]] = defaultdict(list)
    for key in parcels:
        idx[key[0]].append(key)
    return parcels, idx, len(rows)


def load_zone_from_db(sido: str) -> dict[str, list[str]]:
    """PNU → 빈도·라벨 정렬된 zone_labels. 키는 pnu 와 '법정동|지번'."""
    eng = get_parcel_engine()
    with eng.connect() as conn:
        rows = conn.execute(text(ZONE_SQL), {"pfx": f"{sido}%"}).all()
    by_pnu: dict[str, Counter] = defaultdict(Counter)
    coarse: dict[str, set[str]] = defaultdict(set)
    pnu_lot: dict[str, str] = {}
    for pnu, label, is_coarse, n_hits in rows:
        p = str(pnu).strip()
        lab = str(label).strip()
        if not p or not lab:
            continue
        by_pnu[p][lab] += int(n_hits or 1)
        if is_coarse:
            coarse[p].add(lab)
        if p not in pnu_lot and len(p) == 19:
            bun = int(p[11:15])
            ji = int(p[15:19])
            pnu_lot[p] = f"{p[:10]}|{lot_str(bun, ji)}"
    out: dict[str, list[str]] = {}
    for pnu, cnt in by_pnu.items():
        ordered = order_zone_labels(cnt, coarse.get(pnu, set()) | ZONE_COARSE_LABELS)
        out[pnu] = ordered
        lot = pnu_lot.get(pnu)
        if lot:
            out[lot] = ordered
    return out


def _zone_for_row(zone: dict[str, list[str]], parcel: Any, pnu: Any) -> list[str]:
    if isinstance(pnu, str) and pnu in zone:
        return zone[pnu]
    if isinstance(parcel, str) and parcel in zone:
        return zone[parcel]
    return []


def compare_gate(
    recs: list[dict[str, Any]],
    existing: dict[str, str],
    *,
    n_tx: int,
    target_n: int | None,
    target_pct: float,
) -> dict[str, Any]:
    new = {r["transaction_hash"]: r["match_tier"] for r in recs}
    new_h, old_h = set(new), set(existing)
    only_new = sorted(new_h - old_h)
    only_old = sorted(old_h - new_h)
    both = new_h & old_h
    tier_diff = [h for h in both if new[h] != existing[h]]
    n_ok = len(recs)
    pct = round(100.0 * n_ok / n_tx, 1) if n_tx else 0.0
    a1 = sum(1 for t in new.values() if t == "A1")
    a2 = sum(1 for t in new.values() if t == "A2")
    old_a1 = sum(1 for t in existing.values() if t == "A1")
    old_a2 = sum(1 for t in existing.values() if t == "A2")
    pct_ok = abs(pct - target_pct) <= 0.3
    n_ok_gate = True if target_n is None else abs(n_ok - target_n) / max(target_n, 1) <= 0.02
    if target_n is None and existing and n_tx:
        existing_pct = round(100.0 * len(existing) / n_tx, 1)
        pct_ok = abs(pct - existing_pct) <= 0.3
    ratio_new = a1 / n_ok if n_ok else 0.0
    ratio_old = old_a1 / len(existing) if existing else 0.0
    ratio_ok = abs(ratio_new - ratio_old) <= 0.03 if existing else True
    return {
        "n_tx": n_tx,
        "n_new": n_ok,
        "n_existing": len(existing),
        "confirmed_pct": pct,
        "pct_ok": pct_ok,
        "n_ok": n_ok_gate,
        "a1": a1,
        "a2": a2,
        "existing_a1": old_a1,
        "existing_a2": old_a2,
        "a1_share_ok": ratio_ok,
        "only_new": len(only_new),
        "only_old": len(only_old),
        "tier_diff": len(tier_diff),
        "only_new_sample": only_new[:20],
        "only_old_sample": only_old[:20],
        "passed": pct_ok and n_ok_gate and ratio_ok,
    }


def run(
    sido: str,
    *,
    min_year: int = 2019,
    apply_enrichment: bool = False,
    target_n: int | None = None,
    target_pct: float = 75.0,
) -> dict:
    built = get_built_engine()
    with built.connect() as conn:
        tx = pd.read_sql(
            text(TX_SQL),
            conn,
            params={"sido_like": f"{sido}%", "min_year": min_year},
        )
        existing_rows = conn.execute(
            text(EXISTING_SQL), {"sido_like": f"{sido}%", "min_year": min_year}
        ).all()
    existing = {str(h): str(t) for h, t in existing_rows if h and t}
    print(f"[원장] {len(tx):,}건 (contract_year>={min_year}) existing={len(existing):,}", flush=True)

    results: dict[str, pd.DataFrame] = {}
    parcels_by_snap: dict[str, dict] = {}
    for snap in SNAPSHOTS:
        parcels, idx, n_b = load_parcels_from_db(sido, snap)
        parcels_by_snap[snap] = parcels
        print(f"[{snap}] building={n_b:,} parcels={len(parcels):,}", flush=True)
        results[snap] = match_all(tx, parcels, idx)

    res = apply_snapshot_policy(results, policy="time_fallback", primary=PRIMARY)
    zone = load_zone_from_db(sido)

    def _pnu_of(row) -> str | None:
        snap = row.get("snapshot_used") if isinstance(row, dict) else None
        parcel = row.get("parcel") if isinstance(row, dict) else None
        if not isinstance(snap, str) or snap not in parcels_by_snap:
            snap = PRIMARY
        key = _parcel_key(parcel) if isinstance(parcel, str) else None
        if key is None:
            return None
        return parcels_by_snap.get(snap, {}).get(key, {}).get("pnu")

    labels = []
    for rec in res.to_dict(orient="records"):
        labels.append(_zone_for_row(zone, rec.get("parcel"), _pnu_of(rec)))
    recs = to_enrichment_records(
        res,
        labels,
        coverage_scope="full" if zone else "A1_only",
        matched_cycle=datetime.now().strftime("%Y%m"),
    )
    cov = policy_coverage(res)
    gate = compare_gate(recs, existing, n_tx=len(tx), target_n=target_n, target_pct=target_pct)
    print(
        f"[게이트] new={gate['n_new']:,} {gate['confirmed_pct']}% "
        f"A1={gate['a1']:,} A2={gate['a2']:,} "
        f"only_new={gate['only_new']:,} only_old={gate['only_old']:,} "
        f"tier_diff={gate['tier_diff']:,} passed={gate['passed']}",
        flush=True,
    )
    applied = None
    if apply_enrichment:
        applied = apply_enrichment_rows(built, recs)
        print(
            f"[enrichment] attempted={applied['attempted']:,} inserted={applied['inserted']:,} "
            f"already={applied['already']:,}",
            flush=True,
        )
    out = {"coverage": cov, "gate": gate, "apply": applied, "n_recs": len(recs)}
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"recover_from_parcel_{sido}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"wrote {path}", flush=True)
    return out


def _parcel_key(parcel: str) -> tuple | None:
    if "|" not in parcel:
        return None
    bjd, lot = parcel.split("|", 1)
    if "-" in lot:
        a, b = lot.split("-", 1)
        bun, ji = to_i(a), to_i(b) or 0
    else:
        bun, ji = to_i(lot), 0
    if bun is None:
        return None
    return (bjd, bun, ji)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="parcel_master 조인 매칭 (원본 파일 없음)")
    p.add_argument("--sido", default="43", help="시도 2자리. all 이면 원장 전 시도")
    p.add_argument("--min-year", type=int, default=2019)
    p.add_argument("--apply-enrichment", action="store_true")
    p.add_argument(
        "--retry-unmatched",
        action="store_true",
        help="미상만 INSERT (apply와 동일, ON CONFLICT DO NOTHING). 대장 달 수동",
    )
    p.add_argument("--target-n", type=int, default=None, help="전국 게이트 498568. 시도 스모크는 생략")
    p.add_argument("--target-pct", type=float, default=75.0)
    args = p.parse_args()
    apply = args.apply_enrichment or args.retry_unmatched
    key = args.sido.strip().lower()
    if key == "all":
        from built.recover_address import ledger_sidos

        sidos = ledger_sidos(get_built_engine())
        print(f"[전국] sidos={sidos}", flush=True)
        gates = []
        for s in sidos:
            print(f"\n======== sido {s} ========", flush=True)
            gates.append(
                run(
                    s,
                    min_year=args.min_year,
                    apply_enrichment=apply,
                    target_n=None,
                    target_pct=args.target_pct,
                )
            )
        n_tx_attempted = sum(g["gate"]["n_tx"] for g in gates)
        n_new = sum(g["gate"]["n_new"] for g in gates)
        n_old = sum(g["gate"]["n_existing"] for g in gates)
        a1 = sum(g["gate"]["a1"] for g in gates)
        a2 = sum(g["gate"]["a2"] for g in gates)
        only_new = sum(g["gate"]["only_new"] for g in gates)
        only_old = sum(g["gate"]["only_old"] for g in gates)
        tier_diff = sum(g["gate"]["tier_diff"] for g in gates)
        with get_built_engine().connect() as conn:
            n_tx = int(
                conn.execute(text(UNIVERSE_COUNT_SQL), {"min_year": args.min_year}).scalar() or 0
            )
        pct = round(100.0 * n_new / n_tx, 1) if n_tx else 0.0
        target_n = args.target_n if args.target_n is not None else 498_568
        pct_ok = abs(pct - args.target_pct) <= 0.3
        n_ok = abs(n_new - target_n) / max(target_n, 1) <= 0.02
        old_a1 = sum(g["gate"]["existing_a1"] for g in gates)
        ratio_ok = True
        if n_old and n_new:
            ratio_ok = abs((a1 / n_new) - (old_a1 / n_old)) <= 0.03
        passed = pct_ok and n_ok and ratio_ok
        summary = {
            "n_tx": n_tx,
            "n_tx_attempted": n_tx_attempted,
            "n_new": n_new,
            "n_existing": n_old,
            "confirmed_pct": pct,
            "a1": a1,
            "a2": a2,
            "only_new": only_new,
            "only_old": only_old,
            "tier_diff": tier_diff,
            "pct_ok": pct_ok,
            "n_ok": n_ok,
            "a1_share_ok": ratio_ok,
            "passed": passed,
            "by_sido": {s: g["gate"] for s, g in zip(sidos, gates)},
        }
        CACHE.mkdir(exist_ok=True)
        path = CACHE / "recover_from_parcel_all.json"
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(
            f"\n[전국 게이트] new={n_new:,}/{n_tx:,} {pct}% "
            f"(attempted={n_tx_attempted:,}) "
            f"A1={a1:,} A2={a2:,} existing={n_old:,} "
            f"only_new={only_new:,} only_old={only_old:,} tier_diff={tier_diff:,} "
            f"passed={passed}",
            flush=True,
        )
        print(f"wrote {path}", flush=True)
        return
    run(
        args.sido.strip(),
        min_year=args.min_year,
        apply_enrichment=apply,
        target_n=args.target_n,
        target_pct=args.target_pct,
    )


if __name__ == "__main__":
    main()
