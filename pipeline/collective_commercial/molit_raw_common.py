"""MOLIT 상업업무·공장창고 CSV 공통 파서 — raw base SSOT (2021~2026).

주거 집합(`collective/molit_schemas.py`)과 달리 **유형** 컬럼으로 집합/일반을 구분한다.
본 모듈은 **유형 == 집합** 행만 정제 DataFrame으로 반환한다.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
RAW_BASE = REPO / "raw" / "raw base"
SHOP_DIR = RAW_BASE / "상업업무_2021_2026"
FACTORY_DIR = RAW_BASE / "공장창고_2021_2026"

MOLIT_SKIPROWS = 16


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


def _parse_contract_date(cy: int | None, cm: int | None, day_raw) -> date | None:
    if cy is None or cm is None:
        return None
    day = 1
    if day_raw is not None and not (isinstance(day_raw, float) and pd.isna(day_raw)):
        try:
            day = int(float(str(day_raw).strip()))
        except (TypeError, ValueError):
            day = 1
    try:
        return date(int(cy), int(cm), max(1, min(day, 28)))
    except ValueError:
        try:
            return date(int(cy), int(cm), 1)
        except ValueError:
            return None


def parse_collective_rows(raw: pd.DataFrame, *, asset_type: str, source_file: str) -> pd.DataFrame:
    """MOLIT 상업/공장 DataFrame → 집합 행만 canonical dict rows."""
    if raw.empty or raw.shape[1] < 11:
        return pd.DataFrame()

    type_col = raw.iloc[:, 2].astype(str).str.strip()
    sub = raw.loc[type_col == "집합"].copy()
    if sub.empty:
        return pd.DataFrame()

    rows = []
    for r in sub.itertuples(index=False):
        vals = list(r)
        full_addr = vals[1] if len(vals) > 1 else None
        lot = vals[3] if len(vals) > 3 else None
        road = vals[4] if len(vals) > 4 else None
        zone = vals[5] if len(vals) > 5 else None
        use = vals[6] if len(vals) > 6 else None
        road_width_raw = vals[7] if len(vals) > 7 else None
        gross = vals[8] if len(vals) > 8 else None
        price = _parse_price(vals[10] if len(vals) > 10 else None)
        floor_raw = vals[11] if len(vals) > 11 else None
        land_raw = vals[9] if len(vals) > 9 else None
        cy, cm = _parse_yyyymm(vals[14] if len(vals) > 14 else None)
        day_raw = vals[15] if len(vals) > 15 else None
        by_raw = vals[17] if len(vals) > 17 else None
        buyer = vals[12] if len(vals) > 12 else None
        seller = vals[13] if len(vals) > 13 else None
        deal_type = vals[19] if len(vals) > 19 else None
        cancel_raw = vals[18] if len(vals) > 18 else None

        if cancel_raw is not None and not (isinstance(cancel_raw, float) and pd.isna(cancel_raw)):
            cs = str(cancel_raw).strip()
            if cs and cs.lower() not in ("nan", "-") and re.search(r"\d{4}", cs):
                continue

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
                "contract_date": _parse_contract_date(cy, cm, day_raw),
                "price": price,
                "gross_area": ga,
                "land_area": land_area,
                "building_year": building_year,
                "building_age": building_age,
                "floor": floor,
                "road_code": None,
                "road_width_label": road_width_label,
                "buyer_type": str(buyer).strip() if buyer is not None and str(buyer).strip() not in ("", "nan") else None,
                "seller_type": str(seller).strip() if seller is not None and str(seller).strip() not in ("", "nan") else None,
                "deal_type": str(deal_type).strip() if deal_type is not None and str(deal_type).strip() not in ("", "nan") else None,
                "source_file": source_file,
            }
        )
    return pd.DataFrame(rows)


def read_molit_csv(path: Path) -> pd.DataFrame:
    """MOLIT CSV — skiprows=16, header=None (주거 refine.py와 동일)."""
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(
                path,
                header=None,
                skiprows=MOLIT_SKIPROWS,
                encoding=enc,
                dtype=str,
                keep_default_na=False,
                on_bad_lines="skip",
            )
        except UnicodeDecodeError as e:
            last_err = e
        except pd.errors.ParserError:
            return pd.read_csv(
                path,
                header=None,
                skiprows=MOLIT_SKIPROWS,
                encoding=enc,
                dtype=str,
                keep_default_na=False,
                engine="python",
                on_bad_lines="skip",
            )
    if last_err:
        raise last_err
    raise RuntimeError(f"failed to read csv: {path}")


def _finalize(df: pd.DataFrame, *, year_from: int, year_to: int) -> pd.DataFrame:
    if df.empty:
        return df
    out = df[(df["contract_year"] >= year_from) & (df["contract_year"] <= year_to)].copy()
    out["unit_price"] = (out["price"] / out["gross_area"]).replace([np.inf, -np.inf], np.nan)
    out = out.dropna(subset=["unit_price"])
    out = out[out["unit_price"] > 0]
    return out.reset_index(drop=True)


def iter_molit_csvs(base_dir: Path, *, pattern: str) -> list[Path]:
    if not base_dir.is_dir():
        return []
    paths = sorted(base_dir.glob(pattern))
    failed = base_dir / "failed"
    return [p for p in paths if failed not in p.parents]


def load_from_dir(
    base_dir: Path,
    *,
    glob_pattern: str,
    asset_type: str,
    year_from: int = 2021,
    year_to: int = 2026,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in iter_molit_csvs(base_dir, pattern=glob_pattern):
        m = re.search(r"(20\d{2})", path.stem)
        if not m:
            continue
        year = int(m.group(1))
        if year < year_from or year > year_to:
            continue
        try:
            raw = read_molit_csv(path)
        except Exception as exc:
            raise RuntimeError(f"failed to read {path}: {exc}") from exc
        part = parse_collective_rows(raw, asset_type=asset_type, source_file=path.name)
        if not part.empty:
            frames.append(part)
    if not frames:
        return pd.DataFrame()
    return _finalize(pd.concat(frames, ignore_index=True), year_from=year_from, year_to=year_to)
