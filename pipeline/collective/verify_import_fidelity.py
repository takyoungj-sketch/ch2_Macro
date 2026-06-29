"""MOLIT raw CSV → refine import fidelity (§3.4.1 매핑 검증).

Usage:
  py pipeline/collective/verify_import_fidelity.py apartment \\
      "raw/raw base/아파트_2021_2026/서울특별시_아파트_매매_2025.csv"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from molit_schemas import SCHEMAS, AssetType
from refine import _extract_raw, read_molit_raw_csv, refine_dataframe

PASS_PCT = 95.0
DISPLAY_COLS = ("buyer_type", "seller_type", "deal_type")


def _refined_work(df, asset_type: AssetType):
    """Same row set as refine_dataframe (before reset_index)."""
    work = _extract_raw(df, asset_type)
    work = work.dropna(subset=["price", "exclusive_area"])
    work = work[work["exclusive_area"] > 0]
    work = work[work["price"] > 0]
    return work


def verify(path: Path, asset_type: AssetType) -> int:
    raw = read_molit_raw_csv(path)
    work = _refined_work(raw, asset_type)
    refined = refine_dataframe(raw, asset_type, input_kind="raw")

    print(f"file={path.name}  asset_type={asset_type}  raw={len(raw)}  refined={len(refined)}")
    failed = False
    for col in DISPLAY_COLS:
        src = int(work[col].notna().sum()) if col in work.columns else 0
        db = int(refined[col].notna().sum())
        pct = 100.0 * db / src if src else 100.0
        ok = pct >= PASS_PCT
        flag = "OK" if ok else "FAIL"
        print(f"  {col:12} src_nonempty={src:6}  refined={db:6}  fidelity={pct:5.1f}%  [{flag}]")
        if not ok:
            failed = True

    if failed:
        print(f"\nAt least one column below {PASS_PCT}% - check molit_schemas col index.")
        return 1
    print(f"\nAll display columns >= {PASS_PCT}% import fidelity.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="MOLIT CSV import fidelity check (§3.4.1)")
    parser.add_argument("asset_type", choices=tuple(SCHEMAS.keys()))
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    path = args.csv_path
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(2)
    sys.exit(verify(path, args.asset_type))


if __name__ == "__main__":
    main()
