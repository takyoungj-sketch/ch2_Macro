"""MOLIT raw base CSV → canonical built_transactions DataFrame."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from .molit_schemas import (
    CANCEL_REGEX,
    MOLIT_CSV_SKIPROWS,
    BuiltAssetType,
    SCHEMAS,
)

_EMPTY = {"", "-", "nan", "none", "null"}


def _s(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    t = str(v).strip()
    return "" if t.lower() in _EMPTY else t


def _get_col(df: pd.DataFrame, idx: int) -> pd.Series:
    if df.shape[1] > idx:
        return df.iloc[:, idx]
    return pd.Series([None] * len(df), index=df.index)


def parse_price(val: Any) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace(",", "").replace(" ", "")
    if not s or s in _EMPTY:
        return None
    try:
        n = float(s)
        return n if n > 0 else None
    except ValueError:
        return None


def parse_optional_float(val: Any) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace(",", "")
    if not s or s in _EMPTY:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_contract_dates(
    contract_ym: pd.Series,
    contract_day: pd.Series,
    *,
    day_fillna: int | None,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ym = contract_ym.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    day = contract_day.copy()
    if day_fillna is not None:
        day = day.fillna(day_fillna)
    day_num = pd.to_numeric(day, errors="coerce")
    day_str = day_num.apply(lambda x: str(int(x)).zfill(2) if pd.notna(x) else "")
    dt = pd.to_datetime(ym + day_str, format="%Y%m%d", errors="coerce")
    return dt.dt.date, dt.dt.year.astype("Int64"), dt.dt.month.astype("Int64")


def parse_sigungu_to_addr(sigungu: pd.Series) -> pd.DataFrame:
    parts = sigungu.astype(str).str.strip().str.split(" ", expand=True)
    out = pd.DataFrame(index=sigungu.index)
    for i in range(5):
        if i < parts.shape[1]:
            out[f"addr{i + 1}"] = parts[i].fillna("").astype(str).str.strip()
        else:
            out[f"addr{i + 1}"] = ""
    for c in out.columns:
        out[c] = out[c].map(_s)
    return out


def normalize_road_width(val: Any) -> str | None:
    s = _s(val)
    if not s or s == "-":
        return None
    return s[:32]


def normalize_road_name(val: Any) -> str | None:
    s = _s(val)
    return s[:64] if s else None


def normalize_lot(val: Any) -> str | None:
    s = _s(val)
    return s[:64] if s else None


def format_display_address(row: pd.Series) -> str | None:
    parts: list[str] = []
    for c in ("addr3", "addr4", "addr5"):
        v = _s(row.get(c))
        if v:
            parts.append(v)
    lot = _s(row.get("lot_number"))
    if lot:
        parts.append(lot)
    base = " ".join(parts)
    road = _s(row.get("road_name"))
    if road:
        return f"{base} ({road})".strip() if base else f"({road})"
    return base or None


def _building_age(contract_year: pd.Series, building_year: pd.Series) -> pd.Series:
    by = pd.to_numeric(building_year, errors="coerce")
    cy = pd.to_numeric(contract_year, errors="coerce")
    age = cy - by
    age = age.where((by >= 1900) & (by <= 2100))
    age = age.where((age >= 0) & (age <= 150))
    return age


def refine_molit_dataframe(df: pd.DataFrame, asset_type: BuiltAssetType) -> pd.DataFrame:
    """Raw MOLIT CSV (skiprows=15, with header) → refined rows."""
    if df.empty:
        return pd.DataFrame()

    schema = SCHEMAS[asset_type]
    work = df.copy()

    if schema.type_filter_col is not None and schema.type_filter_value:
        types = _get_col(work, schema.type_filter_col).astype(str).str.strip()
        work = work.loc[types == schema.type_filter_value].copy()
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
    out["deal_form"] = "general"
    out["lot_number"] = _get_col(work, cols["lot_number"]).map(normalize_lot)
    out["road_name"] = _get_col(work, cols["road_name"]).map(normalize_road_name)
    out["road_width_label"] = _get_col(work, cols["road_width_raw"]).map(normalize_road_width)
    out["road_code"] = None
    out["price"] = _get_col(work, cols["price"]).map(parse_price)
    out["gross_area"] = _get_col(work, cols["gross_area"]).map(parse_optional_float)
    out["land_area"] = _get_col(work, cols["land_area"]).map(parse_optional_float)
    if "floor" in cols:
        out["floor"] = _get_col(work, cols["floor"]).map(parse_optional_float)
    else:
        out["floor"] = None
    out["building_use"] = _get_col(work, cols["building_use"]).map(_s).replace("", None)

    if asset_type == "detached":
        out["zone_type"] = None
    else:
        out["zone_type"] = _get_col(work, cols["zone_type"]).map(_s).replace("", None)

    if "deal_type" in cols:
        out["deal_type"] = _get_col(work, cols["deal_type"]).map(_s).replace("", None)
    else:
        out["deal_type"] = None

    cdate, cyear, cmonth = parse_contract_dates(
        _get_col(work, cols["contract_ym"]),
        _get_col(work, cols["contract_day"]),
        day_fillna=schema.contract_day_fillna,
    )
    out["contract_date"] = cdate
    out["contract_year"] = cyear
    out["contract_month"] = cmonth
    out["trade_year_label"] = cyear.astype(str).str[-2:].where(cyear.notna(), None)

    by = _get_col(work, cols["building_year"])
    out["building_age"] = _building_age(cyear.astype(float), by)

    out["building_scale"] = None
    out["land_scale"] = None
    out["age_bucket"] = None
    out["is_valid"] = True

    out = out.dropna(subset=["price", "gross_area"])
    out = out[out["gross_area"] > 0]

    out["display_address"] = out.apply(format_display_address, axis=1)
    return out.reset_index(drop=True)


def read_molit_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, skiprows=MOLIT_CSV_SKIPROWS, encoding="cp949", low_memory=False)


def refine_molit_file(path: Path, asset_type: BuiltAssetType) -> pd.DataFrame:
    raw = read_molit_csv(path)
    return refine_molit_dataframe(raw, asset_type)
