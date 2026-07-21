# -*- coding: utf-8 -*-
"""Land upper + annual mart rebuild under D-028 canonical (sidos with code_reissue).

Does NOT touch Master beopjungri_code. Rebuilds:
  - land_upper_stats_v2 (as_of + windows)
  - land_annual_stats + land_annual_upper_stats (year range)

Default sidos: 41 (경기·화성 분구), 43 (충북·대소).

Usage:
  cd backend
  .venv/Scripts/python.exe ../pipeline/rebuild_land_upper_annual_canonical.py
  .venv/Scripts/python.exe ../pipeline/rebuild_land_upper_annual_canonical.py --dry-run
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "backend"))

OUT_MD = ROOT / "docs" / "reports" / "REGION_CODE_LAND_UPPER_ANNUAL_VERIFY.md"
DEFAULT_AS_OF = date(2026, 6, 1)
DEFAULT_SIDOS = ("41", "43")
DEFAULT_YEARS = "2010-2026"


def _run(cmd: list[str], *, dry_run: bool) -> int:
    print("+", " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.call(cmd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--as-of", default=DEFAULT_AS_OF.isoformat())
    ap.add_argument("--windows", default="3,5")
    ap.add_argument("--years", default=DEFAULT_YEARS)
    ap.add_argument("--sido-code", action="append", default=[], help="repeatable; default 41,43")
    ap.add_argument("--skip-upper", action="store_true")
    ap.add_argument("--skip-annual", action="store_true")
    args = ap.parse_args()

    sidos = [str(s).zfill(2)[:2] for s in (args.sido_code or list(DEFAULT_SIDOS))]
    py = sys.executable
    pipe = ROOT / "pipeline"

    from sqlalchemy import text

    from db_utils import get_engine
    from region_canonical import load_code_reissue_pairs_from_csv

    csv_1a = ROOT / "docs" / "reports" / "REGION_CODE_PHASE1A_CLASSIFICATION.csv"
    pairs = load_code_reissue_pairs_from_csv(csv_1a)
    pairs = [(a, b) for a, b in pairs if a[:2] in sidos or b[:2] in sidos]
    from_codes = sorted({a for a, _ in pairs})
    stale_eup = sorted({a[:8] for a, b in pairs if a[:8] != b[:8]})

    if not args.dry_run and (from_codes or stale_eup):
        eng = get_engine()
        with eng.begin() as conn:
            if from_codes:
                n = conn.execute(
                    text(
                        "DELETE FROM land_annual_stats WHERE beopjungri_code = ANY(:c)"
                    ),
                    {"c": from_codes},
                ).rowcount
                print(f"deleted land_annual_stats historical rows: {n}")
            if stale_eup:
                n = conn.execute(
                    text(
                        """
                        DELETE FROM land_upper_stats_v2
                        WHERE region_level = 'eupmyeondong'
                          AND region_code = ANY(:e)
                          AND as_of_month = :a
                        """
                    ),
                    {"e": stale_eup, "a": date.fromisoformat(args.as_of)},
                ).rowcount
                print(f"deleted land_upper_stats_v2 stale eup rows: {n}")
                n = conn.execute(
                    text(
                        """
                        DELETE FROM land_annual_upper_stats
                        WHERE region_level = 'eupmyeondong'
                          AND region_code = ANY(:e)
                        """
                    ),
                    {"e": stale_eup},
                ).rowcount
                print(f"deleted land_annual_upper_stats stale eup rows: {n}")

    rc = 0
    if not args.skip_upper:
        # build_upper only accepts one --sido-code; run per sido
        for s in sidos:
            one = [
                py,
                str(pipe / "build_upper_stats_v2.py"),
                "--as-of",
                args.as_of,
                "--windows",
                args.windows,
                "--col-axis",
                "both",
                "--sido-code",
                s,
            ]
            rc = _run(one, dry_run=args.dry_run) or rc

    if not args.skip_annual:
        cmd = [
            py,
            str(pipe / "build_annual_stats.py"),
            "--years",
            args.years,
            "--col-axis",
            "both",
            "--with-upper",
        ]
        for s in sidos:
            cmd.extend(["--sido-code", s])
        rc = _run(cmd, dry_run=args.dry_run) or rc

    if args.dry_run:
        print("dry-run done")
        return 0

    # smoke: 대소읍(43770256) eup upper + 수태리 annual under canonical
    from sqlalchemy import text

    from db_utils import get_engine

    eng = get_engine()
    as_of = date.fromisoformat(args.as_of)
    lines = [
        "# Land upper/annual canonical rebuild verify",
        "",
        f"- as_of={as_of} windows={args.windows} years={args.years} sidos={sidos}",
        "",
    ]
    with eng.connect() as conn:
        master = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM land_transactions WHERE beopjungri_code='4377034026'"
                )
            ).scalar()
            or 0
        )
        lines.append(f"- Master hist 수태리 tx (immutable expect 220): **{master}**")
        eup = conn.execute(
            text(
                """
                SELECT count FROM land_upper_stats_v2
                WHERE region_level='eupmyeondong' AND region_code='43770256'
                  AND as_of_month=:a AND window_years=3 AND col_axis='category'
                  AND zone_type='ALL' AND land_category='ALL'
                """
            ),
            {"a": as_of},
        ).scalar()
        lines.append(f"- upper eup 대소읍 ALL×ALL 3y count: **{eup}**")
        ann = conn.execute(
            text(
                """
                SELECT SUM(transaction_count)::int
                FROM land_annual_stats
                WHERE beopjungri_code='4377025626' AND col_axis='category'
                  AND zone_type='ALL' AND land_category='ALL'
                """
            )
        ).scalar()
        lines.append(f"- annual canonical 수태리 ALL×ALL sum(count): **{ann}**")
        hist_ann = conn.execute(
            text(
                """
                SELECT COALESCE(SUM(transaction_count),0)::int
                FROM land_annual_stats
                WHERE beopjungri_code='4377034026' AND col_axis='category'
                  AND zone_type='ALL' AND land_category='ALL'
                """
            )
        ).scalar()
        lines.append(f"- annual historical 구코드 sum (expect 0 after rebuild): **{hist_ann}**")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {OUT_MD}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
