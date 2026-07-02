"""MOLIT raw base CSV → 집합상가·집합공장 (유형=집합).

정식 소스: ch2_Macro/raw/raw base/상업업무_2021_2026, 공장창고_2021_2026
(GUKTO xlsx는 초기 데이터 — 신규 적재에 사용하지 않음)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import pandas as pd

from built.molit_schemas import CANCEL_REGEX, COMMERCIAL_FACTORY, FILE_LABEL, RAW_BASE_DIRS
from built.refine_built import (
    _building_age,
    _get_col,
    _s,
    normalize_lot,
    normalize_road_name,
    normalize_road_width,
    parse_contract_dates,
    parse_optional_float,
    parse_price,
    parse_sigungu_to_addr,
    read_molit_csv,
)

CollectiveMolitAsset = Literal["collective_shop", "collective_factory"]

REPO = Path(__file__).resolve().parents[2]
RAW_BASE = REPO / "raw" / "raw base"
COLLECTIVE_TYPE = "집합"


def refine_collective_molit_dataframe(
    df: pd.DataFrame,
    *,
    asset_type: CollectiveMolitAsset,
) -> pd.DataFrame:
    """raw base CSV (skiprows=15) → 집합상가·집합공장 canonical rows."""
    if df.empty:
        return pd.DataFrame()

    schema = COMMERCIAL_FACTORY
    work = df.copy()

    if schema.type_filter_col is not None:
        types = _get_col(work, schema.type_filter_col).astype(str).str.strip()
        work = work.loc[types == COLLECTIVE_TYPE].copy()
    if work.empty:
        return pd.DataFrame()

    if work.shape[1] > schema.cancel_col:
        cancel_val = work.iloc[:, schema.cancel_col].astype(str).str.strip()
        work = work.loc[~cancel_val.str.match(CANCEL_REGEX, na=False)].copy()
    if work.empty:
        return pd.DataFrame()

    cols = schema.columns
    out = parse_sigungu_to_addr(_get_col(work, cols["sigungu"]))
    out["asset_type"] = asset_type
    out["lot_number"] = _get_col(work, cols["lot_number"]).map(normalize_lot)
    out["road_name"] = _get_col(work, cols["road_name"]).map(normalize_road_name)
    out["road_width_label"] = _get_col(work, cols["road_width_raw"]).map(normalize_road_width)
    out["road_code"] = None
    out["price"] = _get_col(work, cols["price"]).map(parse_price)
    out["gross_area"] = _get_col(work, cols["gross_area"]).map(parse_optional_float)
    out["land_area"] = _get_col(work, cols["land_area"]).map(parse_optional_float)
    out["floor"] = _get_col(work, cols["floor"]).map(parse_optional_float)
    out["building_use"] = _get_col(work, cols["building_use"]).map(_s).replace("", None)
    out["zone_type"] = _get_col(work, cols["zone_type"]).map(_s).replace("", None)
    out["deal_type"] = _get_col(work, cols["deal_type"]).map(_s).replace("", None)

    cdate, cyear, cmonth = parse_contract_dates(
        _get_col(work, cols["contract_ym"]),
        _get_col(work, cols["contract_day"]),
        day_fillna=schema.contract_day_fillna,
    )
    out["contract_date"] = cdate
    out["contract_year"] = cyear
    out["contract_month"] = cmonth

    by_raw = pd.to_numeric(_get_col(work, cols["building_year"]), errors="coerce")
    out["building_year"] = by_raw.astype("Int64").where((by_raw >= 1900) & (by_raw <= 2100))
    out["building_age"] = _building_age(cyear.astype(float), by_raw)

    out["is_valid"] = True
    out = out.dropna(subset=["price", "gross_area"])
    out = out[out["gross_area"] > 0]
    out["unit_price"] = out["price"] / out["gross_area"]

    road = out["road_name"].astype(str).str.strip()
    out = out[road.notna() & (road != "") & (road.str.lower() != "nan")].copy()
    return out.reset_index(drop=True)


def refine_collective_molit_file(path: Path, *, asset_type: CollectiveMolitAsset) -> pd.DataFrame:
    return refine_collective_molit_dataframe(read_molit_csv(path), asset_type=asset_type)


def _iter_molit_csv(folder: Path, *, year_from: int, year_to: int) -> list[Path]:
    if not folder.is_dir():
        return []
    paths: list[Path] = []
    for path in sorted(folder.glob("*.csv")):
        m = re.search(r"(20\d{2})", path.stem)
        if not m:
            continue
        year = int(m.group(1))
        if year_from <= year <= year_to:
            paths.append(path)
    return paths


def _load_from_folder(
    folder_name: str,
    file_label: str,
    *,
    asset_type: CollectiveMolitAsset,
    year_from: int,
    year_to: int,
) -> pd.DataFrame:
    folder = RAW_BASE / folder_name
    paths = _iter_molit_csv(folder, year_from=year_from, year_to=year_to)
    if not paths:
        raise FileNotFoundError(f"MOLIT CSV not found under {folder} ({year_from}~{year_to})")

    frames: list[pd.DataFrame] = []
    for path in paths:
        part = refine_collective_molit_file(path, asset_type=asset_type)
        if not part.empty:
            frames.append(part)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["unit_price"] = out["price"] / out["gross_area"]
    return out.reset_index(drop=True)


def load_collective_from_paths(
    paths: list[Path],
    *,
    asset_type: CollectiveMolitAsset,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        part = refine_collective_molit_file(path, asset_type=asset_type)
        if not part.empty:
            frames.append(part)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["unit_price"] = out["price"] / out["gross_area"]
    return out.reset_index(drop=True)


def load_collective_shop_raw(*, year_from: int = 2021, year_to: int = 2026) -> pd.DataFrame:
    return _load_from_folder(
        RAW_BASE_DIRS["commercial"],
        FILE_LABEL["commercial"],
        asset_type="collective_shop",
        year_from=year_from,
        year_to=year_to,
    )


def load_collective_factory_raw(*, year_from: int = 2021, year_to: int = 2026) -> pd.DataFrame:
    return _load_from_folder(
        RAW_BASE_DIRS["factory"],
        FILE_LABEL["factory"],
        asset_type="collective_factory",
        year_from=year_from,
        year_to=year_to,
    )
