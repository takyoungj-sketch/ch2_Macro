"""같은 지번 아파트·오피스텔 가격비율 실험.

계획: docs/lab/APT_OFFICETEL_SAME_BUILDING_LAB.md
제품 회귀·층 효용·같은 지번 칩은 바꾸지 않는다.
문턱(15·10·40·30, 면적 0.85–1.15)은 결과를 본 뒤 내리지 않는다.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import bindparam, text

from app.collective.building_stats_query import latest_mart_snapshot
from app.collective.danji_attributes import ATTRIBUTES_TABLE
from app.collective.db import get_collective_engine
from app.parcel_lab.db import get_parcel_engine
from app.v2_stats_windows import period_bounds_for_window

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "apt_officetel_same_building.json"
LEDGER_PATH = Path(r"C:\CH2\parcel_master\building_ledger_v1.sqlite")
_TITLE_PURPOSE = 35
_TITLE_PURPOSE_DETAIL = 36
_TITLE_APPROVE = 60

WINDOW_YEARS = 5
STOP_MIN_PAIRS = 30
MATCH_MIN = 10
SIDE_MIN = 15
REG_TOTAL_MIN = 40
CELL_MIN = 15
REUSE_MEDIAN_MAX = 5
AREA_PRIMARY = (0.85, 1.15)
AREA_STRICT = (0.90, 1.10)
STRICT_DAYS = 92
_LOT_RE = re.compile(r"^(산)?\s*(\d+)(?:-(\d+))?$")
LEVERAGE_HC1 = 0.99
KAPT_SAME_PNU = "kapt_same_pnu"
METRO = ("부산", "대구", "인천", "대전", "울산", "광주")

KEY_SQL = """
SELECT btrim(beopjungri_code::text) AS bj,
       btrim(lot_number) AS lot,
       asset_type,
       building_key,
       COUNT(*)::int AS n,
       MIN(addr1) AS addr1,
       MIN(NULLIF(btrim(addr2::text), '')) AS addr2
FROM collective_transactions
WHERE is_valid
  AND asset_type IN ('apartment', 'officetel')
  AND contract_date >= :start
  AND contract_date <= :end
  AND price > 0
  AND exclusive_area > 0
  AND beopjungri_code IS NOT NULL
  AND lot_number IS NOT NULL
  AND btrim(lot_number) <> ''
  AND (deal_type IS NULL OR deal_type IN ('중개거래', '직거래'))
GROUP BY 1, 2, 3, 4
"""

TRADE_SQL = """
SELECT building_key,
       asset_type,
       btrim(beopjungri_code::text) AS bj,
       btrim(lot_number) AS lot,
       price::float8 AS price,
       exclusive_area::float8 AS area,
       floor::float8 AS floor,
       contract_date,
       NULLIF(btrim(dong), '') AS dong,
       addr1,
       NULLIF(btrim(addr2::text), '') AS addr2
FROM collective_transactions
WHERE is_valid
  AND asset_type IN ('apartment', 'officetel')
  AND contract_date >= :start
  AND contract_date <= :end
  AND price > 0
  AND exclusive_area > 0
  AND building_key IN :keys
  AND (deal_type IS NULL OR deal_type IN ('중개거래', '직거래'))
"""

ATTR_SQL = """
SELECT building_key, asset_type, approved_year, match_rule, max_floor
FROM collective_building_attributes
WHERE snapshot_ym = :snap
  AND asset_type IN ('apartment', 'officetel')
  AND building_key IN :keys
"""


def _r(value, ndigits: int = 4):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, ndigits)


def classify_years(n_apt_keys: int, n_off_keys: int, year_apt, year_off) -> str:
    """한 지번의 분류. 동 이름은 분류에 쓰지 않는다."""
    if n_apt_keys != 1 or n_off_keys != 1:
        return "multi_key"
    if year_apt is None or year_off is None:
        return "year_unknown"
    if abs(int(year_apt) - int(year_off)) <= 1:
        return "same_building"
    return "different_building"


def stratum_of(sido: str, place: str) -> str:
    if str(sido).startswith("서울"):
        return "서울"
    if any(str(sido).startswith(name) for name in METRO):
        return "광역시"
    if str(sido).startswith("전남광주"):
        last = str(place).split()[-1] if place else ""
        if last.endswith("구"):
            return "광역시"
    last = str(place).split()[-1] if place else ""
    if not last:
        last = str(sido)
    if last.endswith("군"):
        return "군"
    return "시"


def vintage_of(approved_year, as_of_year: int) -> str:
    if approved_year is None:
        return "그 밖"
    age = int(as_of_year) - int(approved_year)
    if 0 <= age <= 5:
        return "5년 이하"
    if age >= 20:
        return "20년 이상"
    return "그 밖"


def floors_within_20(left, right) -> bool:
    if left is None or right is None:
        return False
    a, b = float(left), float(right)
    if not math.isfinite(a) or not math.isfinite(b) or a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= 0.20 + 1e-12


def assign_floor_bands(floors: pd.Series) -> pd.Series:
    """키 자신의 거래로 나눈 저·중·고. 같은 층수는 한 대역이다."""
    out = pd.Series(pd.NA, index=floors.index, dtype="object")
    values = pd.to_numeric(floors, errors="coerce")
    valid = values.notna()
    if not valid.any():
        return out
    pct = values[valid].rank(method="average", pct=True)
    bands = pd.Series("mid", index=pct.index)
    bands = bands.mask(pct <= (1 / 3), "low")
    bands = bands.mask(pct > (2 / 3), "high")
    out.loc[valid] = bands.to_numpy()
    return out


def _year_or_none(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    number = float(value)
    if not math.isfinite(number) or number < 1900 or number > 2100:
        return None
    return int(number)


def distribution(values, *, min_n: int | None = None, below: float = 1.0, force_count_only: bool = False) -> dict:
    arr = np.asarray(
        [float(v) for v in values if v is not None and math.isfinite(float(v))],
        dtype=float,
    )
    n = int(arr.size)
    hidden = force_count_only or (min_n is not None and n < min_n)
    if n == 0 or hidden:
        return {"n": n, "median": None, "p25": None, "p75": None, "share_below": None}
    p25, med, p75 = np.percentile(arr, [25, 50, 75])
    return {
        "n": n,
        "median": _r(med),
        "p25": _r(p25),
        "p75": _r(p75),
        "share_below": _r(float(np.mean(arr < below))),
    }


def ratio_sign(median) -> str | None:
    if median is None:
        return None
    if median < 1:
        return "below"
    if median > 1:
        return "above"
    return "equal"


def sign_flipped(left, right) -> bool:
    a, b = ratio_sign(left), ratio_sign(right)
    if a is None or b is None or a == "equal" or b == "equal":
        return False
    return a != b


def match_trades(
    apt: pd.DataFrame,
    off: pd.DataFrame,
    *,
    area_lo: float,
    area_hi: float,
    time_col: str,
    floor_mode: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """오피스텔 거래마다 조건을 만족하는 아파트 거래가 하나라도 있으면 양쪽을 맞았다고 본다.

    floor_mode='band'는 키 안 저·중·고. floor_mode='absolute'는 절대층 ±2.
    반환은 아파트 사용 마스크, 오피스텔 사용 마스크, 아파트 거래별 재사용 횟수.
    """
    apt = apt.reset_index(drop=True)
    off = off.reset_index(drop=True)
    apt_used = np.zeros(len(apt), dtype=bool)
    off_used = np.zeros(len(off), dtype=bool)
    reuse = np.zeros(len(apt), dtype=np.int32)
    if apt.empty or off.empty:
        return apt_used, off_used, reuse

    apt_stamp = _stamp_array(apt[time_col])
    off_stamp = _stamp_array(off[time_col])
    apt_area = apt["area"].to_numpy(dtype=float)
    off_area = off["area"].to_numpy(dtype=float)
    apt_band = apt["band"].tolist() if floor_mode == "band" else None
    off_band = off["band"].tolist() if floor_mode == "band" else None
    apt_floor = apt["floor"].to_numpy(dtype=float)
    off_floor = off["floor"].to_numpy(dtype=float)

    buckets: dict[tuple, list[int]] = {}
    for i in range(len(apt)):
        if not math.isfinite(apt_area[i]) or apt_area[i] <= 0 or apt_stamp[i] is None:
            continue
        if floor_mode == "band":
            band = apt_band[i]
            if band is None or (isinstance(band, float) and math.isnan(band)) or pd.isna(band):
                continue
            key = (apt_stamp[i], band)
        else:
            if not math.isfinite(apt_floor[i]):
                continue
            key = (apt_stamp[i],)
        buckets.setdefault(key, []).append(i)
    ordered = {}
    for key, idxs_list in buckets.items():
        idxs = np.asarray(idxs_list, dtype=int)
        areas = apt_area[idxs]
        order = np.argsort(areas, kind="mergesort")
        ordered[key] = (idxs[order], areas[order], apt_floor[idxs][order])

    for j in range(len(off)):
        area = off_area[j]
        if not math.isfinite(area) or area <= 0 or off_stamp[j] is None:
            continue
        if floor_mode == "band":
            band = off_band[j]
            if band is None or (isinstance(band, float) and math.isnan(band)) or pd.isna(band):
                continue
            key = (off_stamp[j], band)
        else:
            if not math.isfinite(off_floor[j]):
                continue
            key = (off_stamp[j],)
        found = ordered.get(key)
        if found is None:
            continue
        idxs, areas, floors = found
        # 0.85·1.15 경계는 포함한다. 나눗셈 오차로 경계값이 빠지지 않게 아주 좁게만 넓힌다.
        slack = 1e-8
        left = int(np.searchsorted(areas, (area / area_hi) * (1 - slack), side="left"))
        right = int(np.searchsorted(areas, (area / area_lo) * (1 + slack), side="right"))
        if right <= left:
            continue
        hit = idxs[left:right]
        if floor_mode == "absolute":
            hit = hit[np.abs(floors[left:right] - off_floor[j]) <= 2]
            if hit.size == 0:
                continue
        off_used[j] = True
        apt_used[hit] = True
        reuse[hit] += 1
    return apt_used, off_used, reuse


def match_trades_window(
    apt: pd.DataFrame,
    off: pd.DataFrame,
    *,
    area_lo: float,
    area_hi: float,
    window_days: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """같은 층 대역 안에서 전용면적 비율과 계약일 차이가 동시에 맞는 거래."""
    apt = apt.reset_index(drop=True)
    off = off.reset_index(drop=True)
    apt_used = np.zeros(len(apt), dtype=bool)
    off_used = np.zeros(len(off), dtype=bool)
    reuse = np.zeros(len(apt), dtype=np.int32)
    if apt.empty or off.empty or "date_ord" not in apt.columns or "date_ord" not in off.columns:
        return apt_used, off_used, reuse
    apt_area = apt["area"].to_numpy(dtype=float)
    off_area = off["area"].to_numpy(dtype=float)
    apt_ord = apt["date_ord"].to_numpy(dtype=float)
    off_ord = off["date_ord"].to_numpy(dtype=float)
    apt_band = apt["band"].tolist()
    off_band = off["band"].tolist()
    buckets: dict[object, list[int]] = {}
    for i in range(len(apt)):
        band = apt_band[i]
        if (
            band is None
            or (isinstance(band, float) and math.isnan(band))
            or pd.isna(band)
            or not math.isfinite(apt_area[i])
            or apt_area[i] <= 0
            or not math.isfinite(apt_ord[i])
        ):
            continue
        buckets.setdefault(band, []).append(i)
    ordered = {}
    for band, idxs_list in buckets.items():
        idxs = np.asarray(idxs_list, dtype=int)
        ords = apt_ord[idxs]
        order = np.argsort(ords, kind="mergesort")
        ordered[band] = (idxs[order], apt_area[idxs][order], ords[order])
    slack = 1e-8
    for j in range(len(off)):
        area = off_area[j]
        band = off_band[j]
        if (
            band is None
            or (isinstance(band, float) and math.isnan(band))
            or pd.isna(band)
            or not math.isfinite(area)
            or area <= 0
            or not math.isfinite(off_ord[j])
        ):
            continue
        found = ordered.get(band)
        if found is None:
            continue
        idxs, areas, ords = found
        left = int(np.searchsorted(ords, off_ord[j] - window_days, side="left"))
        right = int(np.searchsorted(ords, off_ord[j] + window_days, side="right"))
        if right <= left:
            continue
        lo = (area / area_hi) * (1 - slack)
        hi = (area / area_lo) * (1 + slack)
        hit = idxs[left:right][(areas[left:right] >= lo) & (areas[left:right] <= hi)]
        if hit.size == 0:
            continue
        off_used[j] = True
        apt_used[hit] = True
        reuse[hit] += 1
    return apt_used, off_used, reuse


def pair_ratio(apt: pd.DataFrame, off: pd.DataFrame, apt_used, off_used, reuse) -> dict:
    n_apt = int(apt_used.sum())
    n_off = int(off_used.sum())
    used = reuse[apt_used]
    median_reuse = float(np.median(used)) if used.size else None
    out = {
        "n_matched_apt": n_apt,
        "n_matched_off": n_off,
        "ratio": None,
        "thin": n_apt < MATCH_MIN or n_off < MATCH_MIN,
        "reuse_flag": bool(median_reuse is not None and median_reuse > REUSE_MEDIAN_MAX),
        "median_reuse": _r(median_reuse, 2) if median_reuse is not None else None,
        "matched_area_apt": None,
        "matched_area_off": None,
    }
    if out["thin"] or n_apt == 0 or n_off == 0:
        return out
    apt_unit = apt["unit"].to_numpy(dtype=float)[apt_used]
    off_unit = off["unit"].to_numpy(dtype=float)[off_used]
    if not np.isfinite(apt_unit).all() or not np.isfinite(off_unit).all():
        apt_unit = apt_unit[np.isfinite(apt_unit)]
        off_unit = off_unit[np.isfinite(off_unit)]
    if apt_unit.size < MATCH_MIN or off_unit.size < MATCH_MIN:
        out["thin"] = True
        return out
    apt_med = float(np.median(apt_unit))
    off_med = float(np.median(off_unit))
    if apt_med <= 0:
        out["thin"] = True
        return out
    out["ratio"] = off_med / apt_med
    apt_area = apt["area"].to_numpy(dtype=float)[apt_used]
    off_area = off["area"].to_numpy(dtype=float)[off_used]
    apt_area = apt_area[np.isfinite(apt_area) & (apt_area > 0)]
    off_area = off_area[np.isfinite(off_area) & (off_area > 0)]
    if apt_area.size and off_area.size:
        out["matched_area_apt"] = float(np.median(apt_area))
        out["matched_area_off"] = float(np.median(off_area))
    return out


def _positive(value):
    try:
        if value is None or pd.isna(value):
            return None
    except TypeError:
        if value is None:
            return None
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def _stamp_array(series: pd.Series) -> np.ndarray:
    values = []
    for value in series.tolist():
        if value is None or value is pd.NA:
            values.append(None)
            continue
        try:
            if pd.isna(value):
                values.append(None)
                continue
        except TypeError:
            pass
        if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
            values.append(str(int(value)))
        else:
            text = str(value).strip()
            values.append(None if text in {"", "nan", "None", "<NA>"} else text)
    return np.asarray(values, dtype=object)


def hat_diag(x_values: np.ndarray) -> np.ndarray:
    q, _ = np.linalg.qr(x_values, mode="reduced")
    return np.sum(q * q, axis=1)


def _design(frame: pd.DataFrame) -> pd.DataFrame | None:
    if frame["officetel"].nunique() < 2:
        return None
    parts = [
        pd.Series(1.0, index=frame.index, name="const"),
        frame["officetel"].astype(float).rename("officetel"),
        np.log(frame["area"].astype(float)).rename("ln_area"),
    ]
    bands = [b for b in frame["band"].dropna().unique()]
    if len(bands) >= 2:
        ref = "mid" if "mid" in bands else sorted(bands)[0]
        for band in sorted(b for b in bands if b != ref):
            parts.append((frame["band"] == band).astype(float).rename(f"band_{band}"))
    years = sorted(int(y) for y in frame["year"].dropna().unique())
    if len(years) >= 2:
        for year in years[1:]:
            parts.append((frame["year"].astype(int) == year).astype(float).rename(f"yr_{year}"))
    matrix = pd.concat(parts, axis=1)
    keep = [col for col in matrix.columns if col == "const" or float(matrix[col].std(ddof=0) or 0) > 0]
    matrix = matrix[keep]
    if "officetel" not in matrix.columns:
        return None
    if len(matrix) <= matrix.shape[1]:
        return None
    return matrix


def fit_pair_percent(frame: pd.DataFrame) -> dict:
    """짝 하나의 오피스텔 항. 이상치를 빼지 않는다. 중심화하지 않는다."""
    matrix = _design(frame)
    if matrix is None:
        return {"ok": False, "reason": "설계행렬 불가"}
    y = np.log(frame.loc[matrix.index, "price"].to_numpy(dtype=float))
    x = matrix.to_numpy(dtype=float)
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        return {"ok": False, "reason": "비유한 값"}
    try:
        leverage = hat_diag(x)
        cov = "HC1" if np.any(leverage >= LEVERAGE_HC1) else "HC3"
        robust = sm.OLS(y, x).fit(cov_type=cov)
    except Exception as exc:  # noqa: BLE001 — 짝 하나의 실패는 분포에서만 뺀다
        return {"ok": False, "reason": str(exc.__class__.__name__)}
    names = list(matrix.columns)
    coef = float(robust.params[names.index("officetel")])
    ci = np.asarray(robust.conf_int())
    low, high = (float(v) for v in ci[names.index("officetel")])
    if not all(math.isfinite(v) for v in (coef, low, high)):
        return {"ok": False, "reason": "계수 비유한"}
    return {
        "ok": True,
        "percent": 100 * (math.exp(coef) - 1),
        "ci_low": 100 * (math.exp(low) - 1),
        "ci_high": 100 * (math.exp(high) - 1),
        "cov": cov,
        "n": int(len(matrix)),
    }


def fit_pooled(frame: pd.DataFrame) -> dict:
    """지번 고정효과는 짝 안 평균을 뺀 within 추정. 표준오차는 짝으로 묶는다."""
    if frame["pair_id"].nunique() < 2 or frame["officetel"].nunique() < 2:
        return {"ok": False, "reason": "짝이 2곳 미만"}
    design = frame[["officetel"]].astype(float).copy()
    design["ln_area"] = np.log(frame["area"].astype(float))
    bands = [b for b in frame["band"].dropna().unique()]
    if len(bands) >= 2:
        ref = "mid" if "mid" in bands else sorted(bands)[0]
        for band in sorted(b for b in bands if b != ref):
            design[f"band_{band}"] = (frame["band"] == band).astype(float)
    years = sorted(int(y) for y in frame["year"].dropna().unique())
    if len(years) >= 2:
        for year in years[1:]:
            design[f"yr_{year}"] = (frame["year"].astype(int) == year).astype(float)
    design["y"] = np.log(frame["price"].astype(float))
    design["pair_id"] = frame["pair_id"].to_numpy()
    cols = [c for c in design.columns if c not in ("y", "pair_id")]
    demeaned = design[cols + ["y"]] - design.groupby("pair_id")[cols + ["y"]].transform("mean")
    keep = [c for c in cols if float(demeaned[c].std(ddof=0) or 0) > 1e-12]
    if "officetel" not in keep:
        return {"ok": False, "reason": "오피스텔 항이 짝 안에서 변하지 않음"}
    y = demeaned["y"].to_numpy(dtype=float)
    x = demeaned[keep].to_numpy(dtype=float)
    try:
        robust = sm.OLS(y, x, hasconst=False).fit(
            cov_type="cluster",
            cov_kwds={"groups": design["pair_id"].to_numpy()},
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": str(exc.__class__.__name__)}
    idx = keep.index("officetel")
    coef = float(robust.params[idx])
    ci = np.asarray(robust.conf_int())
    low, high = float(ci[idx, 0]), float(ci[idx, 1])
    if not all(math.isfinite(v) for v in (coef, low, high)):
        return {"ok": False, "reason": "계수 비유한"}
    return {
        "ok": True,
        "percent": _r(100 * (math.exp(coef) - 1), 2),
        "ci_low": _r(100 * (math.exp(low) - 1), 2),
        "ci_high": _r(100 * (math.exp(high) - 1), 2),
        "n_pairs": int(frame["pair_id"].nunique()),
        "n_trades": int(len(frame)),
        "se": "cluster_pair",
    }


def _count_dist(values: list[int]) -> dict:
    if not values:
        return {"n": 0, "p10": None, "p50": None, "p90": None}
    arr = np.asarray(values, dtype=float)
    p10, p50, p90 = np.percentile(arr, [10, 50, 90])
    return {"n": int(arr.size), "p10": _r(p10, 1), "p50": _r(p50, 1), "p90": _r(p90, 1)}


def _area_span(series: pd.Series) -> dict:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {"n": 0, "p10": None, "p50": None, "p90": None}
    p10, p50, p90 = np.percentile(values.to_numpy(dtype=float), [10, 50, 90])
    return {"n": int(values.size), "p10": _r(p10, 2), "p50": _r(p50, 2), "p90": _r(p90, 2)}


def _chunks(items: list[str], size: int = 2000):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _read_in(conn, sql: str, params: dict, keys: list[str]) -> pd.DataFrame:
    frames = []
    stmt = text(sql).bindparams(bindparam("keys", expanding=True))
    for chunk in _chunks(keys):
        frames.append(pd.read_sql(stmt, conn, params={**params, "keys": chunk}))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def prepare_trades(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    out["building_key"] = out["building_key"].astype(str).str.strip()
    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out["area"] = pd.to_numeric(out["area"], errors="coerce")
    out["floor"] = pd.to_numeric(out["floor"], errors="coerce")
    out = out[(out["price"] > 0) & (out["area"] > 0)].copy()
    out["unit"] = out["price"] / out["area"]
    when = pd.to_datetime(out["contract_date"])
    out["year"] = when.dt.year.astype("Int64")
    out["quarter"] = out["year"].astype(str) + "Q" + (((when.dt.month - 1) // 3) + 1).astype(str)
    out["month"] = when.dt.strftime("%Y-%m")
    out["date_ord"] = (when - pd.Timestamp("1970-01-01")).dt.days
    out["band"] = pd.NA
    valid = out["floor"].notna()
    if valid.any():
        out.loc[valid, "band"] = (
            out.loc[valid].groupby("building_key", sort=False)["floor"].transform(assign_floor_bands).to_numpy()
        )
    return out


def evaluate_pairs(
    trades: pd.DataFrame,
    pairs: pd.DataFrame,
    *,
    area_lo: float,
    area_hi: float,
    time_col: str,
    floor_mode: str,
    reband: bool = False,
    date_window_days: int | None = None,
) -> list[dict]:
    if trades.empty or pairs.empty:
        return []
    work = trades
    if reband:
        work = trades.copy()
        work["band"] = pd.NA
        valid = work["floor"].notna()
        if valid.any():
            work.loc[valid, "band"] = (
                work.loc[valid].groupby("building_key", sort=False)["floor"].transform(assign_floor_bands).to_numpy()
            )
    by_key = {key: g for key, g in work.groupby("building_key", sort=False)}
    rows = []
    for pair in pairs.itertuples(index=False):
        apt = by_key.get(pair.apt_key, pd.DataFrame())
        off = by_key.get(pair.off_key, pd.DataFrame())
        if apt.empty or off.empty:
            rows.append(
                {
                    "pair_id": pair.pair_id,
                    "ratio": None,
                    "thin": True,
                    "reuse_flag": False,
                    "median_reuse": None,
                    "n_matched_apt": 0,
                    "n_matched_off": 0,
                    "matched_area_apt": None,
                    "matched_area_off": None,
                }
            )
            continue
        if date_window_days is None:
            apt_used, off_used, reuse = match_trades(
                apt, off, area_lo=area_lo, area_hi=area_hi, time_col=time_col, floor_mode=floor_mode
            )
        else:
            apt_used, off_used, reuse = match_trades_window(
                apt, off, area_lo=area_lo, area_hi=area_hi, window_days=date_window_days
            )
        item = pair_ratio(apt, off, apt_used, off_used, reuse)
        item["pair_id"] = pair.pair_id
        rows.append(item)
    return rows


def _iqr_keep(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    unit = frame["unit"].to_numpy(dtype=float)
    q1, q3 = np.percentile(unit, [25, 75])
    span = q3 - q1
    if not math.isfinite(span) or span <= 0:
        return frame
    keep = (unit >= q1 - 1.5 * span) & (unit <= q3 + 1.5 * span)
    return frame.loc[keep]


def filter_iqr_by_key(trades: pd.DataFrame) -> pd.DataFrame:
    parts = [_iqr_keep(g) for _, g in trades.groupby("building_key", sort=False)]
    if not parts:
        return trades.iloc[0:0]
    return pd.concat(parts, ignore_index=True)


def _side_by_side(primary_median, other: dict) -> dict:
    return {
        "distribution": other,
        "sign_flipped": sign_flipped(primary_median, other.get("median")),
    }


def regression_frame(trades: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    if trades.empty or pairs.empty:
        return pd.DataFrame()
    eligible = pairs[(pairs["n_apt"] >= SIDE_MIN) & (pairs["n_off"] >= SIDE_MIN) & (pairs["n_apt"] + pairs["n_off"] >= REG_TOTAL_MIN)]
    if eligible.empty:
        return pd.DataFrame()
    keys = set(eligible["apt_key"]).union(eligible["off_key"])
    work = trades[trades["building_key"].isin(keys)].copy()
    work = work[work["floor"].notna() & work["year"].notna() & work["band"].notna() & (work["price"] > 0) & (work["area"] > 0)]
    if work.empty:
        return work
    key_pair = {}
    key_off = {}
    for row in eligible.itertuples(index=False):
        key_pair[row.apt_key] = row.pair_id
        key_pair[row.off_key] = row.pair_id
        key_off[row.apt_key] = 0.0
        key_off[row.off_key] = 1.0
    work["pair_id"] = work["building_key"].map(key_pair)
    work["officetel"] = work["building_key"].map(key_off)
    return work.dropna(subset=["pair_id", "officetel"])


def run_regressions(frame: pd.DataFrame, direct_by_id: dict | None = None) -> dict:
    direct_by_id = direct_by_id or {}
    if frame.empty:
        return {
            "n_fit": 0,
            "n_failed": 0,
            "n_hc1": 0,
            "distribution": distribution([], below=0.0),
            "intervals": _interval_counts([]),
            "beside_direct": [],
            "pooled": {"ok": False, "reason": "표본 없음"},
        }
    beside = []
    failed = 0
    for pid, group in frame.groupby("pair_id", sort=False):
        if group["officetel"].nunique() < 2:
            failed += 1
            continue
        fitted = fit_pair_percent(group)
        if not fitted.get("ok"):
            failed += 1
            continue
        beside.append(
            {
                "direct_ratio": _r(direct_by_id.get(pid)),
                "percent": _r(fitted["percent"], 2),
                "ci_low": _r(fitted["ci_low"], 2),
                "ci_high": _r(fitted["ci_high"], 2),
                "cov": fitted["cov"],
                "n": fitted["n"],
            }
        )
    return {
        "n_fit": len(beside),
        "n_failed": failed,
        "n_hc1": sum(1 for row in beside if row["cov"] == "HC1"),
        "distribution": distribution([row["percent"] for row in beside], below=0.0),
        "intervals": _interval_counts(beside),
        "beside_direct": beside,
        "pooled": fit_pooled(frame),
    }


def _interval_counts(beside: list[dict]) -> dict:
    if not beside:
        return {
            "n": 0,
            "entirely_below_0": 0,
            "crosses_0": 0,
            "entirely_above_0": 0,
            "n_trades_min": None,
            "n_trades_median": None,
        }
    below = cross = above = 0
    ns = []
    for row in beside:
        ns.append(int(row["n"]))
        if row["ci_high"] < 0:
            below += 1
        elif row["ci_low"] > 0:
            above += 1
        else:
            cross += 1
    ns.sort()
    return {
        "n": len(beside),
        "entirely_below_0": below,
        "crosses_0": cross,
        "entirely_above_0": above,
        "n_trades_min": ns[0],
        "n_trades_median": ns[len(ns) // 2],
    }


def _headline(rows: list[dict]) -> dict:
    ratios = [row["ratio"] for row in rows if row.get("ratio") is not None]
    flagged = [row["ratio"] for row in rows if row.get("ratio") is not None and not row.get("reuse_flag")]
    dist = distribution(ratios)
    return {
        "pass_n": dist["n"],
        "thin_n": sum(1 for row in rows if row.get("thin")),
        "reuse_flag_n": sum(1 for row in rows if row.get("reuse_flag") and row.get("ratio") is not None),
        "distribution": dist,
        "without_reuse_flag": _side_by_side(dist.get("median"), distribution(flagged)),
    }


def _cell_table(pairs: pd.DataFrame, field: str, *, count_only: set[str] | None = None) -> dict:
    count_only = count_only or set()
    out = {}
    if pairs.empty or field not in pairs.columns:
        return out
    for name, group in pairs.groupby(field, sort=False):
        ratios = group["ratio"].dropna().tolist() if "ratio" in group else []
        force = str(name) in count_only
        item = distribution(ratios, min_n=CELL_MIN, force_count_only=force)
        out[str(name)] = item
    return out


def regression_selection(passed: pd.DataFrame, reg_ids: set) -> dict:
    """직접 비교를 통과한 곳 중 회귀에 들어간 곳과 거래량 때문에 빠진 곳. 주소는 저장하지 않는다."""

    def _counts(frame: pd.DataFrame, col: str) -> dict:
        if frame.empty or col not in frame.columns:
            return {}
        return {str(name): int(count) for name, count in frame[col].value_counts().items()}

    def _block(frame: pd.DataFrame) -> dict:
        ratios = frame["ratio"].tolist() if "ratio" in frame.columns else []
        return {
            "n": int(len(frame)),
            "ratio": distribution(ratios),
            "region_n": _counts(frame, "stratum"),
            "vintage_n": _counts(frame, "vintage"),
        }

    inside = passed[passed["pair_id"].isin(reg_ids)]
    outside = passed[~passed["pair_id"].isin(reg_ids)]
    return {
        "rule": "직접 비교를 통과한 곳 가운데 유형별 거래 15건 이상, 합계 40건 이상만 회귀에 넣는다.",
        "in_regression": _block(inside),
        "direct_only": _block(outside),
    }


def build_same_building_report(
    pairs: pd.DataFrame,
    trades: pd.DataFrame,
    as_of_year: int,
    primary: list[dict] | None = None,
) -> dict:
    """2단계 문턱을 넘긴 동일 건물 후보의 직접 비교·회귀·층위·민감도."""
    if primary is None:
        primary = evaluate_pairs(
            trades, pairs, area_lo=AREA_PRIMARY[0], area_hi=AREA_PRIMARY[1], time_col="year", floor_mode="band"
        )
    by_id = {row["pair_id"]: row for row in primary}
    held = pairs.copy()
    held["ratio"] = held["pair_id"].map(lambda pid: by_id.get(pid, {}).get("ratio"))
    held["thin"] = held["pair_id"].map(lambda pid: by_id.get(pid, {}).get("thin", True))
    held["reuse_flag"] = held["pair_id"].map(lambda pid: bool(by_id.get(pid, {}).get("reuse_flag")))
    passed = held[held["ratio"].notna()].copy()
    headline = _headline(primary)

    def _run(area, time_col, floor_mode, subset=None, source=None, reband=False):
        block = pairs if subset is None else subset
        base = trades if source is None else source
        return evaluate_pairs(
            base, block, area_lo=area[0], area_hi=area[1], time_col=time_col, floor_mode=floor_mode, reband=reband
        )

    area_10 = _headline(_run((0.90, 1.10), "year", "band"))
    area_20 = _headline(_run((0.80, 1.20), "year", "band"))
    quarter = _headline(_run(AREA_PRIMARY, "quarter", "band"))
    month_rows = _run(AREA_PRIMARY, "month", "band")
    month_pass = sum(1 for row in month_rows if row.get("ratio") is not None)

    close_mask = np.array(
        [floors_within_20(a, b) for a, b in zip(pairs["max_floor_apt"], pairs["max_floor_off"])],
        dtype=bool,
    )
    close_pairs = pairs.iloc[close_mask] if close_mask.any() else pairs.iloc[0:0]
    absolute = _headline(_run(AREA_PRIMARY, "year", "absolute", subset=close_pairs)) if not close_pairs.empty else _headline([])

    iqr_trades = filter_iqr_by_key(trades)
    iqr = _headline(_run(AREA_PRIMARY, "year", "band", source=iqr_trades, reband=True))

    kapt_pairs = pairs[~pairs["kapt_same_pnu"]]
    kapt_rows = [row for row in primary if row["pair_id"] in set(kapt_pairs["pair_id"])]
    no_kapt = _headline(kapt_rows)

    raw_ok = pairs[(pairs["n_apt"] >= SIDE_MIN) & (pairs["n_off"] >= SIDE_MIN)]
    raw_ratios = []
    area_ratios = []
    floor_gaps = []
    if not raw_ok.empty and not trades.empty:
        med = trades.groupby(["building_key"]).agg(unit=("unit", "median"), area=("area", "median"), floor=("floor", "median"))
        for row in raw_ok.itertuples(index=False):
            if row.apt_key not in med.index or row.off_key not in med.index:
                continue
            apt_m = med.loc[row.apt_key]
            off_m = med.loc[row.off_key]
            if float(apt_m.unit) <= 0:
                continue
            raw_ratios.append(float(off_m.unit) / float(apt_m.unit))
            if float(apt_m.area) > 0:
                area_ratios.append(float(off_m.area) / float(apt_m.area))
            if pd.notna(apt_m.floor) and pd.notna(off_m.floor):
                floor_gaps.append(float(off_m.floor) - float(apt_m.floor))

    reg_ids = set(
        passed.loc[
            (passed["n_apt"] >= SIDE_MIN) & (passed["n_off"] >= SIDE_MIN) & (passed["n_apt"] + passed["n_off"] >= REG_TOTAL_MIN),
            "pair_id",
        ]
    )
    reg_pairs = pairs[pairs["pair_id"].isin(reg_ids)]
    direct_by_id = {row["pair_id"]: row["ratio"] for row in primary if row.get("ratio") is not None}
    reg_public = run_regressions(regression_frame(trades, reg_pairs), direct_by_id)
    reg_public["n_eligible"] = int(len(reg_pairs))
    reg_public["n_direct_only"] = int(len(passed) - len(reg_pairs))

    passed = passed.copy()
    passed["stratum"] = [stratum_of(a, b or "") for a, b in zip(passed["addr1"], passed["addr2"])]
    passed["vintage"] = [vintage_of(y, as_of_year) for y in passed["approved_year_apt"]]
    reg_public["selection"] = regression_selection(passed, reg_ids)
    strict_rows = evaluate_pairs(
        trades,
        pairs,
        area_lo=AREA_STRICT[0],
        area_hi=AREA_STRICT[1],
        time_col="year",
        floor_mode="band",
        date_window_days=STRICT_DAYS,
    )
    headline_ids = {row["pair_id"] for row in primary if row.get("ratio") is not None}

    return {
        "direct": headline,
        "composition": {
            "note": "면적·층·연도를 맞추기 전 유형별 ㎡당 중앙값의 비. 본결과가 아니다.",
            "rule": "유형마다 창 안 거래 15건 이상",
            "distribution": distribution(raw_ratios),
            "median_area_ratio": _r(float(np.median(area_ratios))) if area_ratios else None,
            "median_floor_gap_off_minus_apt": _r(float(np.median(floor_gaps)), 2) if floor_gaps else None,
        },
        "regression": reg_public,
        "strata": {
            "region": _cell_table(passed, "stratum"),
            "vintage": _cell_table(passed, "vintage", count_only={"그 밖"}),
        },
        "sensitivity": {
            "area_pm15": headline["distribution"],
            "area_pm10": area_10["distribution"],
            "area_pm20": area_20["distribution"],
            "quarter": quarter["distribution"],
            "month_pass_n": month_pass,
            "absolute_floor_pm2": {
                "n_floors_within_20pct": int(close_mask.sum()),
                "n_floors_far": int((~close_mask).sum()),
                "distribution": absolute["distribution"],
            },
            "iqr_1_5": _side_by_side(headline["distribution"].get("median"), iqr["distribution"]),
            "without_kapt_same_pnu": _side_by_side(headline["distribution"].get("median"), no_kapt["distribution"]),
            "without_reuse_flag": headline["without_reuse_flag"],
        },
        "followup": {
            "matched_area": matched_area_summary(primary),
            "region_vintage": region_vintage_table(passed),
            "strict_90_92d": strict_summary(strict_rows, headline["distribution"].get("median"), headline_ids),
        },
    }


def matched_area_summary(rows: list[dict]) -> dict:
    """본결과에서 실제로 맞은 거래의 전용면적. 구간이 겹친다는 말과 따로 둔다."""
    apt_areas = []
    off_areas = []
    ratios = []
    for row in rows:
        if row.get("ratio") is None:
            continue
        apt_area = row.get("matched_area_apt")
        off_area = row.get("matched_area_off")
        if apt_area is None or off_area is None or apt_area <= 0:
            continue
        apt_areas.append(float(apt_area))
        off_areas.append(float(off_area))
        ratios.append(float(off_area) / float(apt_area))
    return {
        "n": len(ratios),
        "median_matched_area_apt": _r(float(np.median(apt_areas)), 2) if apt_areas else None,
        "median_matched_area_off": _r(float(np.median(off_areas)), 2) if off_areas else None,
        "area_ratio": distribution(ratios),
    }


def region_vintage_table(passed: pd.DataFrame) -> list[dict]:
    if passed.empty:
        return []
    rows = []
    for (region, vintage), group in passed.groupby(["stratum", "vintage"], sort=False):
        force = str(vintage) == "그 밖" or len(group) < CELL_MIN
        item = distribution(group["ratio"].tolist(), min_n=CELL_MIN, force_count_only=force)
        item["region"] = str(region)
        item["vintage"] = str(vintage)
        rows.append(item)
    return rows


def strict_summary(rows: list[dict], headline_median, headline_ids: set[str]) -> dict:
    passed = [row for row in rows if row.get("ratio") is not None]
    dist = distribution([row["ratio"] for row in passed])
    if dist["n"] < STOP_MIN_PAIRS:
        dist = {"n": dist["n"], "median": None, "p25": None, "p75": None, "share_below": None}
    return {
        "rule": "전용면적 비율 0.90–1.10, 계약일 차이 92일 이내, 키 안 층 대역. 양쪽 10건.",
        "pass_n": len(passed),
        "among_headline_n": sum(1 for row in passed if row["pair_id"] in headline_ids),
        "replaces_headline": False,
        "distribution": dist,
        "sign_flipped": sign_flipped(headline_median, dist.get("median")),
    }


def open_pnu(beopjungri, lot) -> str | None:
    """마스킹되지 않은 지번만 19자리 PNU로 연다. 열리지 않으면 확인 불가다."""
    text_lot = re.sub(r"\s+", "", str(lot or ""))
    if not text_lot or any(ch in text_lot for ch in "*＊xX"):
        return None
    matched = _LOT_RE.match(text_lot)
    if not matched:
        return None
    code = re.sub(r"\D", "", str(beopjungri or ""))
    if len(code) != 10:
        return None
    bun_raw = matched.group(2)
    ji_raw = matched.group(3) or "0"
    if len(bun_raw) > 4 or len(ji_raw) > 4:
        return None
    gbn = "2" if matched.group(1) else "1"
    return code + gbn + bun_raw.zfill(4) + ji_raw.zfill(4)


def classify_title_years(years: list[int], year_apt: int, year_off: int) -> str:
    """표제부 사용승인연도가 속성 연도와 1년 이내로 한 덩어리인지."""
    usable = [int(year) for year in years if year is not None]
    if not usable:
        return "no_title_year"
    cover = [year for year in usable if abs(year - year_apt) <= 1 or abs(year - year_off) <= 1]
    covers_apt = any(abs(year - year_apt) <= 1 for year in usable)
    covers_off = any(abs(year - year_off) <= 1 for year in usable)
    if not covers_apt or not covers_off:
        return "year_miss"
    if max(cover) - min(cover) <= 1:
        return "verified"
    return "ambiguous"


def _approve_year(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if hasattr(value, "year"):
        year = int(value.year)
        return year if 1900 <= year <= 2100 else None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) < 4:
        return None
    year = int(digits[:4])
    return year if 1900 <= year <= 2100 else None


def _purpose_class(texts: list[str]) -> str:
    blob = " ".join(text for text in texts if text)
    has_apt = "아파트" in blob
    has_off = "오피스텔" in blob
    if has_apt and has_off:
        return "both"
    if has_apt:
        return "apt_only"
    if has_off:
        return "off_only"
    return "neither"


def verify_headline_pairs(pairs: pd.DataFrame, headline_median=None) -> dict:
    """104곳만 대장과 대조한다. 확인 불가 짝은 본결과에서 빼지 않는다."""
    base = {
        "available": False,
        "n": int(len(pairs)),
        "note": "확인된 짝만 따로 센다. 확인 불가 짝은 본결과 104곳에 그대로 둔다. 용도 문구는 확인 조건이 아니다.",
    }
    if pairs.empty:
        base["reason"] = "비교 짝 없음"
        return base
    eng = get_parcel_engine()
    if eng is None:
        base["reason"] = "대장DB 연결 없음"
        return base
    prepared = []
    for row in pairs.itertuples(index=False):
        prepared.append(
            {
                "pnu": open_pnu(row.bj, row.lot),
                "year_apt": int(row.approved_year_apt),
                "year_off": int(row.approved_year_off),
                "ratio": None if pd.isna(row.ratio) else float(row.ratio),
            }
        )
    pnus = [row["pnu"] for row in prepared if row["pnu"]]
    try:
        parcel_pnus, titles, source = _load_titles(eng, pnus)
    except Exception as exc:  # noqa: BLE001 — 대장 조회 실패는 확인 불가로 적는다
        base["reason"] = exc.__class__.__name__
        return base
    base["source"] = source
    counts = {"lot_closed": 0, "no_parcel": 0, "no_title_year": 0, "year_miss": 0, "ambiguous": 0, "verified": 0}
    verified_ratios = []
    by_purpose: dict[str, list[float]] = {"both": [], "apt_only": [], "off_only": [], "neither": []}
    for row in prepared:
        pnu = row["pnu"]
        if pnu is None:
            counts["lot_closed"] += 1
            continue
        if pnu not in parcel_pnus and pnu not in titles:
            counts["no_parcel"] += 1
            continue
        info = titles.get(pnu, {"years": [], "purposes": []})
        label = classify_title_years(info["years"], row["year_apt"], row["year_off"])
        counts[label] += 1
        if label == "verified" and row["ratio"] is not None:
            verified_ratios.append(row["ratio"])
            by_purpose[_purpose_class(info["purposes"])].append(row["ratio"])
    dist = distribution(verified_ratios, min_n=CELL_MIN)
    not_both = by_purpose["apt_only"] + by_purpose["off_only"] + by_purpose["neither"]
    base.update(
        {
            "available": True,
            **counts,
            "verified_distribution": dist,
            "purpose_both_n": len(by_purpose["both"]),
            "purpose_split": {
                "both": distribution(by_purpose["both"], min_n=CELL_MIN),
                "not_both": distribution(not_both, min_n=CELL_MIN),
                "apt_only_n": len(by_purpose["apt_only"]),
                "off_only_n": len(by_purpose["off_only"]),
                "neither_n": len(by_purpose["neither"]),
            },
            "sign_flipped": sign_flipped(headline_median, dist.get("median")),
        }
    )
    return base


def _load_titles(eng, pnus: list[str]) -> tuple[set[str], dict, str]:
    if LEDGER_PATH.exists():
        return _load_titles_ledger(pnus)
    if not pnus:
        return set(), {}, "none"
    unique = list(dict.fromkeys(pnus))
    parcel_sql = "SELECT pnu FROM parcel WHERE pnu IN :keys"
    title_sql = """
        SELECT pnu, mgmt_pk, snapshot, main_purpose, purpose_detail, approve_date
        FROM building
        WHERE pnu IN :keys
    """
    with eng.connect() as conn:
        parcels = _read_in(conn, parcel_sql, {}, unique)
        titles = _read_in(conn, title_sql, {}, unique)
    parcel_pnus = set(parcels["pnu"].astype(str).str.strip()) if not parcels.empty else set()
    by_pnu: dict[str, dict] = {}
    if titles.empty:
        return parcel_pnus, by_pnu, "parcel_master"
    titles = titles.copy()
    titles["pnu"] = titles["pnu"].astype(str).str.strip()
    titles["mgmt_pk"] = titles["mgmt_pk"].astype(str)
    titles["snapshot"] = titles["snapshot"].astype(str)
    titles = titles.sort_values("snapshot", ascending=False).drop_duplicates("mgmt_pk")
    for pnu, group in titles.groupby("pnu", sort=False):
        years = []
        purposes = []
        for rec in group.itertuples(index=False):
            year = _approve_year(rec.approve_date)
            if year is not None:
                years.append(year)
            purposes.append(f"{rec.main_purpose or ''} {rec.purpose_detail or ''}")
        by_pnu[str(pnu)] = {"years": years, "purposes": purposes}
    return parcel_pnus, by_pnu, "parcel_master"


def _decode_cell(blob: bytes) -> str:
    for encoding in ("utf-8", "cp949"):
        try:
            return blob.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return blob.decode("cp949", "replace").strip()


def _load_titles_ledger(pnus: list[str]) -> tuple[set[str], dict, str]:
    import sqlite3

    unique = list(dict.fromkeys(pnus))
    if not unique:
        return set(), {}, "building_ledger_v1"
    uri = LEDGER_PATH.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        found = []
        for chunk in _chunks(unique, 80):
            marks = ",".join("?" * len(chunk))
            found.extend(
                conn.execute(
                    f"""
                    SELECT o.pnu, o.snapshot, o.pk, v.raw
                    FROM title_observation o
                    JOIN title_version v ON v.pk = o.pk AND v.raw_hash = o.raw_hash
                    WHERE o.pnu IN ({marks})
                    """,
                    chunk,
                ).fetchall()
            )
    finally:
        conn.close()
    latest: dict[tuple[str, str], bytes] = {}
    order: dict[tuple[str, str], str] = {}
    for pnu, snapshot, pk, raw in found:
        key = (str(pk), str(pnu))
        snap = str(snapshot)
        if key not in order or snap > order[key]:
            order[key] = snap
            latest[key] = raw if isinstance(raw, bytes) else bytes(raw)
    by_pnu: dict[str, dict] = {}
    parcel_pnus: set[str] = set()
    for (_pk, pnu), raw in latest.items():
        parcel_pnus.add(pnu)
        body = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
        parts = body.split(b"|")
        year = _approve_year(_decode_cell(parts[_TITLE_APPROVE]) if len(parts) > _TITLE_APPROVE else b"")
        purpose = ""
        if len(parts) > _TITLE_PURPOSE_DETAIL:
            purpose = _decode_cell(parts[_TITLE_PURPOSE]) + " " + _decode_cell(parts[_TITLE_PURPOSE_DETAIL])
        bucket = by_pnu.setdefault(pnu, {"years": [], "purposes": []})
        if year is not None:
            bucket["years"].append(year)
        bucket["purposes"].append(purpose)
    return parcel_pnus, by_pnu, "building_ledger_v1"


def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        if not math.isfinite(float(obj)):
            return None
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


def load_keys(conn, start, end) -> pd.DataFrame:
    frame = pd.read_sql(text(KEY_SQL), conn, params={"start": start, "end": end})
    if frame.empty:
        return frame
    frame["building_key"] = frame["building_key"].astype(str).str.strip()
    frame["n"] = frame["n"].astype(int)
    return frame


def load_attrs(conn, snap, keys: list[str]) -> pd.DataFrame:
    cols = ["building_key", "asset_type", "approved_year", "match_rule", "max_floor"]
    if not keys or snap is None:
        return pd.DataFrame(columns=cols)
    frame = _read_in(conn, ATTR_SQL, {"snap": snap}, keys)
    if frame.empty:
        return pd.DataFrame(columns=cols)
    frame["building_key"] = frame["building_key"].astype(str).str.strip()
    return frame.drop_duplicates(["building_key", "asset_type"])


def build_pair_table(keys: pd.DataFrame, attrs: pd.DataFrame) -> pd.DataFrame:
    if keys.empty:
        return pd.DataFrame()
    merged = keys.merge(attrs, on=["building_key", "asset_type"], how="left")
    nuniq = merged.groupby(["bj", "lot"], sort=False)["asset_type"].transform("nunique")
    mixed = merged[nuniq >= 2]
    rows = []
    for (bj, lot), group in mixed.groupby(["bj", "lot"], sort=False):
        apt = group[group["asset_type"] == "apartment"]
        off = group[group["asset_type"] == "officetel"]
        if apt.empty or off.empty:
            continue
        base = {
            "pair_id": f"{bj}|{lot}",
            "bj": bj,
            "lot": lot,
            "n_apt_keys": int(len(apt)),
            "n_off_keys": int(len(off)),
            "n_apt": int(apt["n"].sum()),
            "n_off": int(off["n"].sum()),
            "addr1": str(apt["addr1"].dropna().iloc[0]) if apt["addr1"].notna().any() else "",
            "addr2": str(apt["addr2"].dropna().iloc[0]) if apt["addr2"].notna().any() else "",
        }
        if len(apt) != 1 or len(off) != 1:
            base.update(
                {
                    "klass": "multi_key",
                    "apt_key": None,
                    "off_key": None,
                    "approved_year_apt": None,
                    "approved_year_off": None,
                    "kapt_same_pnu": False,
                    "max_floor_apt": None,
                    "max_floor_off": None,
                }
            )
            rows.append(base)
            continue
        a = apt.iloc[0]
        o = off.iloc[0]
        year_a = _year_or_none(a.get("approved_year"))
        year_o = _year_or_none(o.get("approved_year"))
        base.update(
            {
                "klass": classify_years(1, 1, year_a, year_o),
                "apt_key": str(a["building_key"]),
                "off_key": str(o["building_key"]),
                "approved_year_apt": year_a,
                "approved_year_off": year_o,
                "kapt_same_pnu": str(o.get("match_rule") or "") == KAPT_SAME_PNU,
                "max_floor_apt": _positive(a.get("max_floor")),
                "max_floor_off": _positive(o.get("max_floor")),
            }
        )
        rows.append(base)
    return pd.DataFrame(rows)


def _fill_traded_floors(pairs: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    if pairs.empty or trades.empty:
        return pairs
    traded = trades.groupby("building_key")["floor"].max()
    out = pairs.copy()
    for column, key_col in (("max_floor_apt", "apt_key"), ("max_floor_off", "off_key")):
        missing = out[column].isna()
        if missing.any():
            out.loc[missing, column] = out.loc[missing, key_col].map(traded)
    return out


def dong_name_counts(trades: pd.DataFrame, pairs: pd.DataFrame) -> dict:
    """동 이름이 양쪽 다 있을 때 겹치는지. 비어 있는 쪽은 다른 건물로 바꾸지 않는다."""
    empty = {"both_nonempty_n": 0, "disjoint_n": 0, "overlap_n": 0}
    if trades.empty or pairs.empty:
        return empty
    names = (
        trades.dropna(subset=["dong"])
        .groupby("building_key")["dong"]
        .agg(lambda s: set(str(v) for v in s if str(v).strip()))
        .to_dict()
    )
    both = disjoint = overlap = 0
    for row in pairs.itertuples(index=False):
        left = names.get(row.apt_key) or set()
        right = names.get(row.off_key) or set()
        if not left or not right:
            continue
        both += 1
        if left.isdisjoint(right):
            disjoint += 1
        else:
            overlap += 1
    return {"both_nonempty_n": both, "disjoint_n": disjoint, "overlap_n": overlap}


def area_overlap_n(trades: pd.DataFrame, pairs: pd.DataFrame) -> int:
    if trades.empty or pairs.empty:
        return 0
    med = trades.groupby("building_key")["area"].median()
    n = 0
    for row in pairs.itertuples(index=False):
        a = med.get(row.apt_key)
        o = med.get(row.off_key)
        if a is None or o is None or not math.isfinite(float(a)) or float(a) <= 0:
            continue
        ratio = float(o) / float(a)
        if AREA_PRIMARY[0] <= ratio <= AREA_PRIMARY[1]:
            n += 1
    return n


def stage1(pairs: pd.DataFrame, trades: pd.DataFrame, pass_n: int) -> dict:
    same = pairs[pairs["klass"] == "same_building"] if not pairs.empty else pairs
    return {
        "mixed_lot_n": int(len(pairs)),
        "same_building_n": int((pairs["klass"] == "same_building").sum()) if not pairs.empty else 0,
        "year_unknown_n": int((pairs["klass"] == "year_unknown").sum()) if not pairs.empty else 0,
        "different_building_n": int((pairs["klass"] == "different_building").sum()) if not pairs.empty else 0,
        "multi_key_n": int((pairs["klass"] == "multi_key").sum()) if not pairs.empty else 0,
        "same_building_trade_counts": {
            "apartment": _count_dist(same["n_apt"].astype(int).tolist()) if not same.empty else _count_dist([]),
            "officetel": _count_dist(same["n_off"].astype(int).tolist()) if not same.empty else _count_dist([]),
        },
        "exclusive_area": {
            "apartment": _area_span(trades.loc[trades["asset_type"] == "apartment", "area"]) if not trades.empty else _area_span(pd.Series(dtype=float)),
            "officetel": _area_span(trades.loc[trades["asset_type"] == "officetel", "area"]) if not trades.empty else _area_span(pd.Series(dtype=float)),
        },
        "area_median_within_15pct_n": area_overlap_n(trades, same),
        "dong": dong_name_counts(trades, same),
        "kapt_same_pnu_n": int(same["kapt_same_pnu"].sum()) if not same.empty else 0,
        "direct_pass_n": int(pass_n),
        "stop": bool(pass_n < STOP_MIN_PAIRS),
    }


def main() -> None:
    eng = get_collective_engine()
    if eng is None:
        raise SystemExit("COLLECTIVE_DATABASE_URL 없음")
    with eng.connect() as conn:
        as_of, _ = latest_mart_snapshot(conn)
        if as_of is None:
            raise SystemExit("collective_building_stats 스냅샷이 없습니다")
        start, end = period_bounds_for_window(as_of, WINDOW_YEARS)
        snap = conn.execute(text(f"SELECT MAX(snapshot_ym) FROM {ATTRIBUTES_TABLE}")).scalar()
        print(f"window {start} {end} as_of {as_of} snap {snap}", flush=True)
        keys = load_keys(conn, start, end)
        print(f"keys {len(keys)}", flush=True)
        if keys.empty:
            attr_keys: list[str] = []
        else:
            nuniq = keys.groupby(["bj", "lot"], sort=False)["asset_type"].transform("nunique")
            attr_keys = keys.loc[nuniq >= 2, "building_key"].astype(str).unique().tolist()
        attrs = load_attrs(conn, snap, attr_keys)
        print(f"attrs {len(attrs)}", flush=True)
        pairs = build_pair_table(keys, attrs)
        print(pairs["klass"].value_counts().to_dict() if not pairs.empty else {}, flush=True)
        same = pairs[pairs["klass"] == "same_building"] if not pairs.empty else pairs
        same_keys = []
        if not same.empty:
            same_keys = list(dict.fromkeys([*same["apt_key"].tolist(), *same["off_key"].tolist()]))
        trades = prepare_trades(_read_in(conn, TRADE_SQL, {"start": start, "end": end}, same_keys)) if same_keys else pd.DataFrame()
        print(f"same trades {len(trades)}", flush=True)
        trades = _fill_scope(trades, same)
        pairs = _fill_traded_floors(pairs, trades)
        same = pairs[pairs["klass"] == "same_building"] if not pairs.empty else pairs
        primary = evaluate_pairs(
            trades, same, area_lo=AREA_PRIMARY[0], area_hi=AREA_PRIMARY[1], time_col="year", floor_mode="band"
        ) if not same.empty else []
        pass_n = sum(1 for row in primary if row.get("ratio") is not None)
        funnel = stage1(pairs, trades, pass_n)
        print(f"pass {pass_n} stop {funnel['stop']}", flush=True)
        payload = {
            "status": "stopped_at_stage_1" if funnel["stop"] else "executed",
            "as_of": as_of.isoformat(),
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "window_years": WINDOW_YEARS,
            "attribute_snapshot": str(snap) if snap is not None else None,
            "thresholds": {
                "stop_min_pairs": STOP_MIN_PAIRS,
                "matched_min_each_side": MATCH_MIN,
                "side_min_trades": SIDE_MIN,
                "regression_min_trades": REG_TOTAL_MIN,
                "cell_min_pairs": CELL_MIN,
                "area_ratio": list(AREA_PRIMARY),
                "reuse_median_over": REUSE_MEDIAN_MAX,
            },
            "notes": [
                "짝은 법정동·리 코드와 지번이다. 건물 키는 유형을 포함하므로 같은 주소가 두 키가 된다.",
                "사용승인연도는 단지 속성 최신 스냅샷의 approved_year다. 거래의 건축년도로 짝을 나누지 않았다.",
                "건축물대장 관리번호는 거래 행에 없어 1차에서 붙이지 않았다.",
                "해제 거래는 is_valid에서 빠져 있다. 거래구분은 중개·직거래만 남겼다.",
                "동 이름이 어긋나도 다른 건물로 다시 분류하지 않는다.",
                "kapt_same_pnu 오피스텔은 가격이 있으면 표본에 남긴다. 세대수로 가중하지 않는다.",
                "비율은 전용면적 ㎡당 실거래가다. 감정평가 할인율이 아니고, 법적 용도만의 차이로 읽지 않는다.",
                "후속 확인(면적 0.90–1.10과 92일, 대장 대조)은 본결과 분포를 바꾸지 않는다.",
                "건물 안 회귀가 통제한 것은 전용면적, 키 안 층 대역, 계약연도다. 사용승인연도는 이미 1년 이내라 그 식의 변수가 아니다.",
            ],
            "stage1": funnel,
        }
        if not funnel["stop"]:
            report = build_same_building_report(same, trades, end.year, primary)
            ratio_by_id = {row["pair_id"]: row["ratio"] for row in primary if row.get("ratio") is not None}
            headline_pairs = same[same["pair_id"].isin(ratio_by_id)].copy()
            headline_pairs["ratio"] = headline_pairs["pair_id"].map(ratio_by_id)
            report["register"] = verify_headline_pairs(
                headline_pairs, report["direct"]["distribution"].get("median")
            )
            print(
                "followup",
                report["followup"]["strict_90_92d"]["pass_n"],
                "register",
                report["register"].get("verified"),
                report["register"].get("reason"),
                flush=True,
            )
            different = pairs[pairs["klass"] == "different_building"]
            diff_keys = []
            if not different.empty:
                diff_keys = list(dict.fromkeys([*different["apt_key"].dropna().tolist(), *different["off_key"].dropna().tolist()]))
            diff_trades = prepare_trades(_read_in(conn, TRADE_SQL, {"start": start, "end": end}, diff_keys)) if diff_keys else pd.DataFrame()
            diff_rows = evaluate_pairs(
                diff_trades,
                different,
                area_lo=AREA_PRIMARY[0],
                area_hi=AREA_PRIMARY[1],
                time_col="year",
                floor_mode="band",
            ) if not different.empty else []
            payload["same_building"] = report
            payload["different_building"] = {
                "note": "같은 지번이고 사용승인연도 차이가 2년 이상. 동일 건물 분포와 합치지 않는다.",
                "direct": _headline(diff_rows),
            }
        else:
            payload["same_building"] = None
            payload["different_building"] = None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(_clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(OUT), "status": payload["status"], "pass": pass_n}, ensure_ascii=False), flush=True)


def _fill_scope(trades: pd.DataFrame, same: pd.DataFrame) -> pd.DataFrame:
    """거래에 짝 주소를 확인만 한다. 다른 지번으로 새지 않게 키와 지번이 맞는 행만 남긴다."""
    if trades.empty or same.empty:
        return trades
    allowed = set(zip(same["apt_key"], same["bj"], same["lot"])) | set(zip(same["off_key"], same["bj"], same["lot"]))
    mask = [(key, bj, lot) in allowed for key, bj, lot in zip(trades["building_key"], trades["bj"], trades["lot"])]
    return trades.loc[mask].copy()


if __name__ == "__main__":
    main()
