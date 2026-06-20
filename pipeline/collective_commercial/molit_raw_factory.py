"""MOLIT raw base 공장창고 CSV → collective_factory (집합만)."""

from __future__ import annotations

from molit_raw_common import FACTORY_DIR, load_from_dir


def load_collective_factory_molit(*, year_from: int = 2021, year_to: int = 2026) -> pd.DataFrame:
    if not FACTORY_DIR.is_dir():
        raise FileNotFoundError(f"MOLIT factory raw base not found: {FACTORY_DIR}")
    return load_from_dir(
        FACTORY_DIR,
        glob_pattern="*_공장창고_매매_*.csv",
        asset_type="collective_factory",
        year_from=year_from,
        year_to=year_to,
    )
