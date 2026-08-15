"""주거 전월세 CSV → 원장 행 (전환율 없음)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from rent.molit_schemas import HEADER_MAP, RentAssetType, normalize_header

_BLANK = {"", "-", "nan", "none", "null", "NaN", "None"}


def detect_molit_csv_skiprows(file_path: str | Path) -> int:
    path = Path(file_path)
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            with path.open(encoding=enc, errors="strict") as fh:
                for i, line in enumerate(fh):
                    stripped = line.strip().lstrip("\ufeff")
                    if stripped.startswith('"NO"') or stripped.startswith("NO,"):
                        return i
                    if stripped.startswith('"순번"') or stripped.startswith("순번,"):
                        return i
            break
        except UnicodeDecodeError:
            continue
    return 15


def read_rent_csv(path: Path) -> pd.DataFrame:
    skip = detect_molit_csv_skiprows(path)
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            df = pd.read_csv(
                path,
                skiprows=skip,
                header=0,
                dtype=str,
                encoding=enc,
                on_bad_lines="skip",
                low_memory=False,
            )
            break
        except UnicodeDecodeError as exc:
            last_err = exc
            df = None
    else:
        raise last_err or UnicodeDecodeError("utf-8", b"", 0, 1, "rent csv encoding")
    assert df is not None
    df.columns = [normalize_header(c) for c in df.columns]
    rename = {k: v for k, v in HEADER_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)
    if "NO" in df.columns:
        df = df[df["NO"].notna() & (df["NO"].astype(str).str.strip() != "")]
    return df


def _blank_series(s: pd.Series) -> pd.Series:
    t = s.fillna("").astype(str).str.strip()
    return t.mask(t.isin(_BLANK), None)


def _manwon(s: pd.Series) -> pd.Series:
    t = s.fillna("").astype(str).str.replace(",", "", regex=False).str.strip()
    t = t.mask(t.isin(_BLANK), None)
    return pd.to_numeric(t, errors="coerce")


def _fmt_num(s: pd.Series) -> pd.Series:
    return s.map(lambda x: "" if x is None or (isinstance(x, float) and pd.isna(x)) else f"{float(x):g}")


def _tx_hash_series(df: pd.DataFrame, asset_type: str) -> pd.Series:
    def _s(col: str) -> pd.Series:
        if col not in df.columns:
            return pd.Series("", index=df.index)
        return df[col].fillna("").astype(str)

    nan_s = pd.Series(np.nan, index=df.index)
    raw = (
        asset_type
        + "|" + _s("addr1")
        + "|" + _s("addr2")
        + "|" + _s("addr3")
        + "|" + _s("addr4")
        + "|" + _s("addr5")
        + "|" + _s("lot_number")
        + "|" + _s("lot_bun")
        + "|" + _s("lot_ji")
        + "|" + _s("building_name")
        + "|" + _fmt_num(df["exclusive_area"] if "exclusive_area" in df.columns else nan_s)
        + "|" + _fmt_num(df["contract_area"] if "contract_area" in df.columns else nan_s)
        + "|" + _fmt_num(df["floor"] if "floor" in df.columns else nan_s)
        + "|" + df["contract_date"].astype(str)
        + "|" + _fmt_num(df["deposit_manwon"])
        + "|" + _fmt_num(df["monthly_rent_manwon"])
        + "|" + _s("molit_lease_kind")
    )
    return raw.map(lambda x: hashlib.sha256(x.encode("utf-8")).hexdigest())


def refine_rent_dataframe(
    df: pd.DataFrame,
    asset_type: RentAssetType,
    *,
    source_path: str = "",
) -> pd.DataFrame:
    out = df.copy()
    for col in HEADER_MAP.values():
        if col not in out.columns:
            out[col] = None

    out["molit_lease_kind"] = _blank_series(out["molit_lease_kind"])
    out["building_name"] = _blank_series(out["building_name"])
    out["lot_number"] = _blank_series(out["lot_number"])
    out["lot_bun"] = _blank_series(out["lot_bun"])
    out["lot_ji"] = _blank_series(out["lot_ji"])
    out["road_name"] = _blank_series(out["road_name"])
    out["road_width_label"] = _blank_series(out["road_width_label"])
    out["lease_term_raw"] = _blank_series(out["lease_term_raw"])
    out["contract_class_raw"] = _blank_series(out["contract_class_raw"])
    out["renewal_right_raw"] = _blank_series(out["renewal_right_raw"])
    out["housing_subtype"] = _blank_series(out["housing_subtype"])

    for col in (
        "deposit_manwon",
        "monthly_rent_manwon",
        "prev_deposit_manwon",
        "prev_monthly_rent_manwon",
        "exclusive_area",
        "contract_area",
        "floor",
        "building_year",
        "contract_ym",
        "contract_day",
    ):
        out[col] = _manwon(out[col])

    day = out["contract_day"].fillna(1)
    day_num = pd.to_numeric(day, errors="coerce")
    day_str = day_num.apply(lambda x: str(int(x)).zfill(2) if pd.notna(x) else "")
    ym = (
        out["contract_ym"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    temp_dt = pd.to_datetime(ym + day_str, format="%Y%m%d", errors="coerce")
    out["contract_date"] = temp_dt.dt.date
    out["contract_year"] = temp_dt.dt.year
    out["contract_month"] = temp_dt.dt.month
    out["building_age"] = temp_dt.dt.year - out["building_year"]

    addr = out["sigungu"].fillna("").astype(str).str.split(" ", expand=True)
    for i in range(5):
        out[f"addr{i + 1}"] = addr[i] if i < addr.shape[1] else ""

    area = out["exclusive_area"] if asset_type != "detached" else out["contract_area"]
    area = pd.to_numeric(area, errors="coerce")
    dep = pd.to_numeric(out["deposit_manwon"], errors="coerce")
    mon = pd.to_numeric(out["monthly_rent_manwon"], errors="coerce")
    per = area.where(area > 0)
    out["deposit_per_m2"] = (dep / per).replace([np.inf, -np.inf], np.nan)
    out["monthly_per_m2"] = (mon / per).replace([np.inf, -np.inf], np.nan)

    if asset_type == "detached":
        out["exclusive_area"] = np.nan
        out["floor"] = np.nan
        out["lot_bun"] = None
        out["lot_ji"] = None
        out["building_name"] = None
    else:
        out["contract_area"] = np.nan
        out["road_width_label"] = None

    out["asset_type"] = asset_type
    out["source_path"] = source_path
    out = out[out["contract_date"].notna()].copy()
    out["is_valid"] = True
    out["transaction_hash"] = _tx_hash_series(out, asset_type)
    return out
