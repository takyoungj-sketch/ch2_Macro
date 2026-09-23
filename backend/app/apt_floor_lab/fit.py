"""아파트 층 효용 1차 — 단지별 1층=100, 그다음 지역 분포·구성·상호작용.

오피스텔은 넣지 않는다. 연식은 단지 안 식에 넣지 않는다.
재실행 (backend에서): python -m app.apt_floor_lab.fit
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import text

from app.apt_floor_lab.screen import (
    N1_MIN,
    OTHER_BIN_MIN,
    ROOT,
    experiment_floor_bin,
    latest_as_of_month,
)
from app.collective.db import get_collective_engine
from app.land_lab.area_elasticity_screen import period_bounds_for_window

SCREEN_JSON = ROOT / "docs" / "lab" / "apt_floor_utility_screen.json"
SCREEN_CSV = ROOT / "docs" / "lab" / "apt_floor_utility_screen.csv"
OUT_JSON = ROOT / "docs" / "lab" / "apt_floor_utility_phase1.json"
OUT_CSV = ROOT / "docs" / "lab" / "apt_floor_utility_buildings.csv"
OUT_PHASE5 = ROOT / "docs" / "lab" / "apt_floor_utility_phase5.json"

BIN_INDEX = ("low", "mid", "high", "top")
TIER_REF = "metro"
TIER_OTHER = ("metro_city", "other_urban", "nonurban", "sejong")
BAND_REF = "le15"
BAND_OTHER = ("m16_25", "ge26")
AGE_REF = "a11_20"
AGE_OTHER = ("le10", "a21_30", "ge31")
TIER_LABELS = {
    "metro": "수도권",
    "metro_city": "광역시",
    "other_urban": "기타 도시",
    "nonurban": "비도시",
    "sejong": "세종",
    "non_metro": "비수도권",
}
BAND_LABELS = {"le15": "≤15층", "m16_25": "16–25층", "ge26": "≥26층"}
AGE_LABELS = {"le10": "연식 ≤10", "a11_20": "연식 11–20", "a21_30": "연식 21–30", "ge31": "연식 ≥31"}
MIN_PERIOD = 5


def age_band(building_year: float | None, as_of_year: int) -> str | None:
    if building_year is None or not np.isfinite(building_year):
        return None
    year = int(round(float(building_year)))
    if year < 1960 or year > as_of_year:
        return None
    age = as_of_year - year
    if age <= 10:
        return "le10"
    if age <= 20:
        return "a11_20"
    if age <= 30:
        return "a21_30"
    return "ge31"


def _period_codes(year: np.ndarray, month: np.ndarray) -> np.ndarray:
    out = np.empty(len(year), dtype=object)
    for i, (y, m) in enumerate(zip(year, month)):
        if y is None or (isinstance(y, float) and not np.isfinite(y)) or pd.isna(y):
            out[i] = None
            continue
        yi = int(y)
        if m is None or (isinstance(m, float) and not np.isfinite(m)) or pd.isna(m):
            out[i] = f"{yi}"
        else:
            out[i] = f"{yi}H{1 if int(m) <= 6 else 2}"
    return out


def fit_building_index(
    floor: np.ndarray,
    area: np.ndarray,
    price: np.ndarray,
    year: np.ndarray,
    month: np.ndarray,
    max_floor: float,
) -> dict[str, Any]:
    """한 단지의 1층 대비 지수. 칸 n<5는 비운다. 연식은 넣지 않는다."""
    bins = np.array([experiment_floor_bin(float(f), max_floor) for f in floor], dtype=object)
    keep = np.array([b is not None for b in bins])
    bins = bins[keep]
    area = area[keep]
    price = price[keep]
    year = year[keep]
    month = month[keep]
    counts: dict[str, int] = {}
    for b in bins:
        counts[str(b)] = counts.get(str(b), 0) + 1
    use = np.array(
        [b == "f1" or counts.get(str(b), 0) >= OTHER_BIN_MIN for b in bins]
    )
    bins = bins[use]
    area = area[use]
    price = price[use]
    year = year[use]
    month = month[use]
    empty = {name: None for name in BIN_INDEX}
    empty.update({"ok": False, "n": int(len(price)), "reason": "thin"})
    if counts.get("f1", 0) < N1_MIN or len(price) < N1_MIN + OTHER_BIN_MIN:
        return empty
    present = [name for name in BIN_INDEX if counts.get(name, 0) >= OTHER_BIN_MIN]
    if not present:
        return empty
    y = np.log(price.astype(float))
    cols = [np.ones(len(y))]
    names = ["intercept"]
    for name in present:
        cols.append((bins == name).astype(float))
        names.append(name)
    ln_a = np.log(area.astype(float))
    if float(np.nanstd(ln_a)) > 1e-8:
        cols.append(ln_a)
        names.append("ln_a")
    periods = _period_codes(year, month)
    pcount: dict[str, int] = {}
    for p in periods:
        if p is None:
            continue
        pcount[str(p)] = pcount.get(str(p), 0) + 1
    if len(pcount) >= 2:
        ref = max(pcount, key=pcount.get)
        for code, cnt in pcount.items():
            if code == ref or cnt < MIN_PERIOD:
                continue
            cols.append(np.array([1.0 if p == code else 0.0 for p in periods]))
            names.append(f"p_{code}")
    x = np.column_stack(cols)
    if len(y) <= x.shape[1]:
        empty["reason"] = "dof"
        return empty
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if int(rank) < x.shape[1]:
        empty["reason"] = "rank"
        return empty
    out: dict[str, Any] = {"ok": True, "n": int(len(y)), "reason": ""}
    for name in BIN_INDEX:
        out[name] = None
    for name, coef in zip(names, beta):
        if name not in BIN_INDEX:
            continue
        gamma = float(coef)
        if not np.isfinite(gamma):
            continue
        out[name] = float(np.exp(gamma) * 100.0)
    return out


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float | None:
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    v = values[mask]
    w = weights[mask]
    if len(v) == 0:
        return None
    order = np.argsort(v, kind="mergesort")
    v = v[order]
    w = w[order]
    cutoff = float(w.sum()) * 0.5
    return float(v[int(np.searchsorted(np.cumsum(w), cutoff, side="left"))])


def _quantile(values: np.ndarray, q: float) -> float | None:
    v = values[np.isfinite(values)]
    if len(v) == 0:
        return None
    return float(np.quantile(v, q))


def dist_row(values: np.ndarray, weights: np.ndarray, *, key: str, label: str) -> dict[str, Any]:
    v = values[np.isfinite(values)]
    wmed = weighted_median(values, weights)
    med = _quantile(values, 0.5)
    return {
        "key": key,
        "label": label,
        "buildings": int(len(v)),
        "txns": int(np.nansum(weights[np.isfinite(values)])) if len(values) else 0,
        "p10": None if med is None else round(_quantile(values, 0.10) or 0, 1),
        "p50": None if med is None else round(med, 1),
        "p90": None if med is None else round(_quantile(values, 0.90) or 0, 1),
        "w_p50": None if wmed is None else round(wmed, 1),
        "share_above_100": None if len(v) == 0 else round(float(np.mean(v > 100)), 3),
    }


def summarize_indices(frame: pd.DataFrame) -> dict[str, Any]:
    """단지 1행. 동일가중 중위와 거래가중 중위. 전국 한 숫자는 만들지 않는다."""
    def pack(sub: pd.DataFrame, key: str, label: str) -> dict[str, Any]:
        row: dict[str, Any] = {"key": key, "label": label, "bins": {}}
        for name in BIN_INDEX:
            row["bins"][name] = dist_row(
                sub[name].to_numpy(dtype=float),
                sub["n"].to_numpy(dtype=float),
                key=name,
                label=name,
            )
        return row

    tiers = []
    for key in ("metro", "metro_city", "other_urban", "nonurban", "sejong"):
        sub = frame[frame["tier"] == key]
        if sub.empty:
            continue
        tiers.append(pack(sub, key, TIER_LABELS[key]))
    non_metro = frame[frame["tier"].isin(["metro_city", "other_urban", "nonurban"])]
    summary = [
        pack(frame[frame["tier"] == "metro"], "metro", TIER_LABELS["metro"]),
        pack(non_metro, "non_metro", TIER_LABELS["non_metro"]),
    ]
    bands = []
    for key in ("le15", "m16_25", "ge26"):
        sub = frame[frame["band"] == key]
        if sub.empty:
            continue
        bands.append(pack(sub, key, BAND_LABELS[key]))
    return {"by_tier": tiers, "capital_summary": summary, "by_band": bands}


def _design(series: pd.Series, levels: tuple[str, ...], prefix: str) -> tuple[pd.DataFrame, list[str]]:
    cols = {}
    names = []
    for level in levels:
        name = f"{prefix}_{level}"
        cols[name] = (series == level).astype(float)
        names.append(name)
    return pd.DataFrame(cols, index=series.index), names


def composition_fit(frame: pd.DataFrame, outcome: str, *, weighted: bool) -> dict[str, Any]:
    """단지 1행. 지수 ~ 지역 + 최고층 대역 + 연식대. 기준=수도권·≤15층·연식 11–20."""
    work = frame.dropna(subset=[outcome, "tier", "band", "age_band", "n"]).copy()
    work = work[work["age_band"].isin([AGE_REF, *AGE_OTHER])]
    work = work[work["tier"].isin([TIER_REF, *TIER_OTHER])]
    work = work[work["band"].isin([BAND_REF, *BAND_OTHER])]
    y = work[outcome].to_numpy(dtype=float)
    parts = [pd.Series(1.0, index=work.index, name="intercept")]
    names = ["intercept"]
    for series, levels, prefix in (
        (work["tier"], TIER_OTHER, "tier"),
        (work["band"], BAND_OTHER, "band"),
        (work["age_band"], AGE_OTHER, "age"),
    ):
        block, block_names = _design(series, levels, prefix)
        parts.append(block)
        names.extend(block_names)
    x = pd.concat(parts, axis=1).to_numpy(dtype=float)
    if weighted:
        model = sm.WLS(y, x, weights=work["n"].to_numpy(dtype=float)).fit()
    else:
        model = sm.OLS(y, x).fit()
    coefs = []
    for i, name in enumerate(names):
        if name == "intercept":
            continue
        coefs.append(
            {
                "name": name,
                "coef": round(float(model.params[i]), 2),
                "se": round(float(model.bse[i]), 2),
                "p": round(float(model.pvalues[i]), 4),
            }
        )
    return {
        "outcome": outcome,
        "weighted": weighted,
        "n_buildings": int(len(work)),
        "reference": "수도권 · ≤15층 · 연식 11–20",
        "coefs": coefs,
    }


def _within_cluster(work: pd.DataFrame, xcols: list[str]) -> dict[str, Any]:
    cols = ["ln_p", *xcols]
    dem = work[cols].astype(float) - work.groupby("building_key")[cols].transform("mean")
    keep = [c for c in xcols if float(dem[c].std()) > 1e-10]
    y = dem["ln_p"].to_numpy()
    x = dem[keep].to_numpy()
    groups = pd.factorize(work["building_key"])[0]
    model = sm.OLS(y, x, hasconst=False).fit(
        cov_type="cluster",
        cov_kwds={"groups": groups},
    )
    out = {}
    for i, name in enumerate(keep):
        gamma = float(model.params[i])
        out[name] = {
            "gamma": round(gamma, 4),
            "index": round(float(np.exp(gamma) * 100.0), 1),
            "se": round(float(model.bse[i]), 4),
            "p": round(float(model.pvalues[i]), 4),
        }
    return {
        "n": int(len(work)),
        "n_buildings": int(work["building_key"].nunique()),
        "coefs": out,
    }


def _period_columns(work: pd.DataFrame) -> list[str]:
    counts = work["period"].dropna().value_counts()
    if len(counts) < 2:
        return []
    ref = str(counts.idxmax())
    cols = []
    for code, cnt in counts.items():
        if str(code) == ref or int(cnt) < MIN_PERIOD:
            continue
        col = f"p_{code}"
        work[col] = (work["period"] == code).astype(float)
        cols.append(col)
    return cols


def interaction_region(work: pd.DataFrame) -> dict[str, Any]:
    """단지 FE. 지역 주효과는 넣지 않는다. 기준 계층=수도권, 기준 층=1층."""
    xcols: list[str] = []
    for name in BIN_INDEX:
        col = f"d_{name}"
        work[col] = (work["bin"] == name).astype(float)
        xcols.append(col)
        for tier in TIER_OTHER:
            icol = f"d_{name}__{tier}"
            work[icol] = ((work["bin"] == name) & (work["tier"] == tier)).astype(float)
            xcols.append(icol)
    work["ln_a"] = np.log(work["exclusive_area"].astype(float))
    xcols.append("ln_a")
    xcols.extend(_period_columns(work))
    fit = _within_cluster(work, xcols)
    fit["reference"] = "수도권의 1층 대비. θ는 그 계층이 수도권과 다른 정도."
    return fit


def interaction_band(work: pd.DataFrame) -> dict[str, Any]:
    xcols: list[str] = []
    for name in BIN_INDEX:
        col = f"d_{name}"
        work[col] = (work["bin"] == name).astype(float)
        xcols.append(col)
        for band in BAND_OTHER:
            icol = f"d_{name}__{band}"
            work[icol] = ((work["bin"] == name) & (work["band"] == band)).astype(float)
            xcols.append(icol)
    work["ln_a"] = np.log(work["exclusive_area"].astype(float))
    xcols.append("ln_a")
    xcols.extend(_period_columns(work))
    fit = _within_cluster(work, xcols)
    fit["reference"] = "≤15층 단지의 1층 대비. θ는 더 높은 대역이 ≤15층과 다른 정도."
    return fit


def _floor_main_columns(work: pd.DataFrame) -> list[str]:
    cols = []
    for name in BIN_INDEX:
        col = f"d_{name}"
        work[col] = (work["bin"] == name).astype(float)
        cols.append(col)
    return cols


def _region_floor_columns(work: pd.DataFrame) -> list[str]:
    """지역 주효과는 없다. 기준 계층은 수도권."""
    cols = []
    for name in BIN_INDEX:
        for tier in TIER_OTHER:
            icol = f"d_{name}__{tier}"
            work[icol] = ((work["bin"] == name) & (work["tier"] == tier)).astype(float)
            cols.append(icol)
    return cols


def _band_floor_columns(work: pd.DataFrame) -> list[str]:
    """대역 주효과는 없다. 기준 대역은 ≤15층."""
    cols = []
    for name in BIN_INDEX:
        for band in BAND_OTHER:
            icol = f"d_{name}__{band}"
            work[icol] = ((work["bin"] == name) & (work["band"] == band)).astype(float)
            cols.append(icol)
    return cols


def _height_floor_columns(work: pd.DataFrame) -> list[str]:
    """최고층은 15층에서 중심화. 단지 높이 주효과는 없다."""
    work["h"] = work["max_floor"].astype(float) - 15.0
    cols = []
    for name in BIN_INDEX:
        icol = f"d_{name}__h"
        work[icol] = (work["bin"] == name).astype(float) * work["h"]
        cols.append(icol)
    return cols


def _finish_fe(work: pd.DataFrame, xcols: list[str], reference: str) -> dict[str, Any]:
    work = work.dropna(subset=["tier", "band", "max_floor"]).copy()
    work["ln_a"] = np.log(work["exclusive_area"].astype(float))
    xcols = [*xcols, "ln_a", *_period_columns(work)]
    fit = _within_cluster(work, xcols)
    fit["reference"] = reference
    return fit


def interaction_joint_band(work: pd.DataFrame) -> dict[str, Any]:
    """상대층×지역과 상대층×대역을 한 식에. 유형은 넣지 않는다."""
    xcols = [
        *_floor_main_columns(work),
        *_region_floor_columns(work),
        *_band_floor_columns(work),
    ]
    return _finish_fe(
        work,
        xcols,
        "기준은 수도권·≤15층의 1층. 지역 θ는 대역을 통제한 뒤의 기울기 차이다.",
    )


def interaction_joint_height(work: pd.DataFrame) -> dict[str, Any]:
    """상대층×지역과 상대층×최고층(연속)을 한 식에. 대역 식과 섞지 않는다."""
    xcols = [
        *_floor_main_columns(work),
        *_region_floor_columns(work),
        *_height_floor_columns(work),
    ]
    return _finish_fe(
        work,
        xcols,
        "기준은 수도권·최고층 15의 1층. __h 는 최고층 1층당 기울기. 지역 θ는 그 높이를 통제한 뒤다.",
    )


def interaction_height(work: pd.DataFrame) -> dict[str, Any]:
    """최고층 연속. 15층에서 중심화. θ는 최고층 1층당 기울기 차이."""
    work = work.copy()
    work["h"] = work["max_floor"].astype(float) - 15.0
    xcols: list[str] = []
    for name in BIN_INDEX:
        col = f"d_{name}"
        work[col] = (work["bin"] == name).astype(float)
        xcols.append(col)
        icol = f"d_{name}__h"
        work[icol] = work[col] * work["h"]
        xcols.append(icol)
    work["ln_a"] = np.log(work["exclusive_area"].astype(float))
    xcols.append("ln_a")
    xcols.extend(_period_columns(work))
    fit = _within_cluster(work, xcols)
    fit["reference"] = "최고층 15에서 1층 대비. __h 는 최고층이 1층 늘 때 γ의 변화."
    return fit


def height_on_index(frame: pd.DataFrame, outcome: str, *, weighted: bool) -> dict[str, Any]:
    work = frame.dropna(subset=[outcome, "tier", "age_band", "max_floor", "n"]).copy()
    work = work[work["tier"].isin([TIER_REF, *TIER_OTHER])]
    work = work[work["age_band"].isin([AGE_REF, *AGE_OTHER])]
    y = work[outcome].to_numpy(dtype=float)
    parts = [
        pd.Series(1.0, index=work.index, name="intercept"),
        pd.Series(work["max_floor"].astype(float) - 15.0, index=work.index, name="height_c"),
    ]
    names = ["intercept", "height_c"]
    for series, levels, prefix in (
        (work["tier"], TIER_OTHER, "tier"),
        (work["age_band"], AGE_OTHER, "age"),
    ):
        block, block_names = _design(series, levels, prefix)
        parts.append(block)
        names.extend(block_names)
    x = pd.concat(parts, axis=1).to_numpy(dtype=float)
    if weighted:
        model = sm.WLS(y, x, weights=work["n"].to_numpy(dtype=float)).fit()
    else:
        model = sm.OLS(y, x).fit()
    coefs = []
    for i, name in enumerate(names):
        if name == "intercept":
            continue
        coefs.append(
            {
                "name": name,
                "coef": round(float(model.params[i]), 2),
                "se": round(float(model.bse[i]), 2),
                "p": round(float(model.pvalues[i]), 4),
            }
        )
    return {
        "outcome": outcome,
        "weighted": weighted,
        "n_buildings": int(len(work)),
        "reference": "최고층은 15층 기준 1층당 지수 점. 지역 기준=수도권, 연식 11–20",
        "coefs": coefs,
    }


def load_eligible_keys() -> pd.DataFrame:
    meta = pd.read_csv(SCREEN_CSV)
    meta = meta[meta["asset_type"] == "apartment"].copy()
    meta["building_key"] = meta["building_key"].astype(str).str.strip()
    return meta


def fetch_transactions(conn, keys: list[str], p_start, p_end) -> pd.DataFrame:
    conn.execute(text("DROP TABLE IF EXISTS apt_floor_lab_keys"))
    conn.execute(text("CREATE TEMP TABLE apt_floor_lab_keys (building_key text PRIMARY KEY)"))
    conn.execute(
        text("INSERT INTO apt_floor_lab_keys (building_key) VALUES (:k)"),
        [{"k": k} for k in keys],
    )
    sql = """
        SELECT
            t.building_key,
            t.floor,
            t.exclusive_area,
            t.unit_price,
            t.contract_year,
            t.contract_month,
            t.building_year
        FROM collective_transactions t
        JOIN apt_floor_lab_keys k ON k.building_key = t.building_key
        WHERE t.asset_type = 'apartment'
          AND t.is_valid = TRUE
          AND t.contract_date >= :p_start
          AND t.contract_date <= :p_end
          AND t.unit_price > 0
          AND t.exclusive_area > 0
          AND t.floor >= 1
    """
    upper = sql.upper()
    if "ANY" in upper or "AVG(" in upper:
        raise RuntimeError("phase1 SQL must not aggregate price or use ANY")
    return pd.read_sql(text(sql), conn, params={"p_start": p_start, "p_end": p_end})


def attach_bins(tx: pd.DataFrame) -> pd.DataFrame:
    tx = tx.copy()
    tx["building_key"] = tx["building_key"].astype(str).str.strip()
    tx["floor"] = pd.to_numeric(tx["floor"], errors="coerce")
    tx["exclusive_area"] = pd.to_numeric(tx["exclusive_area"], errors="coerce")
    tx["unit_price"] = pd.to_numeric(tx["unit_price"], errors="coerce")
    tx["building_year"] = pd.to_numeric(tx["building_year"], errors="coerce")
    tx = tx.dropna(subset=["floor", "exclusive_area", "unit_price"])
    tx = tx[(tx["floor"] >= 1) & (tx["exclusive_area"] > 0) & (tx["unit_price"] > 0)]
    mx = tx.groupby("building_key")["floor"].transform("max")
    tx["max_floor"] = mx
    tx["bin"] = [experiment_floor_bin(float(f), float(m)) for f, m in zip(tx["floor"], mx)]
    tx = tx[tx["bin"].notna()]
    counts = tx.groupby(["building_key", "bin"]).size().rename("bin_n").reset_index()
    tx = tx.merge(counts, on=["building_key", "bin"], how="left")
    tx = tx[(tx["bin"] == "f1") | (tx["bin_n"] >= OTHER_BIN_MIN)]
    return tx


def fit_all_buildings(tx: pd.DataFrame, meta: pd.DataFrame, as_of_year: int) -> pd.DataFrame:
    rows = []
    for key, g in tx.groupby("building_key", sort=False):
        fitted = fit_building_index(
            g["floor"].to_numpy(),
            g["exclusive_area"].to_numpy(),
            g["unit_price"].to_numpy(),
            g["contract_year"].to_numpy(),
            g["contract_month"].to_numpy(),
            float(g["max_floor"].iloc[0]),
        )
        year = float(np.nanmedian(g["building_year"].to_numpy(dtype=float)))
        rows.append(
            {
                "building_key": key,
                "ok": bool(fitted["ok"]),
                "reason": fitted.get("reason") or "",
                "n_fit": fitted.get("n"),
                "year": year if np.isfinite(year) else None,
                "low": fitted.get("low"),
                "mid": fitted.get("mid"),
                "high": fitted.get("high"),
                "top": fitted.get("top"),
            }
        )
    fitted_df = pd.DataFrame(rows)
    out = meta.merge(fitted_df, on="building_key", how="left")
    out["age_band"] = [age_band(y, as_of_year) for y in out["year"]]
    return out


def prepare_fe_frame(tx: pd.DataFrame, buildings: pd.DataFrame) -> pd.DataFrame:
    ok_keys = set(buildings.loc[buildings["ok"] == True, "building_key"])  # noqa: E712
    work = tx[tx["building_key"].isin(ok_keys)].copy()
    meta = buildings.set_index("building_key")[["tier", "band"]]
    work["tier"] = work["building_key"].map(meta["tier"])
    work["band"] = work["building_key"].map(meta["band"])
    work["ln_p"] = np.log(work["unit_price"].astype(float))
    work["period"] = _period_codes(
        work["contract_year"].to_numpy(),
        work["contract_month"].to_numpy(),
    )
    return work


def run_phase5() -> dict[str, Any]:
    """실험 5. 아파트만. 지역×층과 높이×층을 한 FE에 넣는다. 오피스텔 없음."""
    screen = json.loads(SCREEN_JSON.read_text(encoding="utf-8"))
    buildings = pd.read_csv(OUT_CSV)
    buildings["building_key"] = buildings["building_key"].astype(str).str.strip()
    buildings = buildings[buildings["ok"] == True].copy()  # noqa: E712
    engine = get_collective_engine()
    if engine is None:
        raise RuntimeError("COLLECTIVE_DATABASE_URL 없음")
    with engine.connect() as conn:
        as_of = latest_as_of_month(conn)
        p_start, p_end = period_bounds_for_window(as_of, 5)
        if p_start.isoformat() != screen["period_start"] or p_end.isoformat() != screen["period_end"]:
            raise RuntimeError("0차 창과 5차 창이 다릅니다. 0차를 다시 실행하세요.")
        tx = fetch_transactions(conn, buildings["building_key"].tolist(), p_start, p_end)
    work = prepare_fe_frame(attach_bins(tx), buildings)
    payload = {
        "as_of": as_of.isoformat(),
        "period_start": p_start.isoformat(),
        "period_end": p_end.isoformat(),
        "asset": "apartment",
        "officetel": "not_in_model",
        "note": "지역 주효과·높이 주효과·상품유형은 넣지 않는다. 대역 식과 연속 식은 따로다.",
        "joint_band": interaction_joint_band(work.copy()),
        "joint_height": interaction_joint_height(work.copy()),
    }
    OUT_PHASE5.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_phase1() -> dict[str, Any]:
    screen = json.loads(SCREEN_JSON.read_text(encoding="utf-8"))
    meta = load_eligible_keys()
    engine = get_collective_engine()
    if engine is None:
        raise RuntimeError("COLLECTIVE_DATABASE_URL 없음")
    with engine.connect() as conn:
        as_of = latest_as_of_month(conn)
        p_start, p_end = period_bounds_for_window(as_of, 5)
        if p_start.isoformat() != screen["period_start"] or p_end.isoformat() != screen["period_end"]:
            raise RuntimeError("0차 창과 1차 창이 다릅니다. 0차를 다시 실행하세요.")
        tx = fetch_transactions(conn, meta["building_key"].tolist(), p_start, p_end)
    tx = attach_bins(tx)
    buildings = fit_all_buildings(tx, meta, as_of.year)
    ok = buildings[buildings["ok"] == True].copy()  # noqa: E712
    dist = summarize_indices(ok)
    comp = {
        "top_equal": composition_fit(ok, "top", weighted=False),
        "top_weighted": composition_fit(ok, "top", weighted=True),
        "low_equal": composition_fit(ok, "low", weighted=False),
        "low_weighted": composition_fit(ok, "low", weighted=True),
    }
    height = {
        "top_equal": height_on_index(ok, "top", weighted=False),
        "top_weighted": height_on_index(ok, "top", weighted=True),
        "low_equal": height_on_index(ok, "low", weighted=False),
        "low_weighted": height_on_index(ok, "low", weighted=True),
    }
    fe_work = prepare_fe_frame(tx, buildings)
    fe = {
        "region": interaction_region(fe_work.copy()),
        "band": interaction_band(fe_work.copy()),
        "height": interaction_height(fe_work.copy()),
    }
    outside = {}
    for name in BIN_INDEX:
        v = ok[name]
        outside[name] = int(((v < 50) | (v > 200)).sum())
    payload = {
        "as_of": as_of.isoformat(),
        "period_start": p_start.isoformat(),
        "period_end": p_end.isoformat(),
        "asset": "apartment",
        "officetel": "closed_at_phase0",
        "buildings_eligible": int(len(buildings)),
        "buildings_fit": int(len(ok)),
        "buildings_failed": int((buildings["ok"] != True).sum()),  # noqa: E712
        "index_outside_50_200": outside,
        "note": "1층=100은 단지마다. p50은 동일가중, w_p50은 거래건수 가중. p10–p90은 가운데 80%. 전국 평균 지수는 없음.",
        "distribution": dist,
        "composition": comp,
        "height_on_index": height,
        "fe": fe,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    keep = [
        "building_key",
        "tier",
        "band",
        "n",
        "max_floor",
        "age_band",
        "year",
        "ok",
        "low",
        "mid",
        "high",
        "top",
    ]
    buildings[keep].to_csv(OUT_CSV, index=False)
    return payload


def main() -> None:
    payload = run_phase1()
    top = next(row["bins"]["top"] for row in payload["distribution"]["by_tier"] if row["key"] == "metro")
    print(
        json.dumps(
            {
                "fit": payload["buildings_fit"],
                "failed": payload["buildings_failed"],
                "metro_top_p50": top["p50"],
                "metro_top_w_p50": top["w_p50"],
                "json": str(OUT_JSON),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
