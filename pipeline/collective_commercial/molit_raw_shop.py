"""MOLIT raw base 상업업무 CSV → collective_shop (집합만)."""

from __future__ import annotations

import pandas as pd

from molit_raw_common import SHOP_DIR, load_from_dir


def load_collective_shop_molit(*, year_from: int = 2021, year_to: int = 2026) -> pd.DataFrame:
    if not SHOP_DIR.is_dir():
        raise FileNotFoundError(f"MOLIT shop raw base not found: {SHOP_DIR}")
    return load_from_dir(
        SHOP_DIR,
        glob_pattern="*_상업업무_매매_*.csv",
        asset_type="collective_shop",
        year_from=year_from,
        year_to=year_to,
    )
