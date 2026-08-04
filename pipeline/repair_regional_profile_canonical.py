# -*- coding: utf-8 -*-
"""Remove stale historical regional_profile rows when canonical profile exists (D-028).

Usage:
  cd backend
  .venv/Scripts/python.exe ../pipeline/repair_regional_profile_canonical.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env", override=True)

from sqlalchemy import text

from collective.db_utils import get_collective_engine
from db_utils import get_engine
from region_canonical import RESOLVE_CHANGE_TYPES

_TYPES = ",".join(f"'{t}'" for t in RESOLVE_CHANGE_TYPES)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    land = get_engine()
    coll = get_collective_engine()

    with land.connect() as conn:
        pairs = conn.execute(
            text(
                f"""
                SELECT DISTINCT ON (from_code) from_code, to_code
                FROM region_code_history
                WHERE change_type IN ({_TYPES})
                ORDER BY from_code, effective_from DESC, id DESC
                """
            )
        ).fetchall()

    deleted = 0
    with coll.begin() as conn:
        for row in pairs:
            hist = str(row.from_code).strip()
            canon = str(row.to_code).strip()
            if len(hist) >= 8 and len(canon) >= 8 and hist[:8] == canon[:8]:
                continue
            for level, hcode, ccode in (
                ("eupmyeondong", hist[:8], canon[:8]),
                ("beopjungri", hist, canon),
            ):
                if hcode == ccode:
                    continue
                hist_row = conn.execute(
                    text(
                        """
                        SELECT feature_count FROM regional_profile
                        WHERE region_level=:lv AND region_code=:c
                          AND profile_version='v2.1-national' AND window_years=3
                        ORDER BY as_of_month DESC LIMIT 1
                        """
                    ),
                    {"lv": level, "c": hcode},
                ).scalar()
                canon_row = conn.execute(
                    text(
                        """
                        SELECT feature_count FROM regional_profile
                        WHERE region_level=:lv AND region_code=:c
                          AND profile_version='v2.1-national' AND window_years=3
                        ORDER BY as_of_month DESC LIMIT 1
                        """
                    ),
                    {"lv": level, "c": ccode},
                ).scalar()
                if hist_row is None:
                    continue
                if canon_row is None:
                    if args.dry_run:
                        print(f"DRY rename {level} {hcode} -> {ccode}")
                        continue
                    n = conn.execute(
                        text(
                            """
                            UPDATE regional_profile SET region_code=:canon
                            WHERE region_level=:lv AND region_code=:hist
                            """
                        ),
                        {"lv": level, "hist": hcode, "canon": ccode},
                    ).rowcount
                    print(f"renamed {level} {hcode}->{ccode} rows={n}")
                    continue
                if int(canon_row or 0) >= int(hist_row or 0):
                    if args.dry_run:
                        print(f"DRY delete stale {level} {hcode} (canon fc={canon_row})")
                        continue
                    n = conn.execute(
                        text(
                            """
                            DELETE FROM regional_profile
                            WHERE region_level=:lv AND region_code=:hist
                            """
                        ),
                        {"lv": level, "hist": hcode},
                    ).rowcount
                    deleted += int(n or 0)
                    print(f"deleted stale {level} {hcode} rows={n} (canon fc={canon_row})")

    print(f"done deleted={deleted} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
