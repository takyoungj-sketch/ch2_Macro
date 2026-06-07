"""GUKTO 공장창고 통합 xlsx → 집합공장 (상업업무용 원본과 동일 열 구조)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from gukto_raw_shop import _read_raw_file

GUKTO = Path(r"C:\startcoding\GUKTO")
RAW_INTEGRATED = GUKTO / "공장창고_매매" / "공장창고_매매_통합"


def load_collective_factory_raw(*, year_from: int = 2021, year_to: int = 2025) -> pd.DataFrame:
    if not RAW_INTEGRATED.is_dir():
        raise FileNotFoundError(f"GUKTO factory integrated dir not found: {RAW_INTEGRATED}")

    frames: list[pd.DataFrame] = []
    for path in sorted(RAW_INTEGRATED.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        part = _read_raw_file(path, asset_type="collective_factory")
        if not part.empty:
            frames.append(part)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out = out[(out["contract_year"] >= year_from) & (out["contract_year"] <= year_to)]
    out["unit_price"] = (out["price"] / out["gross_area"]).replace([np.inf, -np.inf], np.nan)
    out = out.dropna(subset=["unit_price"])
    out = out[out["unit_price"] > 0]
    return out.reset_index(drop=True)
