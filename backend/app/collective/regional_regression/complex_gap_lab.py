# -*- coding: utf-8 -*-
"""아파트 단지 격차와 면적 기울기. 제품 회귀 식은 읽기만 한다.

계획: docs/lab/COLLECTIVE_COMPLEX_GAP_LAB.md
결과: docs/lab/collective_complex_gap_pilot.json

반복 지역은 거래수와 건축연도만으로 고른다. 가격 계수는 선정에 쓰지 않는다.
"""

from __future__ import annotations

import json
import math
from datetime import date

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import bindparam, text

from app.collective.building_stats_query import latest_mart_snapshot
from app.collective.danji_attributes import ATTRIBUTES_TABLE
from app.collective.db import get_collective_engine
from app.collective.regression.engine import relative_floor_group
from app.v2_stats_windows import period_bounds_for_window

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs" / "lab" / "collective_complex_gap_pilot.json"
SEED = 20261104
MIN_N = 30
SLOPE_N = 40
AREA_SPREAD = 1.5
COVERAGE = 0.70
FOLDS = 5
METRO = ("부산", "대구", "인천", "대전", "울산")
DONG_SQL = """
CASE
  WHEN right(btrim(coalesce(addr4, '')), 1) IN ('동', '읍', '면') THEN btrim(addr4)
  WHEN right(btrim(coalesce(addr3, '')), 1) IN ('동', '읍', '면', '가') THEN btrim(addr3)
  ELSE NULLIF(btrim(coalesce(addr4, addr3, '')), '')
END
"""


def _r(value, ndigits: int = 1):
    if value is None or not isinstance(value, (int, float, np.floating)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, ndigits)


def stratum_of(sido: str, place: str) -> str:
    if str(sido).startswith("서울"):
        return "서울"
    if any(str(sido).startswith(name) for name in METRO):
        return "광역시"
    last = str(place).split()[-1] if place else ""
    if str(sido).startswith("전남광주") and last.endswith("구"):
        return "광역시"
    if last.endswith("군"):
        return "군"
    return "시"


def _flags(raw) -> set[str]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return set()
    return {part.strip() for part in str(raw).split(",") if part.strip()}


def load_complex_counts(conn, start: date, end: date) -> pd.DataFrame:
    frame = pd.read_sql(
        text(
            f"""
            SELECT addr1, addr2, {DONG_SQL} AS dong, building_key,
                   MAX(display_name) AS display_name,
                   COUNT(*)::int AS n_raw,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price) AS unit_median,
                   AVG(unit_price)::float AS unit_mean,
                   MODE() WITHIN GROUP (ORDER BY building_year) AS building_year
            FROM collective_transactions
            WHERE is_valid = true
              AND asset_type = 'apartment'
              AND contract_date BETWEEN :start AND :end
              AND price > 0
              AND exclusive_area > 0
              AND unit_price > 0
            GROUP BY addr1, addr2, {DONG_SQL}, building_key
            """
        ),
        conn,
        params={"start": start, "end": end},
    )
    frame["building_key"] = frame["building_key"].astype(str).str.strip()
    frame["building_year"] = pd.to_numeric(frame["building_year"], errors="coerce")
    frame["n_raw"] = pd.to_numeric(frame["n_raw"], errors="coerce").fillna(0).astype(int)
    return frame


def choose_repeat(counts: pd.DataFrame, as_of_year: int) -> tuple[pd.DataFrame, dict]:
    """가격을 보지 않는다. 건수와 건축연도만 쓴다."""
    work = counts.dropna(subset=["dong"]).copy()
    work = work[work["dong"].astype(str).str.len() > 0]
    big = work[work["n_raw"] >= MIN_N].copy()
    big["age"] = as_of_year - big["building_year"]
    rows = []
    for key, grp in big.groupby(["addr1", "addr2", "dong"], dropna=False):
        addr1, addr2, dong = key
        if dong == "금정동" and str(addr1).startswith("경기") and "군포" in str(addr2):
            continue
        if len(grp) < 4:
            continue
        young = int((grp["age"] <= 5).sum())
        old = int((grp["age"] >= 20).sum())
        if young < 1 or old < 1:
            continue
        place = str(addr2)
        rows.append(
            {
                "addr1": addr1,
                "addr2": addr2,
                "dong": dong,
                "stratum": stratum_of(str(addr1), place),
                "n_complex": int(len(grp)),
                "n_tx": int(work[(work.addr1 == addr1) & (work.addr2 == addr2) & (work.dong == dong)]["n_raw"].sum()),
                "n_young": young,
                "n_old": old,
            }
        )
    cand = pd.DataFrame(rows)
    shortfall = {}
    picked = []
    if cand.empty:
        return pd.DataFrame(columns=["addr1", "addr2", "dong", "stratum"]), {"서울": 3, "광역시": 3, "시": 3, "군": 3}
    for name in ("서울", "광역시", "시", "군"):
        block = cand[cand["stratum"] == name].sort_values(["n_tx", "dong"], ascending=[False, True])
        take = block.head(3)
        shortfall[name] = int(3 - len(take))
        picked.append(take)
    out = pd.concat(picked, ignore_index=True) if picked else cand.iloc[0:0]
    return out, shortfall


def load_trades(conn, places: list[tuple[str, str, str]], start: date, end: date) -> pd.DataFrame:
    if not places:
        return pd.DataFrame()
    clauses = []
    params: dict = {"start": start, "end": end}
    for i, (addr1, addr2, dong) in enumerate(places):
        clauses.append(f"(addr1 = :a1_{i} AND addr2 = :a2_{i} AND ({DONG_SQL}) = :dong_{i})")
        params[f"a1_{i}"] = addr1
        params[f"a2_{i}"] = addr2
        params[f"dong_{i}"] = dong
    frame = pd.read_sql(
        text(
            f"""
            SELECT id, building_key, display_name, addr1, addr2,
                   {DONG_SQL} AS dong,
                   contract_year, building_year, exclusive_area, price, unit_price, floor
            FROM collective_transactions
            WHERE is_valid = true
              AND asset_type = 'apartment'
              AND contract_date BETWEEN :start AND :end
              AND price > 0
              AND exclusive_area > 0
              AND ({' OR '.join(clauses)})
            """
        ),
        conn,
        params=params,
    )
    frame["building_key"] = frame["building_key"].astype(str).str.strip()
    for col in ("contract_year", "building_year", "exclusive_area", "price", "unit_price", "floor"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def load_attributes(conn, keys: list[str], snap: str | None) -> pd.DataFrame:
    if not keys or not snap:
        return pd.DataFrame(columns=["building_key", "households", "parking_per_household", "assessed_land_price"])
    exists = conn.execute(
        text("SELECT to_regclass('public.collective_building_assessed_land_price')")
    ).scalar()
    price_sql = "lp.assessed_land_price" if exists else "NULL::numeric AS assessed_land_price"
    join_sql = (
        """
        LEFT JOIN collective_building_assessed_land_price lp
          ON lp.building_key = a.building_key
         AND lp.asset_type = a.asset_type
        """
        if exists
        else ""
    )
    stmt = text(
        f"""
        SELECT a.building_key, a.households, a.parking_per_household, a.attr_quality_flags,
               {price_sql}
        FROM {ATTRIBUTES_TABLE} a
        {join_sql}
        WHERE a.asset_type = 'apartment'
          AND a.snapshot_ym = :snap
          AND a.building_key IN :keys
        """
    ).bindparams(bindparam("keys", expanding=True))
    rows = conn.execute(stmt, {"snap": snap, "keys": list(keys)}).mappings().all()
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["building_key"] = frame["building_key"].astype(str).str.strip()
    return frame


def apply_attribute_flags(attrs: pd.DataFrame) -> pd.DataFrame:
    if attrs.empty:
        return attrs
    out = attrs.copy()
    for col in ("households", "parking_per_household", "assessed_land_price"):
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    flags = out.get("attr_quality_flags", pd.Series([None] * len(out))).map(_flags)
    out.loc[flags.map(lambda s: "hh_zero" in s or "scale_inconsistent" in s), "households"] = np.nan
    out.loc[flags.map(lambda s: "parking_implausible" in s), "parking_per_household"] = np.nan
    out.loc[out["households"] <= 0, "households"] = np.nan
    out.loc[out["parking_per_household"] < 0, "parking_per_household"] = np.nan
    out.loc[out["assessed_land_price"] <= 0, "assessed_land_price"] = np.nan
    return out.drop_duplicates("building_key")


def prepare(trades: pd.DataFrame, attrs: pd.DataFrame) -> pd.DataFrame:
    work = trades.copy()
    work["age"] = work["contract_year"] - work["building_year"]
    work.loc[(work["age"] < 0) | (work["age"] > 80), "age"] = np.nan
    max_floor = work.groupby("building_key")["floor"].transform("max")
    codes = []
    for floor, mx in zip(work["floor"], max_floor):
        if pd.isna(floor) or pd.isna(mx):
            codes.append(None)
        else:
            codes.append(relative_floor_group(float(floor), float(mx)))
    work["floor_code"] = codes
    work["ln_area"] = np.log(work["exclusive_area"].astype(float))
    work["ln_price"] = np.log(work["price"].astype(float))
    if not attrs.empty:
        work = work.merge(
            attrs[["building_key", "households", "parking_per_household", "assessed_land_price"]],
            on="building_key",
            how="left",
        )
    else:
        work["households"] = np.nan
        work["parking_per_household"] = np.nan
        work["assessed_land_price"] = np.nan
    return work


def core_mask(work: pd.DataFrame) -> pd.Series:
    return (
        work["ln_area"].notna()
        & np.isfinite(work["ln_area"])
        & work["ln_price"].notna()
        & work["age"].notna()
        & work["floor_code"].notna()
        & work["contract_year"].notna()
    )


def label_of(display_name, building_year) -> str:
    name = str(display_name or "").strip() or "이름없음"
    if pd.notna(building_year):
        return f"{name} ({int(float(building_year))})"
    return name


def design_matrix(
    frame: pd.DataFrame,
    *,
    age: bool,
    fe_keys: list[str] | None,
    ref_key: str | None,
    c_cols: list[str],
    slope_keys: list[str] | None,
    quadratic: bool,
    year_omit: int,
    floor_omit: str,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    parts = [pd.Series(1.0, index=frame.index, name="const"), frame["ln_area"].astype(float).rename("ln_area")]
    if quadratic:
        parts.append((frame["ln_area"].astype(float) ** 2).rename("ln_area_sq"))
    if age:
        parts.append(frame["age"].astype(float).rename("age"))
    floors = sorted(set(frame["floor_code"].astype(str)) - {floor_omit})
    for code in floors:
        parts.append((frame["floor_code"].astype(str) == code).astype(float).rename(f"fl_{code}"))
    years = sorted(int(y) for y in frame["contract_year"].dropna().unique() if int(y) != year_omit)
    for year in years:
        parts.append((frame["contract_year"].astype(int) == year).astype(float).rename(f"yr_{year}"))
    if fe_keys and ref_key is not None:
        for key in fe_keys:
            if key == ref_key:
                continue
            parts.append((frame["building_key"].astype(str) == key).astype(float).rename(f"fe_{key}"))
    for col in c_cols:
        parts.append(frame[col].astype(float).rename(col))
    if slope_keys:
        base = slope_keys[0]
        for key in slope_keys:
            if key == base:
                continue
            parts.append(
                ((frame["building_key"].astype(str) == key).astype(float) * frame["ln_area"].astype(float)).rename(
                    f"sl_{key}"
                )
            )
    matrix = pd.concat(parts, axis=1)
    if columns is not None:
        return matrix.reindex(columns=columns, fill_value=0.0).fillna(0.0)
    keep = [col for col in matrix.columns if col == "const" or float(matrix[col].std(ddof=0) or 0) > 0]
    return matrix[keep]


def hat_diag(x_values: np.ndarray) -> np.ndarray:
    q, _ = np.linalg.qr(x_values, mode="reduced")
    return np.sum(q * q, axis=1)


def fit_ols(y: np.ndarray, matrix: pd.DataFrame):
    model = sm.OLS(y, matrix.to_numpy(dtype=float), missing="drop")
    names = list(matrix.columns)
    result = model.fit()
    leverage = hat_diag(matrix.to_numpy(dtype=float))
    cov = "HC1" if np.any(leverage >= 0.99) else "HC3"
    robust = model.fit(cov_type=cov)
    return result, robust, names, cov


def mape_from_log(y_log: np.ndarray, pred_log: np.ndarray) -> float | None:
    actual = np.exp(y_log)
    pred = np.exp(pred_log)
    ok = np.isfinite(actual) & np.isfinite(pred) & (actual > 0) & (pred > 0)
    if not ok.any():
        return None
    return float(np.mean(np.abs(pred[ok] - actual[ok]) / actual[ok]) * 100)


def r2_log(y_log: np.ndarray, pred_log: np.ndarray) -> float | None:
    ok = np.isfinite(y_log) & np.isfinite(pred_log)
    if ok.sum() < 3:
        return None
    resid = y_log[ok] - pred_log[ok]
    total = y_log[ok] - np.mean(y_log[ok])
    denom = float(np.sum(total ** 2))
    if denom <= 0:
        return None
    return float(1 - np.sum(resid ** 2) / denom)


def cv_known(frame: pd.DataFrame, spec: dict) -> dict:
    rng = np.random.default_rng(SEED)
    fold = pd.Series(-1, index=frame.index, dtype=int)
    for _, idx in frame.groupby("building_key").groups.items():
        order = np.array(list(idx))
        rng.shuffle(order)
        fold.loc[order] = np.arange(len(order)) % FOLDS
    y_parts = []
    p_parts = []
    for k in range(FOLDS):
        train = frame.loc[fold != k]
        test = frame.loc[fold == k]
        if len(train) < 20 or test.empty:
            continue
        matrix = design_matrix(train, **spec)
        if "ln_area" not in matrix.columns or len(matrix) <= matrix.shape[1] + 2:
            continue
        fitted = sm.OLS(train["ln_price"].to_numpy(dtype=float), matrix.to_numpy(dtype=float)).fit()
        pred = fitted.predict(design_matrix(test, columns=list(matrix.columns), **spec).to_numpy(dtype=float))
        y_parts.append(test["ln_price"].to_numpy(dtype=float))
        p_parts.append(np.asarray(pred, dtype=float))
    if not y_parts:
        return {"mape": None, "n": 0}
    y_all = np.concatenate(y_parts)
    p_all = np.concatenate(p_parts)
    return {"mape": _r(mape_from_log(y_all, p_all), 2), "n": int(len(y_all)), "r2_oof": _r(r2_log(y_all, p_all), 3)}


def cv_held_complex(frame: pd.DataFrame, spec: dict) -> dict:
    y_parts = []
    p_parts = []
    keys = list(frame.groupby("building_key").size().sort_values(ascending=False).index)
    for key in keys:
        train = frame.loc[frame["building_key"] != key]
        test = frame.loc[frame["building_key"] == key]
        if len(train) < 20 or test.empty:
            continue
        use = dict(spec)
        if use.get("fe_keys"):
            continue
        matrix = design_matrix(train, **use)
        if "ln_area" not in matrix.columns or len(matrix) <= matrix.shape[1] + 2:
            continue
        fitted = sm.OLS(train["ln_price"].to_numpy(dtype=float), matrix.to_numpy(dtype=float)).fit()
        pred = fitted.predict(design_matrix(test, columns=list(matrix.columns), **use).to_numpy(dtype=float))
        y_parts.append(test["ln_price"].to_numpy(dtype=float))
        p_parts.append(np.asarray(pred, dtype=float))
    if not y_parts:
        return {"mape": None, "n": 0}
    y_all = np.concatenate(y_parts)
    p_all = np.concatenate(p_parts)
    return {"mape": _r(mape_from_log(y_all, p_all), 2), "n": int(len(y_all))}


def full_fit(frame: pd.DataFrame, spec: dict) -> dict:
    matrix = design_matrix(frame, **spec)
    y = frame["ln_price"].to_numpy(dtype=float)
    point, robust, names, cov = fit_ols(y, matrix)
    pred = np.asarray(point.predict(matrix.to_numpy(dtype=float)), dtype=float)
    frame = frame.copy()
    frame["_pred_log"] = pred
    params = {name: float(value) for name, value in zip(names, robust.params)}
    ses = {name: float(value) for name, value in zip(names, robust.bse)}
    return {
        "params": params,
        "se": ses,
        "cov": cov,
        "n": int(len(frame)),
        "k": int(matrix.shape[1]),
        "r2_log": _r(r2_log(y, pred), 3),
        "mape_in": _r(mape_from_log(y, pred), 2),
        "pred_log": pred,
        "index": frame.index,
    }


def coef_row(fit: dict, name: str) -> dict | None:
    if name not in fit["params"]:
        return None
    est = fit["params"][name]
    se = fit["se"].get(name)
    return {"estimate": _r(est, 4), "se": _r(se, 4), "cov": fit["cov"]}


def analyze_place(raw: pd.DataFrame, as_of_year: int, iqr: bool) -> dict:
    work = raw.copy()
    ready = work.loc[core_mask(work)].copy()
    counts = ready.groupby("building_key").size()
    keep_keys = set(counts[counts >= MIN_N].index.astype(str))
    ready = ready.loc[ready["building_key"].astype(str).isin(keep_keys)].copy()
    if iqr and len(ready) >= 4:
        unit = ready["unit_price"].astype(float)
        q1, q3 = unit.quantile(0.25), unit.quantile(0.75)
        span = q3 - q1
        lo, hi = q1 - 1.5 * span, q3 + 1.5 * span
        ready = ready.loc[(unit >= lo) & (unit <= hi)].copy()
        counts = ready.groupby("building_key").size()
        keep_keys = set(counts[counts >= MIN_N].index.astype(str))
        ready = ready.loc[ready["building_key"].astype(str).isin(keep_keys)].copy()
    if ready["building_key"].nunique() < 2 or len(ready) < MIN_N:
        return {"ok": False, "reason": "분석 단지가 2곳 미만"}

    sizes = ready.groupby("building_key").size().sort_values(ascending=False)
    ref_key = str(sizes.index[0])
    fe_keys = [str(key) for key in sizes.index]
    year_omit = int(ready["contract_year"].min())
    floor_omit = "floor_rel_mid" if (ready["floor_code"] == "floor_rel_mid").any() else str(ready["floor_code"].mode().iloc[0])
    names = (
        ready.groupby("building_key")
        .agg(display_name=("display_name", "first"), building_year=("building_year", "median"), n=("price", "size"))
        .reset_index()
    )
    name_map = {
        str(row.building_key): label_of(row.display_name, row.building_year) for row in names.itertuples(index=False)
    }

    c_candidates = ["households", "parking_per_household", "assessed_land_price"]
    c_cols = []
    dropped_c = []
    for col in c_candidates:
        filled = ready.groupby("building_key")[col].apply(lambda s: bool(s.notna().any()))
        share = float(filled.mean()) if len(filled) else 0.0
        if share >= COVERAGE:
            c_cols.append(col)
        else:
            dropped_c.append({"variable": col, "complex_share": _r(share, 3)})
    both = ready.dropna(subset=c_cols).copy() if c_cols else ready.iloc[0:0].copy()

    def spec_a():
        return dict(age=True, fe_keys=None, ref_key=None, c_cols=[], slope_keys=None, quadratic=False, year_omit=year_omit, floor_omit=floor_omit)

    def spec_b():
        return dict(age=False, fe_keys=fe_keys, ref_key=ref_key, c_cols=[], slope_keys=None, quadratic=False, year_omit=year_omit, floor_omit=floor_omit)

    def spec_c(cols):
        return dict(age=True, fe_keys=None, ref_key=None, c_cols=cols, slope_keys=None, quadratic=False, year_omit=year_omit, floor_omit=floor_omit)

    known_a = cv_known(ready, spec_a())
    known_b = cv_known(ready, spec_b())
    fit_a = full_fit(ready, spec_a())
    fit_b = full_fit(ready, spec_b())
    known_c = held_a = held_c = fit_c = None
    known_a_c = known_b_c = None
    if c_cols and len(both) >= MIN_N and both["building_key"].nunique() >= 2:
        known_a_c = cv_known(both, spec_a())
        known_b_c = cv_known(both, spec_b())
        known_c = cv_known(both, spec_c(c_cols))
        held_a = cv_held_complex(both, spec_a())
        held_c = cv_held_complex(both, spec_c(c_cols))
        fit_c = full_fit(both, spec_c(c_cols))
    held_a_full = cv_held_complex(ready, spec_a())

    gamma = coef_row(fit_a, "ln_area")
    beta = None
    if gamma and gamma["estimate"] is not None:
        beta = {"estimate": _r(gamma["estimate"] - 1, 4), "se": gamma["se"], "cov": gamma["cov"]}

    size_map = {str(k): int(v) for k, v in sizes.items()}
    fe_rows = []
    for key in fe_keys:
        if key == ref_key:
            pct = 0.0
            se = None
        else:
            row = coef_row(fit_b, f"fe_{key}")
            if row is None or row["estimate"] is None:
                continue
            pct = 100 * (math.exp(row["estimate"]) - 1)
            se = row["se"]
        fe_rows.append(
            {
                "complex": name_map.get(key, "단지"),
                "n": size_map.get(key, 0),
                "pct_vs_ref": _r(pct, 1),
                "log_se": _r(se, 4) if se is not None else None,
                "reference": key == ref_key,
            }
        )
    ready = ready.copy()
    ready["_gap"] = ready["ln_price"].to_numpy(dtype=float) - fit_a["pred_log"]
    gap_mean = ready.groupby("building_key")["_gap"].mean()
    ref_gap = float(gap_mean.get(ref_key, 0.0))
    gap_rows = []
    for key in fe_keys:
        gap = float(gap_mean.get(key, np.nan))
        if not math.isfinite(gap):
            continue
        gap_rows.append(
            {
                "complex": name_map.get(key, "단지"),
                "n": size_map.get(key, 0),
                "pct_vs_ref": _r(100 * (math.exp(gap - ref_gap) - 1), 1),
                "reference": key == ref_key,
            }
        )
    gap_pcts = [row["pct_vs_ref"] for row in gap_rows if row["pct_vs_ref"] is not None]
    gap_summary = {
        "reference": name_map.get(ref_key, "기준"),
        "min": _r(min(gap_pcts), 1) if gap_pcts else None,
        "p25": _r(float(np.percentile(gap_pcts, 25)), 1) if gap_pcts else None,
        "p75": _r(float(np.percentile(gap_pcts, 75)), 1) if gap_pcts else None,
        "max": _r(max(gap_pcts), 1) if gap_pcts else None,
        "note": "모형 A의 로그 잔차 평균. 면적·층·연식·시점을 뺀 뒤 기준 단지 대비.",
    }
    pcts = [row["pct_vs_ref"] for row in fe_rows if row["pct_vs_ref"] is not None]
    fe_summary = {
        "reference": name_map.get(ref_key, "기준"),
        "n_complex": len(fe_rows),
        "min": _r(min(pcts), 1) if pcts else None,
        "p25": _r(float(np.percentile(pcts, 25)), 1) if pcts else None,
        "p75": _r(float(np.percentile(pcts, 75)), 1) if pcts else None,
        "max": _r(max(pcts), 1) if pcts else None,
        "age_dropped": True,
    }

    slope_keys = []
    for key, grp in ready.groupby("building_key"):
        if len(grp) < SLOPE_N:
            continue
        area = grp["exclusive_area"].astype(float)
        p10, p90 = float(area.quantile(0.1)), float(area.quantile(0.9))
        if p10 > 0 and p90 / p10 >= AREA_SPREAD:
            slope_keys.append(str(key))
    slope_rows = []
    if len(slope_keys) >= 2:
        slope_spec = dict(
            age=False,
            fe_keys=fe_keys,
            ref_key=ref_key,
            c_cols=[],
            slope_keys=slope_keys,
            quadratic=False,
            year_omit=year_omit,
            floor_omit=floor_omit,
        )
        fit_s = full_fit(ready, slope_spec)
        base = slope_keys[0]
        base_g = fit_s["params"].get("ln_area")
        year_map = {str(row.building_key): row.building_year for row in names.itertuples(index=False)}
        for key in slope_keys:
            if base_g is None:
                break
            extra = 0.0 if key == base else fit_s["params"].get(f"sl_{key}")
            if extra is None:
                continue
            gamma_c = base_g + extra
            beta_c = gamma_c - 1
            year = year_map.get(key)
            age = as_of_year - float(year) if pd.notna(year) else None
            slope_rows.append(
                {
                    "complex": name_map.get(key, "단지"),
                    "beta": _r(beta_c, 3),
                    "age": _r(age, 1) if age is not None else None,
                    "band": "5년이하" if age is not None and age <= 5 else ("20년이상" if age is not None and age >= 20 else "그사이"),
                }
            )
    betas = [row["beta"] for row in slope_rows if row["beta"] is not None]
    def band_median(band: str):
        vals = [row["beta"] for row in slope_rows if row["band"] == band and row["beta"] is not None]
        return _r(float(np.median(vals)), 3) if vals else None

    quad = None
    if len(ready) > 30:
        qspec = spec_a()
        qspec["quadratic"] = True
        known_q = cv_known(ready, qspec)
        fit_q = full_fit(ready, qspec)
        quad = {
            "known_mape": known_q["mape"],
            "ln_area_sq": coef_row(fit_q, "ln_area_sq"),
            "known_mape_A": known_a["mape"],
        }

    return {
        "ok": True,
        "n_trades": int(len(ready)),
        "n_complex": int(ready["building_key"].nunique()),
        "known": {"A": known_a, "B": known_b, "C": known_c, "A_on_C_sample": known_a_c, "B_on_C_sample": known_b_c},
        "heldout_complex": {"A": held_a_full, "A_on_C_sample": held_a, "C": held_c, "B": None},
        "insample": {
            "A": {"r2_log": fit_a["r2_log"], "mape": fit_a["mape_in"], "n": fit_a["n"], "k": fit_a["k"], "cov": fit_a["cov"]},
            "B": {"r2_log": fit_b["r2_log"], "mape": fit_b["mape_in"], "n": fit_b["n"], "k": fit_b["k"], "cov": fit_b["cov"]},
            "C": None
            if fit_c is None
            else {"r2_log": fit_c["r2_log"], "mape": fit_c["mape_in"], "n": fit_c["n"], "k": fit_c["k"], "cov": fit_c["cov"]},
        },
        "gamma_ln_area": gamma,
        "beta_unit": beta,
        "c_kept": c_cols,
        "c_dropped": dropped_c,
        "c_sample_n": int(len(both)),
        "fe": fe_summary,
        "fe_complexes": fe_rows,
        "gap_after_a": gap_summary,
        "gap_after_a_complexes": gap_rows,
        "slopes": {
            "n_eligible": len(slope_rows),
            "median": _r(float(np.median(betas)), 3) if betas else None,
            "p25": _r(float(np.percentile(betas, 25)), 3) if betas else None,
            "p75": _r(float(np.percentile(betas, 75)), 3) if betas else None,
            "share_negative": _r(float(np.mean([b < 0 for b in betas])), 3) if betas else None,
            "median_age_le_5": band_median("5년이하"),
            "median_age_ge_20": band_median("20년이상"),
            "complexes": slope_rows,
        },
        "quadratic": quad,
        "name_map_ref": name_map.get(ref_key),
    }


def complex_catalog(counts: pd.DataFrame, place: tuple[str, str, str], as_of_year: int) -> list[dict]:
    addr1, addr2, dong = place
    block = counts[(counts.addr1 == addr1) & (counts.addr2 == addr2) & (counts.dong == dong)].sort_values("n_raw", ascending=False)
    rows = []
    for row in block.itertuples(index=False):
        year = None if pd.isna(row.building_year) else int(row.building_year)
        age = None if year is None else as_of_year - year
        rows.append(
            {
                "complex": label_of(row.display_name, row.building_year),
                "n": int(row.n_raw),
                "unit_median": _r(row.unit_median, 1),
                "unit_mean": _r(row.unit_mean, 1),
                "building_year": year,
                "age": age,
                "enters": int(row.n_raw) >= MIN_N,
            }
        )
    return rows


def place_payload(catalog: list[dict], result: dict) -> dict:
    entered = [row for row in catalog if row["enters"]]
    held = [row for row in catalog if not row["enters"]]
    return {
        "n_complex_raw": len(catalog),
        "n_complex_entered": len(entered),
        "n_complex_below_30": len(held),
        "entered": entered,
        "analysis": {k: v for k, v in result.items() if k != "ok"},
    }


def summarize_repeats(places: list[dict]) -> dict:
    def col(path):
        vals = []
        for place in places:
            cur = place["analysis"]
            for key in path:
                if cur is None:
                    break
                cur = cur.get(key) if isinstance(cur, dict) else None
            if isinstance(cur, (int, float)) and math.isfinite(float(cur)):
                vals.append(float(cur))
        return vals

    def med(vals):
        return _r(float(np.median(vals)), 3) if vals else None

    a = col(["known", "A", "mape"])
    b = col(["known", "B", "mape"])
    c = col(["known", "C", "mape"])
    beta = col(["beta_unit", "estimate"])
    drop = []
    for aa, bb in zip(a, b):
        drop.append(aa - bb)
    return {
        "n_places": len(places),
        "median_mape_A": med(a),
        "median_mape_B": med(b),
        "median_mape_A_on_C": med(col(["known", "A_on_C_sample", "mape"])),
        "median_mape_B_on_C": med(col(["known", "B_on_C_sample", "mape"])),
        "median_mape_C": med(c),
        "median_A_minus_B": med(drop),
        "median_beta": med(beta),
        "share_beta_negative": _r(float(np.mean([v < 0 for v in beta])), 3) if beta else None,
        "median_slope_share_negative": med(col(["slopes", "share_negative"])),
        "median_fe_min": med(col(["fe", "min"])),
        "median_fe_max": med(col(["fe", "max"])),
    }


def main() -> None:
    eng = get_collective_engine()
    if eng is None:
        raise SystemExit("COLLECTIVE_DATABASE_URL 없음")
    with eng.connect() as conn:
        as_of, _ = latest_mart_snapshot(conn)
        if as_of is None:
            raise SystemExit("collective_building_stats 스냅샷이 없습니다")
        start, end = period_bounds_for_window(as_of, 5)
        snap = conn.execute(text(f"SELECT MAX(snapshot_ym) FROM {ATTRIBUTES_TABLE}")).scalar()
        snap = str(snap) if snap else None
        counts = load_complex_counts(conn, start, end)
        repeat, shortfall = choose_repeat(counts, as_of.year)
        pilot_rows = counts[(counts.dong == "금정동") & counts.addr1.astype(str).str.startswith("경기") & counts.addr2.astype(str).str.contains("군포")]
        if pilot_rows.empty:
            raise SystemExit("군포시 금정동 아파트 거래가 없습니다")
        pilot_place = (str(pilot_rows.iloc[0].addr1), str(pilot_rows.iloc[0].addr2), "금정동")
        places = [pilot_place] + list(zip(repeat.addr1, repeat.addr2, repeat.dong))
        trades = load_trades(conn, places, start, end)
        attrs = apply_attribute_flags(load_attributes(conn, trades["building_key"].astype(str).unique().tolist(), snap))
    prepared = prepare(trades, attrs)
    pilot_cat = complex_catalog(counts, pilot_place, as_of.year)
    pilot_raw = prepared[(prepared.addr1 == pilot_place[0]) & (prepared.addr2 == pilot_place[1]) & (prepared.dong == "금정동")]
    pilot = analyze_place(pilot_raw, as_of.year, iqr=False)
    pilot_iqr = analyze_place(pilot_raw, as_of.year, iqr=True)

    repeat_out = []
    for row in repeat.itertuples(index=False):
        block = prepared[(prepared.addr1 == row.addr1) & (prepared.addr2 == row.addr2) & (prepared.dong == row.dong)]
        result = analyze_place(block, as_of.year, iqr=False)
        catalog = complex_catalog(counts, (row.addr1, row.addr2, row.dong), as_of.year)
        repeat_out.append(
            {
                "addr1": row.addr1,
                "addr2": row.addr2,
                "dong": row.dong,
                "stratum": row.stratum,
                "n_tx_window": int(row.n_tx),
                "n_complex_ge_30": int(row.n_complex),
                "catalog_entered": [item for item in catalog if item["enters"]],
                "analysis": None if not result.get("ok") else {k: v for k, v in result.items() if k != "ok"},
                "reason": None if result.get("ok") else result.get("reason"),
            }
        )
    ok_repeats = [row for row in repeat_out if row["analysis"]]
    payload = {
        "status": "executed",
        "as_of": as_of.isoformat(),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "window_years": 5,
        "attribute_snapshot": snap,
        "seed": SEED,
        "notes": [
            "해제 거래는 적재 때 빠져 is_valid 표본에 없다. 아파트 원장에 지분 칸은 없다.",
            "금액 MAPE와 ㎡당 MAPE는 같은 면적으로 나누면 퍼센트 오차가 같다. 표의 MAPE는 그 값이다.",
            "모형 B는 단지 고정효과와 연도 더미가 연식을 포함하므로 연식 열을 뺐다.",
            "반복 지역은 거래수와 건축연도만으로 골랐다. 금정동은 12곳에 넣지 않았다.",
            "2차 집합공장 층과 3차 거래회전은 이번 실행에 넣지 않았다.",
        ],
        "pilot": {
            "addr1": pilot_place[0],
            "addr2": pilot_place[1],
            "dong": "금정동",
            "catalog": pilot_cat,
            "analysis": None if not pilot.get("ok") else {k: v for k, v in pilot.items() if k != "ok"},
            "iqr_1_5": None if not pilot_iqr.get("ok") else {
                "known": pilot_iqr["known"],
                "beta_unit": pilot_iqr["beta_unit"],
                "n_trades": pilot_iqr["n_trades"],
                "n_complex": pilot_iqr["n_complex"],
            },
        },
        "repeat_shortfall": shortfall,
        "repeat": repeat_out,
        "repeat_summary": summarize_repeats(ok_repeats),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(OUT), "pilot_ok": pilot.get("ok"), "repeat": len(ok_repeats), "shortfall": shortfall}, ensure_ascii=False))


if __name__ == "__main__":
    main()
