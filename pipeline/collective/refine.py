"""
MOLIT raw or refined xlsx → canonical collective DataFrame.

참고: 1.아파트 / 2.연립다세대 / 4.오피스텔 통합 정제.ipynb
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from molit_schemas import REFINED_COL_MAP, SCHEMAS, AssetType

InputKind = Literal["raw", "refined"]

MOLIT_RAW_SKIPROWS = 13
# 국토부 CSV(오피스텔 등): 1~16행 메타·헤더, 17행부터 데이터 (header=None iloc 기준)
MOLIT_CSV_SKIPROWS = 16


def _normalize_dong(val, *, max_len: int = 64) -> str | None:
    """원본 MOLIT 동 — '-', 공란, 숫자형 101.0 등 정규화."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("-", "nan", "none", "null"):
        return None
    if re.match(r"^\d+\.0$", s):
        s = s[:-2]
    if len(s) > max_len:
        s = s[:max_len]
    return s or None


def _get_col(df: pd.DataFrame, idx: int, default=None):
    if df.shape[1] > idx:
        return df.iloc[:, idx]
    if default is not None:
        return pd.Series([default] * len(df), index=df.index)
    return pd.Series([None] * len(df), index=df.index)


def _extract_raw(df: pd.DataFrame, asset_type: AssetType) -> pd.DataFrame:
    schema = SCHEMAS[asset_type]
    out = pd.DataFrame(index=df.index)
    for logical, idx in schema.columns.items():
        out[logical] = _get_col(df, idx)
    out["asset_type"] = asset_type
    if "_source_key" in df.columns:
        out["_source_key"] = df["_source_key"]

    if df.shape[1] > schema.cancel_col:
        cancel_val = df.iloc[:, schema.cancel_col].astype(str).str.strip()
        mask = ~cancel_val.str.match(schema.cancel_regex, na=False)
        out = out.loc[mask].copy()

    out["price"] = (
        out["price"].astype(str).str.replace(",", "", regex=False)
    )
    num_cols = [
        "exclusive_area",
        "land_area",
        "contract_ym",
        "contract_day",
        "price",
        "floor",
        "building_year",
    ]
    for col in num_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    if "dong" in out.columns:
        out["dong"] = out["dong"].map(_normalize_dong)

    day = out["contract_day"]
    if schema.contract_day_fillna is not None:
        day = day.fillna(schema.contract_day_fillna)
    day_num = pd.to_numeric(day, errors="coerce")
    day_str = day_num.apply(lambda x: str(int(x)).zfill(2) if pd.notna(x) else "")
    temp_dt = pd.to_datetime(
        out["contract_ym"].astype(str).str.replace(r"\.0$", "", regex=True) + day_str,
        format="%Y%m%d",
        errors="coerce",
    )
    out["contract_date"] = temp_dt.dt.date
    out["contract_year"] = temp_dt.dt.year
    out["contract_month"] = temp_dt.dt.month

    if "building_year" in out.columns:
        out["building_age"] = temp_dt.dt.year - out["building_year"]
    else:
        out["building_year"] = None
        out["building_age"] = np.nan

    addr = out["sigungu"].astype(str).str.split(" ", expand=True)
    for i in range(5):
        out[f"addr{i + 1}"] = addr[i] if i < addr.shape[1] else ""
    out["lot_number"] = out.get("lot_number", out.get("lot_number"))
    out["road_name"] = out.get("road_name")
    out["housing_subtype"] = out.get("housing_subtype")
    if "dong" not in out.columns:
        out["dong"] = None
    if asset_type == "rowhouse" and "land_area" in out.columns:
        out["land_area"] = pd.to_numeric(out["land_area"], errors="coerce")
    elif asset_type != "rowhouse":
        out["land_area"] = None

    out["area_bucket"] = (out["exclusive_area"] / 30).round() * 30
    out["age_bucket"] = (out["building_age"] / 10).round() * 10
    out["unit_price"] = (
        (out["price"] / out["exclusive_area"])
        .replace([np.inf, -np.inf], np.nan)
    )
    return out


def _load_refined(df: pd.DataFrame, asset_type: AssetType) -> pd.DataFrame:
    source_key = df["_source_key"] if "_source_key" in df.columns else None
    rename = {k: v for k, v in REFINED_COL_MAP.items() if k in df.columns}
    out = df.rename(columns=rename).copy()
    if source_key is not None:
        out["_source_key"] = source_key.values
    if "building_name" not in out.columns:
        if "단지명" in df.columns:
            out["building_name"] = df["단지명"]
        elif "건물명" in df.columns:
            out["building_name"] = df["건물명"]
    out["asset_type"] = asset_type

    if "contract_date_label" in out.columns:
        s = out["contract_date_label"].astype(str).str.strip()
        s = s.where(s.str.len() == 6, None)
        out["contract_date"] = pd.to_datetime(s, format="%y%m%d", errors="coerce").dt.date
        out["contract_year"] = pd.to_datetime(s, format="%y%m%d", errors="coerce").dt.year
        out["contract_month"] = pd.to_datetime(s, format="%y%m%d", errors="coerce").dt.month

    for col in ("exclusive_area", "land_area", "price", "floor", "building_age", "area_bucket", "age_bucket", "unit_price"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    if "unit_price" not in out.columns or out["unit_price"].isna().all():
        out["unit_price"] = out["price"] / out["exclusive_area"]

    for i in range(1, 6):
        c = f"addr{i}"
        if c not in out.columns:
            out[c] = None
    if "road_name" not in out.columns:
        out["road_name"] = None
    if "housing_subtype" not in out.columns:
        out["housing_subtype"] = None
    if "land_area" not in out.columns:
        out["land_area"] = None
    if "dong" not in out.columns:
        out["dong"] = None
    else:
        out["dong"] = out["dong"].map(_normalize_dong)
    return out


def refine_dataframe(
    df: pd.DataFrame,
    asset_type: AssetType,
    *,
    input_kind: InputKind = "refined",
) -> pd.DataFrame:
    if input_kind == "raw":
        work = _extract_raw(df, asset_type)
    else:
        work = _load_refined(df, asset_type)

    work = work.dropna(subset=["price", "exclusive_area"])
    work = work[work["exclusive_area"] > 0]
    work = work[work["price"] > 0]
    return work.reset_index(drop=True)


def read_molit_raw_csv(path) -> pd.DataFrame:
    """MOLIT 자료실 CSV — skiprows=16, iloc 컬럼 인덱스는 xlsx raw와 동일."""
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(
                path,
                header=None,
                skiprows=MOLIT_CSV_SKIPROWS,
                encoding=enc,
                dtype=str,
                keep_default_na=False,
            )
        except UnicodeDecodeError as e:
            last_err = e
    if last_err:
        raise last_err
    raise RuntimeError(f"failed to read csv: {path}")


def read_source_excel(path) -> tuple[pd.DataFrame, InputKind]:
    """정제 xlsx vs MOLIT raw(13행 헤더) 자동 판별."""
    probe = pd.read_excel(path, nrows=5)
    if detect_input_kind(probe) == "refined":
        return pd.read_excel(path), "refined"
    return pd.read_excel(path, header=None, skiprows=MOLIT_RAW_SKIPROWS), "raw"


def read_source_file(path) -> tuple[pd.DataFrame, InputKind]:
    """xlsx 또는 MOLIT raw csv."""
    p = Path(path) if not isinstance(path, Path) else path
    if p.suffix.lower() == ".csv":
        return read_molit_raw_csv(p), "raw"
    return read_source_excel(p)


def refine_excel(path, asset_type: AssetType, *, input_kind: InputKind | None = None) -> pd.DataFrame:
    if input_kind is None:
        df, input_kind = read_source_file(path)
    elif input_kind == "raw":
        p = Path(path)
        if p.suffix.lower() == ".csv":
            df = read_molit_raw_csv(p)
        else:
            df = pd.read_excel(path, header=None, skiprows=MOLIT_RAW_SKIPROWS)
    else:
        df = pd.read_excel(path)
    return refine_dataframe(df, asset_type, input_kind=input_kind)


def detect_input_kind(df: pd.DataFrame) -> InputKind:
    cols = set(str(c) for c in df.columns)
    if cols & {"주소1", "주1", "단지명", "건물명", "전용면적"}:
        return "refined"
    return "raw"
