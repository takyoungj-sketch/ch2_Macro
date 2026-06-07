"""GUKTO 상업업무용 원본 xlsx → 집합상가 (도로명 포함)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

GUKTO = Path(r"C:\startcoding\GUKTO")
RAW_BASE = GUKTO / "상업업무용_매매"


def _parse_price(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace(",", "").replace(" ", "")
    if not s or s in ("-", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_yyyymm(val) -> tuple[int | None, int | None]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None, None
    s = re.sub(r"\D", "", str(val).strip())
    if len(s) >= 6:
        y, m = int(s[:4]), int(s[4:6])
        if 1900 <= y <= 2100 and 1 <= m <= 12:
            return y, m
    if len(s) == 4:
        y = int(s)
        if y < 100:
            y += 2000
        if 1900 <= y <= 2100:
            return y, None
    return None, None


def _split_address(full: str | None) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    if not full or not str(full).strip():
        return None, None, None, None, None
    parts = str(full).strip().split()
    if len(parts) < 2:
        return parts[0] if parts else None, None, None, None, None
    addr1, addr2 = parts[0], parts[1]
    rest = parts[2:]
    addr3 = rest[0] if len(rest) > 0 else None
    addr4 = rest[1] if len(rest) > 1 else None
    addr5 = rest[2] if len(rest) > 2 else None
    return addr1, addr2, addr3, addr4, addr5


def _read_raw_file(path: Path, *, asset_type: str = "collective_shop") -> pd.DataFrame:
    raw = pd.read_excel(path, skiprows=16, header=None)
    if raw.empty or raw.shape[1] < 11:
        return pd.DataFrame()
    sub = raw[raw.iloc[:, 2].astype(str).str.strip() == "집합"].copy()
    if sub.empty:
        return pd.DataFrame()

    rows = []
    for r in sub.itertuples(index=False):
        full_addr = r[1]
        lot = r[3]
        road = r[4]
        zone = r[5]
        use = r[6]
        road_width_raw = r[7] if len(r) > 7 else None
        gross = r[8]
        price = _parse_price(r[10])
        cy, cm = _parse_yyyymm(r[14] if len(r) > 14 else None)
        by_raw = r[17] if len(r) > 17 else None
        floor_raw = r[11] if len(r) > 11 else None
        land_raw = r[9] if len(r) > 9 else None
        addr1, addr2, addr3, addr4, addr5 = _split_address(full_addr)

        road_s = str(road).strip() if road is not None and not (isinstance(road, float) and pd.isna(road)) else ""
        if not road_s or road_s.lower() in ("nan", "-"):
            continue

        try:
            ga = float(gross)
        except (TypeError, ValueError):
            continue
        if ga <= 0 or price is None or price <= 0:
            continue

        building_year = None
        building_age = None
        if by_raw is not None and not (isinstance(by_raw, float) and pd.isna(by_raw)):
            try:
                v = float(by_raw)
                if v >= 1900:
                    building_year = int(round(v))
                elif 0 <= v <= 150 and cy:
                    building_age = v
                    building_year = int(cy) - int(round(v))
            except (TypeError, ValueError):
                pass

        floor = None
        if floor_raw is not None and not (isinstance(floor_raw, float) and pd.isna(floor_raw)):
            try:
                floor = float(floor_raw)
            except (TypeError, ValueError):
                pass

        land_area = _parse_price(land_raw)

        road_width_label = None
        if road_width_raw is not None and not (isinstance(road_width_raw, float) and pd.isna(road_width_raw)):
            rw = str(road_width_raw).strip()
            if rw and rw.lower() not in ("nan", "-"):
                road_width_label = rw

        rows.append(
            {
                "asset_type": asset_type,
                "full_address": str(full_addr).strip() if full_addr is not None else None,
                "addr1": addr1,
                "addr2": addr2,
                "addr3": addr3,
                "addr4": addr4,
                "addr5": addr5,
                "lot_number": str(lot).strip() if lot is not None and str(lot).strip() not in ("", "nan") else None,
                "road_name": road_s,
                "zone_type": str(zone).strip() if zone is not None else None,
                "building_use": str(use).strip() if use is not None else None,
                "contract_year": cy,
                "contract_month": cm,
                "contract_date": None,
                "price": price,
                "gross_area": ga,
                "land_area": land_area,
                "building_year": building_year,
                "building_age": building_age,
                "floor": floor,
                "road_code": None,
                "road_width_label": road_width_label,
                "source_file": path.name,
            }
        )
    return pd.DataFrame(rows)


def load_collective_shop_raw(*, year_from: int = 2021, year_to: int = 2025) -> pd.DataFrame:
    if not RAW_BASE.is_dir():
        raise FileNotFoundError(f"GUKTO raw base not found: {RAW_BASE}")
    frames: list[pd.DataFrame] = []
    for sido_dir in sorted(RAW_BASE.iterdir()):
        if not sido_dir.is_dir():
            continue
        for path in sorted(sido_dir.glob("*.xlsx")):
            if path.name.startswith("~$"):
                continue
            m = re.search(r"(20\d{2})", path.stem)
            if not m:
                continue
            year = int(m.group(1))
            if year < year_from or year > year_to:
                continue
            part = _read_raw_file(path, asset_type="collective_shop")
            if not part.empty:
                frames.append(part)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["unit_price"] = (out["price"] / out["gross_area"]).replace([np.inf, -np.inf], np.nan)
    out = out.dropna(subset=["unit_price"])
    out = out[out["unit_price"] > 0]
    return out.reset_index(drop=True)
