"""GUKTO 정제 xlsx → 집합상가·집합공장 canonical DataFrame."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

GUKTO = Path(r"C:\startcoding\GUKTO")

COL_MAP = {
    "주1": "addr1",
    "주2": "addr2",
    "주3": "addr3",
    "주4": "addr4",
    "주5": "addr5",
    "번지": "lot_number",
    "거래연도": "trade_year_label",
    "용도지역": "zone_type",
    "건축물용도": "building_use",
    "유형": "deal_type_label",
    "금액": "price",
    "연면적": "gross_area",
    "대지면적": "land_area",
    "대지규모": "land_area",
    "연식": "building_age",
    "도로": "road_code",
    "도로명": "road_name",
    "층": "floor",
}


def _find_refined(name_part: str) -> Path:
    for p in GUKTO.rglob("*.xlsx"):
        if p.name.startswith("~$"):
            continue
        if name_part in p.name and "정제" in str(p):
            return p
    raise FileNotFoundError(f"GUKTO refined not found: {name_part}")


def _parse_contract_year(label: object) -> int | None:
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return None
    s = str(label).strip().replace("'", "").replace("‘", "")
    if not s:
        return None
    if s.isdigit():
        n = int(s)
        if n < 100:
            return 2000 + n
        if n >= 1900:
            return n
    return None


def _normalize_df(df: pd.DataFrame, asset_type: str) -> pd.DataFrame:
    out = df.copy()
    for src, dst in COL_MAP.items():
        if src not in out.columns:
            continue
        if dst in out.columns:
            out[dst] = out[dst].combine_first(out[src])
            out = out.drop(columns=[src])
        else:
            out = out.rename(columns={src: dst})
    out["asset_type"] = asset_type
    out["contract_year"] = out["trade_year_label"].map(_parse_contract_year)
    out["contract_month"] = None
    out["contract_date"] = None
    for col in ("price", "gross_area", "land_area", "building_age", "road_code", "floor"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "road_code" in out.columns:
        out["road_code"] = out["road_code"].replace("-", pd.NA)
        out["road_code"] = pd.to_numeric(out["road_code"], errors="coerce")
    out["unit_price"] = (out["price"] / out["gross_area"]).replace([np.inf, -np.inf], np.nan)
    return out


def load_collective_shop_refined(*, year_from: int = 2021, year_to: int = 2025) -> pd.DataFrame:
    path = _find_refined("집합상")
    df = pd.read_excel(path)
    work = _normalize_df(df, "collective_shop")
    work = work[(work["contract_year"] >= year_from) & (work["contract_year"] <= year_to)]
    return _finalize(work)


def load_collective_factory_refined(*, year_from: int = 2021, year_to: int = 2025) -> pd.DataFrame:
    """레거시 정제 xlsx — 신규 적재는 gukto_raw_factory.load_collective_factory_raw 사용."""
    path = _find_refined("공장창고_매매_정제")
    df = pd.read_excel(path)
    if "유형" in df.columns:
        df = df[df["유형"].astype(str).str.strip() == "집합"].copy()
    work = _normalize_df(df, "collective_factory")
    work = work[(work["contract_year"] >= year_from) & (work["contract_year"] <= year_to)]
    return _finalize(work)


def _finalize(work: pd.DataFrame) -> pd.DataFrame:
    work = work.dropna(subset=["price", "gross_area"])
    work = work[(work["gross_area"] > 0) & (work["price"] > 0)]
    for c in ("addr1", "addr2", "addr3", "addr4", "addr5", "lot_number", "road_name", "zone_type", "building_use"):
        if c not in work.columns:
            work[c] = None
    return work.reset_index(drop=True)
