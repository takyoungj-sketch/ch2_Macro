# -*- coding: utf-8 -*-
"""Phase 2 — partial land_basic_stats_v2 rebuild for code_reissue pairs (D-028).

- Upsert 191 canonical codes into region_codes (from master)
- Deactivate 191 historical codes in region_codes
- Delete V2 mart rows for from+to codes (scoped as_of/windows)
- Rebuild via build_stats_v2 --region <canonical> (fetch expands history)
- Does NOT UPDATE land_transactions.beopjungri_code

Usage:
  cd backend
  .venv/Scripts/python.exe ../pipeline/rebuild_stats_v2_canonical_phase2.py
  .venv/Scripts/python.exe ../pipeline/rebuild_stats_v2_canonical_phase2.py --dry-run
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "backend"))

CSV_1A = ROOT / "docs" / "reports" / "REGION_CODE_PHASE1A_CLASSIFICATION.csv"
MASTER = ROOT / "data" / "region_codes" / "법정동코드 전체자료(260701).txt"
OUT_MD = ROOT / "docs" / "reports" / "REGION_CODE_PHASE2_VERIFY.md"
OUT_CSV = ROOT / "docs" / "reports" / "REGION_CODE_PHASE2_VERIFY.csv"

DEFAULT_AS_OF = date(2026, 6, 1)
DEFAULT_WINDOWS = (3, 5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--as-of", default=DEFAULT_AS_OF.isoformat())
    ap.add_argument("--windows", default="3,5")
    ap.add_argument(
        "--skip-rebuild",
        action="store_true",
        help="region_codes + delete only; skip build_stats_v2",
    )
    ap.add_argument(
        "--only-sute",
        action="store_true",
        help="Smoke: only 대소 수태리 pair",
    )
    args = ap.parse_args()
    as_of = date.fromisoformat(args.as_of)
    windows = [int(x) for x in args.windows.split(",") if x.strip()]

    from db_utils import get_engine
    from region_canonical import (
        deactivate_historical_codes,
        load_code_reissue_pairs_from_csv,
        upsert_canonical_region_codes_from_master,
    )
    from build_stats_v2 import period_bounds_for_window as pb_window

    pairs = load_code_reissue_pairs_from_csv(CSV_1A)
    if args.only_sute:
        pairs = [p for p in pairs if p[0] == "4377034026"]
    from_codes = [a for a, _ in pairs]
    to_codes = [b for _, b in pairs]
    all_codes = sorted(set(from_codes) | set(to_codes))

    print(f"pairs={len(pairs)} as_of={as_of} windows={windows} dry_run={args.dry_run}")

    # before metrics
    eng = get_engine()
    before = {}
    with eng.connect() as conn:
        before["hist_tx_sute"] = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM land_transactions WHERE beopjungri_code='4377034026'"
                )
            ).scalar()
            or 0
        )
        before["mart_hist"] = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM land_basic_stats_v2
                    WHERE beopjungri_code='4377034026' AND as_of_month=:a
                    """
                ),
                {"a": as_of},
            ).scalar()
            or 0
        )
        before["mart_can"] = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM land_basic_stats_v2
                    WHERE beopjungri_code='4377025626' AND as_of_month=:a
                    """
                ),
                {"a": as_of},
            ).scalar()
            or 0
        )
        before["allxall_hist"] = conn.execute(
            text(
                """
                SELECT count FROM land_basic_stats_v2
                WHERE beopjungri_code='4377034026' AND as_of_month=:a
                  AND window_years=3 AND col_axis='category'
                  AND zone_type='ALL' AND land_category='ALL'
                """
            ),
            {"a": as_of},
        ).scalar()

    if args.dry_run:
        print("[dry-run] would upsert region_codes, deactivate hist, delete mart, rebuild")
        print("before", before)
        return 0

    n_up = upsert_canonical_region_codes_from_master(eng, to_codes, MASTER)
    n_de = deactivate_historical_codes(eng, from_codes)
    print(f"region_codes upserted_canonical={n_up} deactivated_historical={n_de}")

    with eng.begin() as conn:
        del_res = conn.execute(
            text(
                """
                DELETE FROM land_basic_stats_v2
                WHERE beopjungri_code = ANY(:codes)
                  AND as_of_month = :a
                  AND window_years = ANY(:ws)
                """
            ),
            {"codes": all_codes, "a": as_of, "ws": windows},
        )
        deleted = int(del_res.rowcount or 0)
    print(f"deleted land_basic_stats_v2 rows={deleted}")

    # Master unchanged check
    with eng.connect() as conn:
        hist_tx = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM land_transactions WHERE beopjungri_code='4377034026'"
                )
            ).scalar()
            or 0
        )
    if hist_tx != before["hist_tx_sute"]:
        raise RuntimeError("land_transactions mutated unexpectedly")

    if args.skip_rebuild:
        print("skip rebuild")
        return 0

    # single batch rebuild via --regions-file (canonical list; fetch expands history)
    codes_file = ROOT / "docs" / "reports" / "_phase2_canonical_codes.txt"
    codes_file.write_text("\n".join(to_codes) + "\n", encoding="utf-8")
    py = sys.executable
    build = ROOT / "pipeline" / "build_stats_v2.py"
    t0 = time.perf_counter()
    cmd = [
        py,
        str(build),
        "--as-of",
        as_of.isoformat(),
        "--windows",
        ",".join(str(w) for w in windows),
        "--regions-file",
        str(codes_file),
        "--col-axis",
        "both",
    ]
    print("rebuild cmd:", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(ROOT / "pipeline"))
    elapsed = time.perf_counter() - t0
    failed: list[str] = [] if r.returncode == 0 else list(to_codes)
    print(f"rebuild exit={r.returncode} elapsed={elapsed:.1f}s")

    # verify
    from app.db import SessionLocal
    from app.region_canonical import expand_to_ledger_codes, resolve_to_canonical

    db = SessionLocal()
    try:
        sute_can = resolve_to_canonical(db, ["4377025626"])[0]
        sute_from_hist = resolve_to_canonical(db, ["4377034026"])[0]
        ledger = expand_to_ledger_codes(db, ["4377025626"])
        allxall = db.execute(
            text(
                """
                SELECT count, mean, median FROM land_basic_stats_v2
                WHERE beopjungri_code='4377025626' AND as_of_month=:a
                  AND window_years=3 AND col_axis='category'
                  AND zone_type='ALL' AND land_category='ALL'
                """
            ),
            {"a": as_of},
        ).mappings().first()
        shincheok = "4375025329"
        kept_split = db.execute(
            text(
                """
                SELECT btrim(beopjungri_code::text) AS bc
                FROM land_basic_stats_v2
                WHERE beopjungri_code = ANY(:codes)
                  AND as_of_month = :a AND window_years = 3
                  AND col_axis = 'category'
                  AND zone_type = 'ALL' AND land_category = 'ALL'
                """
            ),
            {"codes": [sute_can, shincheok], "a": as_of},
        ).fetchall()
        kept = sorted({str(r.bc) for r in kept_split})

        # bulk-like ledger count for sute+shincheok
        ledger_pair = expand_to_ledger_codes(db, [sute_can, shincheok])
        ps, pe = pb_window(as_of, 3)
        n_combined = db.execute(
            text(
                """
                SELECT COUNT(*) FROM land_transactions_resolved
                WHERE is_valid AND NOT is_cancelled
                  AND unit_price_per_sqm IS NOT NULL
                  AND contract_date BETWEEN :ps AND :pe
                  AND beopjungri_code = ANY(:codes)
                """
            ),
            {"ps": ps, "pe": pe, "codes": ledger_pair},
        ).scalar()
        n_sute_window = db.execute(
            text(
                """
                SELECT COUNT(*) FROM land_transactions_resolved
                WHERE is_valid AND NOT is_cancelled
                  AND unit_price_per_sqm IS NOT NULL
                  AND contract_date BETWEEN :ps AND :pe
                  AND beopjungri_code = ANY(:codes)
                """
            ),
            {"ps": ps, "pe": pe, "codes": ledger},
        ).scalar()

        master_unchanged = int(
            db.execute(
                text(
                    "SELECT COUNT(*) FROM land_transactions WHERE beopjungri_code='4377034026'"
                )
            ).scalar()
            or 0
        )

        lines = [
            "# Phase 2 — canonical resolve + partial V2 rebuild 검증",
            "",
            f"- **일자:** {date.today().isoformat()}",
            f"- **as_of_month:** {as_of.isoformat()}",
            f"- **windows:** {windows}",
            f"- **pairs rebuilt:** {len(pairs)} (failed={len(failed)})",
            f"- **elapsed_rebuild_s:** {elapsed:.1f}",
            "",
            "## 원칙",
            "",
            "- `land_transactions.beopjungri_code` **미변경** (historical 보존)",
            "- mart grain = `region_code_history` canonical (`to_code`)",
            "- API: GIS 코드 → `resolve_to_canonical` → mart; 원장 조회는 `expand_to_ledger_codes`",
            "- unresolved 2건: history 없음 → resolve identity / 제외",
            "",
            "## 영향 테이블",
            "",
            "| 테이블 | 변경 |",
            "|--------|------|",
            "| `region_code_history` | (Phase 1b 유지, 191) |",
            f"| `region_codes` | canonical upsert {n_up}, historical deactivate {n_de} |",
            f"| `land_basic_stats_v2` | delete {deleted} rows → rebuild {len(to_codes)} regions |",
            "| `land_transactions` | **무변경** |",
            "",
            "## 대소 수태리",
            "",
            f"| 항목 | 값 |",
            f"|------|----|",
            f"| resolve(4377025626) | `{sute_can}` |",
            f"| resolve(4377034026) | `{sute_from_hist}` |",
            f"| ledger expand(canonical) | {ledger} |",
            f"| Master tx @ historical | {master_unchanged} (before={before['hist_tx_sute']}) |",
            f"| mart ALL×ALL count @ canonical (3y category) | {dict(allxall) if allxall else None} |",
            f"| window txs via ledger expand | {n_sute_window} |",
            f"| mart rows hist@as_of before→expect stale deleted | before={before['mart_hist']} |",
            "",
            "## GIS bulk 시뮬레이션 (수태리+신척리)",
            "",
            f"- 신척리 `{shincheok}` + 수태리 canonical `{sute_can}`",
            f"- mart ALL×ALL 보유 코드: {kept}",
            f"- 합산 가능 여부: **{'OK' if sute_can in kept and shincheok in kept else 'FAIL'}**",
            f"- 원장 합산 거래수(3y window, ledger expand): {n_combined}",
            "",
            "## 실패 목록",
            "",
        ]
        if failed:
            for c in failed:
                lines.append(f"- `{c}`")
        else:
            lines.append("_(없음)_")
        lines += [
            "",
            "## 재실행",
            "",
            "```",
            "cd backend",
            ".venv/Scripts/python.exe ../pipeline/rebuild_stats_v2_canonical_phase2.py",
            "```",
            "",
        ]
        OUT_MD.parent.mkdir(parents=True, exist_ok=True)
        OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {OUT_MD}")

        # CSV summary of pairs
        import csv

        with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "historical_code",
                    "canonical_code",
                    "rebuild_ok",
                    "mart_allxall_count_3y",
                ]
            )
            for a, b in pairs:
                row = db.execute(
                    text(
                        """
                        SELECT count FROM land_basic_stats_v2
                        WHERE beopjungri_code=:c AND as_of_month=:a
                          AND window_years=3 AND col_axis='category'
                          AND zone_type='ALL' AND land_category='ALL'
                        """
                    ),
                    {"c": b, "a": as_of},
                ).scalar()
                w.writerow([a, b, b not in failed, row])
        print(f"wrote {OUT_CSV}")

        ok = (
            sute_from_hist == "4377025626"
            and sute_can == "4377025626"
            and master_unchanged == before["hist_tx_sute"]
            and allxall is not None
            and int(allxall["count"] or 0) > 0
            and sute_can in kept
            and shincheok in kept
            and not failed
        )
        print("VERIFY", "PASS" if ok else "FAIL", "allxall", dict(allxall) if allxall else None)
        return 0 if ok else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
