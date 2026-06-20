#!/usr/bin/env python3
"""MOLIT raw base 집합 행 건수·집합/일반 비율 스캔 (ingest 전 검증)."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from molit_raw_common import FACTORY_DIR, SHOP_DIR, iter_molit_csvs, read_molit_csv

REPO = Path(__file__).resolve().parents[2]


def _scan_dir(label: str, base_dir: Path, glob_pattern: str) -> None:
    if not base_dir.is_dir():
        print(f"[{label}] MISSING {base_dir}")
        return
    total = collective = general = 0
    files = 0
    for path in iter_molit_csvs(base_dir, pattern=glob_pattern):
        files += 1
        raw = read_molit_csv(path)
        if raw.empty or raw.shape[1] < 3:
            continue
        type_col = raw.iloc[:, 2].astype(str).str.strip()
        n_col = len(type_col)
        total += n_col
        collective += int((type_col == "집합").sum())
        general += int((type_col == "일반").sum())
    print(f"[{label}] files={files} rows={total:,} 집합={collective:,} 일반={general:,}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--shop-only", action="store_true")
    p.add_argument("--factory-only", action="store_true")
    args = p.parse_args()
    do_shop = not args.factory_only
    do_factory = not args.shop_only
    if do_shop:
        _scan_dir("상업업무", SHOP_DIR, "*_상업업무_매매_*.csv")
    if do_factory:
        _scan_dir("공장창고", FACTORY_DIR, "*_공장창고_매매_*.csv")


if __name__ == "__main__":
    main()
