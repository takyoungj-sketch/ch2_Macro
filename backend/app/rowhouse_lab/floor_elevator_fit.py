"""실험 1: 건물 FE + 층 더미. ln(단가). 연식과 시점을 같이 넣지 않음.

승강기 주효과는 넣지 않는다 (실험 2a/2b).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.rowhouse_lab.floor_elevator import (
    N_SENSITIVITY,
    REGION_TYPES,
    age_band,
    age_coarse,
    cap_band,
    floor_bin,
    floor_bucket,
)

MIN_BUILDINGS = 2
MIN_ROWS = 20
P_ALPHA = 0.05
N_BOOT = 1000


def _period_key(year: Any, month: Any) -> str | None:
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None
    try:
        m = int(month) if month is not None and not (isinstance(month, float) and np.isnan(month)) else 6
    except (TypeError, ValueError):
        m = 6
    half = "h1" if m <= 6 else "h2"
    return f"{y}{half}"


def assemble_work(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    need = {"building_key", "floor", "unit_price", "exclusive_area"}
    if df.empty or not need.issubset(df.columns):
        return pd.DataFrame()
    work = df.copy()
    work["unit_price"] = pd.to_numeric(work["unit_price"], errors="coerce")
    work["exclusive_area"] = pd.to_numeric(work["exclusive_area"], errors="coerce")
    work["floor"] = pd.to_numeric(work["floor"], errors="coerce")
    work = work[work["unit_price"] > 0]
    work = work[work["exclusive_area"] > 0]
    mx = work.groupby("building_key")["floor"].transform("max")
    work["max_floor"] = mx
    work["bin"] = [floor_bin(f, m) for f, m in zip(work["floor"], work["max_floor"])]
    work = work[work["bin"].notna()]
    work["ln_p"] = np.log(work["unit_price"].astype(float))
    work["ln_a"] = np.log(work["exclusive_area"].astype(float))
    if "contract_year" in work.columns:
        month = work["contract_month"] if "contract_month" in work.columns else None
        if month is None:
            work["period"] = [_period_key(y, None) for y in work["contract_year"]]
        else:
            work["period"] = [_period_key(y, m) for y, m in zip(work["contract_year"], month)]
    else:
        work["period"] = None
    return work


def _demean(work: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = work[cols].astype(float).copy()
    means = work.groupby("building_key")[cols].transform("mean")
    return out - means.astype(float)


def fit_floor_fe(rows: list[dict[str, Any]], *, interact_elev: bool = False) -> dict[str, Any]:
    """건물 내 평균 제거 후 ln(단가) ~ 중간 + 최상 + ln(면적) [+ 시점].

    interact_elev=True 이면 중간×승강기·최상×승강기만 추가한다. 승강기 주효과는 넣지 않는다.
    """
    work = assemble_work(rows)
    n = int(len(work))
    n_b = int(work["building_key"].nunique()) if n else 0
    empty = {
        "ok": False,
        "n": n,
        "n_buildings": n_b,
        "gamma_mid": None,
        "gamma_top": None,
        "theta_mid": None,
        "theta_top": None,
        "se_mid": None,
        "se_top": None,
        "se_theta_mid": None,
        "se_theta_top": None,
        "p_mid": None,
        "p_top": None,
        "p_theta_mid": None,
        "p_theta_top": None,
        "beta_area": None,
        "r2": None,
        "reason": "",
        "n_elev_yes": 0,
        "n_elev_no": 0,
    }
    if n < MIN_ROWS or n_b < MIN_BUILDINGS:
        empty["reason"] = "thin"
        return empty
    if interact_elev:
        if "elevator" not in work.columns:
            empty["reason"] = "no_elev"
            return empty
        ev = work["elevator"].map(lambda x: True if x is True or x == 1 or x == "1" else False if x is False or x == 0 or x == "0" else None)
        work = work[ev.notna()].copy()
        work["elev"] = ev.loc[work.index].astype(float)
        n = int(len(work))
        n_b = int(work["building_key"].nunique()) if n else 0
        empty["n"] = n
        empty["n_buildings"] = n_b
        if n < MIN_ROWS or n_b < MIN_BUILDINGS:
            empty["reason"] = "thin"
            return empty
        b_e = work.groupby("building_key")["elev"].max()
        empty["n_elev_yes"] = int((b_e >= 0.5).sum())
        empty["n_elev_no"] = int((b_e < 0.5).sum())
        if empty["n_elev_yes"] < MIN_BUILDINGS or empty["n_elev_no"] < MIN_BUILDINGS:
            empty["reason"] = "one_arm"
            return empty
    work["d_mid"] = (work["bin"] == "mid").astype(float)
    work["d_top"] = (work["bin"] == "top").astype(float)
    xcols = ["d_mid", "d_top", "ln_a"]
    if interact_elev:
        work["d_mid_e"] = work["d_mid"] * work["elev"]
        work["d_top_e"] = work["d_top"] * work["elev"]
        xcols = ["d_mid", "d_top", "d_mid_e", "d_top_e", "ln_a"]
    if work["period"].notna().any():
        per = pd.get_dummies(work["period"], prefix="p", drop_first=True, dummy_na=False)
        for c in per.columns:
            work[c] = per[c].astype(float)
            xcols.append(c)
    dem = _demean(work, ["ln_p"] + xcols)
    y = dem["ln_p"].to_numpy()
    x = dem[xcols].to_numpy()
    need_rank = 4 if interact_elev else 2
    if np.linalg.matrix_rank(x) < need_rank:
        empty["reason"] = "rank"
        return empty
    model = sm.OLS(y, x, hasconst=False).fit()
    names = list(xcols)
    idx = {n: i for i, n in enumerate(names)}

    def coef(name: str) -> float | None:
        i = idx.get(name)
        if i is None:
            return None
        return float(model.params[i])

    def se(name: str) -> float | None:
        i = idx.get(name)
        if i is None:
            return None
        return float(model.bse[i])

    def pv(name: str) -> float | None:
        i = idx.get(name)
        if i is None:
            return None
        return float(model.pvalues[i])

    out = {
        "ok": True,
        "n": n,
        "n_buildings": n_b,
        "gamma_mid": coef("d_mid"),
        "gamma_top": coef("d_top"),
        "theta_mid": coef("d_mid_e") if interact_elev else None,
        "theta_top": coef("d_top_e") if interact_elev else None,
        "se_mid": se("d_mid"),
        "se_top": se("d_top"),
        "se_theta_mid": se("d_mid_e") if interact_elev else None,
        "se_theta_top": se("d_top_e") if interact_elev else None,
        "p_mid": pv("d_mid"),
        "p_top": pv("d_top"),
        "p_theta_mid": pv("d_mid_e") if interact_elev else None,
        "p_theta_top": pv("d_top_e") if interact_elev else None,
        "beta_area": coef("ln_a"),
        "r2": float(model.rsquared),
        "reason": "",
        "n_elev_yes": empty.get("n_elev_yes") or 0,
        "n_elev_no": empty.get("n_elev_no") or 0,
    }
    return out


def _r(x: float | None, nd: int = 4) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v:
        return None
    return round(v, nd)


def pct_from_gamma(gamma: float | None) -> float | None:
    if gamma is None:
        return None
    return float(math.exp(float(gamma)) - 1.0)


def gamma_direction(gamma: float | None, p: float | None, alpha: float = P_ALPHA) -> str:
    if gamma is None or p is None:
        return "na"
    if p >= alpha:
        return "ns"
    return "plus" if gamma > 0 else "minus"


def pack_fit(raw: dict[str, Any]) -> dict[str, Any]:
    g_mid = raw.get("gamma_mid")
    g_top = raw.get("gamma_top")
    t_mid = raw.get("theta_mid")
    t_top = raw.get("theta_top")
    p_mid = raw.get("p_mid")
    p_top = raw.get("p_top")
    p_tm = raw.get("p_theta_mid")
    p_tt = raw.get("p_theta_top")
    return {
        "ok": bool(raw.get("ok")),
        "n": int(raw.get("n") or 0),
        "n_buildings": int(raw.get("n_buildings") or 0),
        "n_elev_yes": int(raw.get("n_elev_yes") or 0),
        "n_elev_no": int(raw.get("n_elev_no") or 0),
        "gamma_mid": _r(g_mid),
        "gamma_top": _r(g_top),
        "theta_mid": _r(t_mid),
        "theta_top": _r(t_top),
        "se_mid": _r(raw.get("se_mid")),
        "se_top": _r(raw.get("se_top")),
        "se_theta_mid": _r(raw.get("se_theta_mid")),
        "se_theta_top": _r(raw.get("se_theta_top")),
        "p_mid": _r(p_mid),
        "p_top": _r(p_top),
        "p_theta_mid": _r(p_tm),
        "p_theta_top": _r(p_tt),
        "pct_mid": _r(pct_from_gamma(g_mid)),
        "pct_top": _r(pct_from_gamma(g_top)),
        "pct_theta_mid": _r(pct_from_gamma(t_mid)),
        "pct_theta_top": _r(pct_from_gamma(t_top)),
        "beta_area": _r(raw.get("beta_area")),
        "r2": _r(raw.get("r2")),
        "dir_mid": gamma_direction(g_mid, p_mid),
        "dir_top": gamma_direction(g_top, p_top),
        "dir_theta_mid": gamma_direction(t_mid, p_tm),
        "dir_theta_top": gamma_direction(t_top, p_tt),
        "reason": str(raw.get("reason") or ""),
    }


def dirs_agree(dirs: list[str]) -> str:
    """plus/minus만 본다. ns는 합의에서 빼고, 유의한 칸이 없으면 ns."""
    sig = [d for d in dirs if d in {"plus", "minus"}]
    if not sig:
        return "ns"
    uniq = set(sig)
    if len(uniq) == 1:
        return next(iter(uniq))
    return "split"


def signs_disagree(dir_pooled: str, share_pos: float | None) -> bool:
    if share_pos is None or dir_pooled not in {"plus", "minus"}:
        return False
    if dir_pooled == "plus" and share_pos < 0.45:
        return True
    if dir_pooled == "minus" and share_pos > 0.55:
        return True
    return False


def _bootstrap_median_ci(values: np.ndarray, n_boot: int = N_BOOT, seed: int = 0) -> tuple[float | None, float | None]:
    if values.size < 8:
        return None, None
    rng = np.random.default_rng(seed)
    meds = np.empty(n_boot, dtype=float)
    n = values.size
    for i in range(n_boot):
        meds[i] = float(np.median(rng.choice(values, size=n, replace=True)))
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def building_median_summary(work: pd.DataFrame) -> dict[str, Any]:
    empty = {
        "n_buildings": 0,
        "n_mid": 0,
        "n_top": 0,
        "n_pos_mid": 0,
        "n_neg_mid": 0,
        "share_pos_mid": None,
        "median_delta_mid": None,
        "mean_delta_mid": None,
        "ci_lo_mid": None,
        "ci_hi_mid": None,
        "n_pos_top": 0,
        "n_neg_top": 0,
        "share_pos_top": None,
        "median_delta_top": None,
        "mean_delta_top": None,
        "ci_lo_top": None,
        "ci_hi_top": None,
    }
    if work.empty:
        return empty
    counts = work.groupby(["building_key", "bin"]).size().unstack(fill_value=0)
    med = work.groupby(["building_key", "bin"])["unit_price"].median().unstack()
    d_mid: list[float] = []
    d_top: list[float] = []
    n_pos_mid = n_neg_mid = n_pos_top = n_neg_top = 0
    for bk, row in med.iterrows():
        n1 = int(counts.loc[bk, "1"]) if "1" in counts.columns and bk in counts.index else 0
        nmid = int(counts.loc[bk, "mid"]) if "mid" in counts.columns and bk in counts.index else 0
        ntop = int(counts.loc[bk, "top"]) if "top" in counts.columns and bk in counts.index else 0
        m1 = row["1"] if "1" in row.index else None
        if m1 is None or (isinstance(m1, float) and (m1 != m1 or m1 <= 0)):
            continue
        if n1 >= 3 and nmid >= 3 and "mid" in row.index and pd.notna(row["mid"]):
            delta = float(row["mid"]) / float(m1) - 1.0
            d_mid.append(delta)
            if delta > 0:
                n_pos_mid += 1
            elif delta < 0:
                n_neg_mid += 1
        if n1 >= 3 and ntop >= 3 and "top" in row.index and pd.notna(row["top"]):
            delta = float(row["top"]) / float(m1) - 1.0
            d_top.append(delta)
            if delta > 0:
                n_pos_top += 1
            elif delta < 0:
                n_neg_top += 1
    lo_m, hi_m = _bootstrap_median_ci(np.array(d_mid, dtype=float)) if d_mid else (None, None)
    lo_t, hi_t = _bootstrap_median_ci(np.array(d_top, dtype=float)) if d_top else (None, None)
    n_m = len(d_mid)
    n_t = len(d_top)
    return {
        "n_buildings": int(work["building_key"].nunique()),
        "n_mid": n_m,
        "n_top": n_t,
        "n_pos_mid": n_pos_mid,
        "n_neg_mid": n_neg_mid,
        "share_pos_mid": _r(n_pos_mid / n_m if n_m else None),
        "median_delta_mid": _r(float(np.median(d_mid)) if d_mid else None),
        "mean_delta_mid": _r(float(np.mean(d_mid)) if d_mid else None),
        "ci_lo_mid": _r(lo_m),
        "ci_hi_mid": _r(hi_m),
        "n_pos_top": n_pos_top,
        "n_neg_top": n_neg_top,
        "share_pos_top": _r(n_pos_top / n_t if n_t else None),
        "median_delta_top": _r(float(np.median(d_top)) if d_top else None),
        "mean_delta_top": _r(float(np.mean(d_top)) if d_top else None),
        "ci_lo_top": _r(lo_t),
        "ci_hi_top": _r(hi_t),
    }


def attach_meta(
    tx_rows: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    elev_by_key: dict[str, bool | None] | None = None,
) -> list[dict[str, Any]]:
    meta = {str(c.get("building_key") or "").strip(): c for c in cells if c.get("eligible")}
    out: list[dict[str, Any]] = []
    for r in tx_rows:
        k = str(r.get("building_key") or "").strip()
        m = meta.get(k)
        if not m:
            continue
        rec = dict(r)
        rec["building_key"] = k
        rec["region_type"] = m.get("region_type")
        rec["n_building"] = int(m.get("n") or 0)
        rec["floor_bucket"] = floor_bucket(m.get("max_floor_tx"))
        rec["housing_subtype"] = (m.get("housing_subtype") or rec.get("housing_subtype") or None)
        rec["median_year"] = m.get("median_year")
        rec["sido_name"] = m.get("sido_name") or rec.get("sido_name")
        rec["ident_45"] = bool(m.get("ident_45"))
        if elev_by_key is not None:
            rec["elevator"] = elev_by_key.get(k)
        out.append(rec)
    return out


def run_phase1(tx_rows: list[dict[str, Any]], cells: list[dict[str, Any]]) -> dict[str, Any]:
    rows = attach_meta(tx_rows, cells)
    pooled = pack_fit(fit_floor_fe(rows))
    by_n: dict[str, Any] = {}
    for t in N_SENSITIVITY:
        sub = [r for r in rows if int(r.get("n_building") or 0) >= t]
        by_n[str(t)] = pack_fit(fit_floor_fe(sub))
    by_type: dict[str, Any] = {}
    for t in REGION_TYPES:
        sub = [r for r in rows if r.get("region_type") == t]
        by_type[t] = pack_fit(fit_floor_fe(sub))
    by_floor: dict[str, Any] = {}
    for b in ("4", "5", "6plus"):
        sub = [r for r in rows if r.get("floor_bucket") == b]
        by_floor[b] = pack_fit(fit_floor_fe(sub))
    subtypes = sorted({str(r.get("housing_subtype")) for r in rows if r.get("housing_subtype")})
    by_subtype: dict[str, Any] = {}
    for s in subtypes:
        sub = [r for r in rows if str(r.get("housing_subtype")) == s]
        packed = pack_fit(fit_floor_fe(sub))
        if packed["n_buildings"] >= MIN_BUILDINGS:
            by_subtype[s] = packed
    work = assemble_work(rows)
    delta = building_median_summary(work)
    type_agree_mid = dirs_agree([by_type[t]["dir_mid"] for t in REGION_TYPES])
    type_agree_top = dirs_agree([by_type[t]["dir_top"] for t in REGION_TYPES])
    n_agree_mid = dirs_agree([by_n[str(t)]["dir_mid"] for t in N_SENSITIVITY])
    n_agree_top = dirs_agree([by_n[str(t)]["dir_top"] for t in N_SENSITIVITY])
    n_sig_mid = [str(t) for t in N_SENSITIVITY if by_n[str(t)]["dir_mid"] in {"plus", "minus"}]
    n_sig_top = [str(t) for t in N_SENSITIVITY if by_n[str(t)]["dir_top"] in {"plus", "minus"}]
    type_sig_mid = [t for t in REGION_TYPES if by_type[t]["dir_mid"] in {"plus", "minus"}]
    type_sig_top = [t for t in REGION_TYPES if by_type[t]["dir_top"] in {"plus", "minus"}]
    return {
        "pooled": pooled,
        "by_n": by_n,
        "by_type": by_type,
        "by_max_floor": by_floor,
        "by_subtype": by_subtype,
        "building_delta": delta,
        "type_agree_mid": type_agree_mid,
        "type_agree_top": type_agree_top,
        "n_agree_mid": n_agree_mid,
        "n_agree_top": n_agree_top,
        "n_sig_mid": n_sig_mid,
        "n_sig_top": n_sig_top,
        "type_sig_mid": type_sig_mid,
        "type_sig_top": type_sig_top,
        "sign_disagree_mid": signs_disagree(pooled["dir_mid"], delta.get("share_pos_mid")),
        "sign_disagree_top": signs_disagree(pooled["dir_top"], delta.get("share_pos_top")),
    }


def run_phase2b(
    tx_rows: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    elev_by_key: dict[str, bool | None],
) -> dict[str, Any]:
    rows = attach_meta(tx_rows, cells, elev_by_key)
    known = [r for r in rows if r.get("elevator") is True or r.get("elevator") is False]
    pooled = pack_fit(fit_floor_fe(known, interact_elev=True))
    by_floor: dict[str, Any] = {}
    for b in ("4", "5", "6plus"):
        sub = [r for r in known if r.get("floor_bucket") == b]
        by_floor[b] = pack_fit(fit_floor_fe(sub, interact_elev=True))
    by_type: dict[str, Any] = {}
    for t in REGION_TYPES:
        sub = [r for r in known if r.get("region_type") == t]
        by_type[t] = pack_fit(fit_floor_fe(sub, interact_elev=True))
    return {
        "pooled": pooled,
        "by_max_floor": by_floor,
        "by_type": by_type,
        "n_known": len({r["building_key"] for r in known}),
        "n_yes": len({r["building_key"] for r in known if r.get("elevator") is True}),
        "n_no": len({r["building_key"] for r in known if r.get("elevator") is False}),
    }


def _elev_flag(v: Any) -> bool | None:
    if v is True or v == 1 or v == "1":
        return True
    if v is False or v == 0 or v == "0":
        return False
    return None


def run_phase2a_balance(
    cells: list[dict[str, Any]],
    elev_by_key: dict[str, bool | None],
) -> dict[str, Any]:
    cells_45 = [c for c in cells if c.get("eligible") and c.get("ident_45")]
    n_yes = n_no = n_unk = 0
    grid: dict[str, dict[str, Any]] = {}
    for c in cells_45:
        k = str(c.get("building_key") or "").strip()
        ev = _elev_flag(elev_by_key.get(k))
        if ev is True:
            n_yes += 1
            arm = "yes"
        elif ev is False:
            n_no += 1
            arm = "no"
        else:
            n_unk += 1
            arm = "unk"
        ab = age_band(c.get("median_year")) or "na"
        fb = floor_bucket(c.get("max_floor_tx")) or "na"
        rt = str(c.get("region_type") or "na")
        key = f"{ab}|{fb}|{rt}"
        rec = grid.setdefault(
            key, {"age_band": ab, "floor": fb, "region_type": rt, "yes": 0, "no": 0, "unk": 0}
        )
        rec[arm] += 1
    rows = sorted(grid.values(), key=lambda r: (r["age_band"], r["floor"], r["region_type"]))
    n_both = sum(1 for r in rows if r["yes"] > 0 and r["no"] > 0)
    return {
        "n_ident45": len(cells_45),
        "n_yes": n_yes,
        "n_no": n_no,
        "n_unknown": n_unk,
        "n_cells": len(rows),
        "n_cells_both": n_both,
        "rows": rows,
        "level_ok": n_yes >= 30 and n_no >= 30 and n_both >= 3,
    }


def fit_elev_level(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """실험 2a: FE 없음. 승강기 주효과 δ. 인과로 읽지 않음."""
    work = assemble_work(rows)
    empty = {
        "ok": False,
        "n": int(len(work)),
        "n_buildings": int(work["building_key"].nunique()) if len(work) else 0,
        "delta": None,
        "se": None,
        "p": None,
        "pct": None,
        "dir": "na",
        "reason": "thin",
    }
    if work.empty or "elevator" not in work.columns:
        return empty
    if "ident_45" in work.columns:
        work = work[work["ident_45"].astype(bool)]
    ev = work["elevator"].map(_elev_flag)
    work = work[ev.notna()].copy()
    work["elev"] = ev.loc[work.index].astype(float)
    work["d_mid"] = (work["bin"] == "mid").astype(float)
    work["d_top"] = (work["bin"] == "top").astype(float)
    n = int(len(work))
    n_b = int(work["building_key"].nunique()) if n else 0
    empty["n"] = n
    empty["n_buildings"] = n_b
    if n < MIN_ROWS or n_b < MIN_BUILDINGS:
        return empty
    parts = [work[["elev", "d_mid", "d_top", "ln_a"]].astype(float)]
    if "region_type" in work.columns and work["region_type"].nunique() > 1:
        d = pd.get_dummies(work["region_type"], prefix="rt", drop_first=True)
        parts.append(d.astype(float))
    if "median_year" in work.columns:
        work["age_b"] = [age_band(y) for y in work["median_year"]]
        if work["age_b"].nunique() > 1:
            d = pd.get_dummies(work["age_b"], prefix="age", drop_first=True, dummy_na=True)
            parts.append(d.astype(float))
    if work["period"].notna().any():
        d = pd.get_dummies(work["period"], prefix="p", drop_first=True, dummy_na=False)
        parts.append(d.astype(float))
    X = pd.concat(parts, axis=1)
    X = sm.add_constant(X, has_constant="add")
    try:
        model = sm.OLS(work["ln_p"].astype(float), X.astype(float), missing="drop").fit()
    except Exception:
        empty["reason"] = "fit"
        return empty
    if "elev" not in model.params.index:
        empty["reason"] = "no_delta"
        return empty
    delta = float(model.params["elev"])
    p = float(model.pvalues["elev"])
    return {
        "ok": True,
        "n": n,
        "n_buildings": n_b,
        "delta": _r(delta),
        "se": _r(float(model.bse["elev"])),
        "p": _r(p),
        "pct": _r(pct_from_gamma(delta)),
        "dir": gamma_direction(delta, p),
        "reason": "",
        "r2": _r(float(model.rsquared)),
    }


def run_phase2a(
    tx_rows: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    elev_by_key: dict[str, bool | None],
) -> dict[str, Any]:
    bal = run_phase2a_balance(cells, elev_by_key)
    out: dict[str, Any] = {"balance": bal, "level": None}
    if not bal.get("level_ok"):
        out["level_skipped"] = "unbalanced"
        return out
    rows = attach_meta(tx_rows, cells, elev_by_key)
    ident = [r for r in rows if r.get("ident_45") and r.get("elevator") is not None]
    out["level"] = fit_elev_level(ident)
    return out


def lab_sketch(fit: dict[str, Any]) -> dict[str, Any]:
    """1층=100. 2b 건물 안 γ(+θ). 2a 수준·제품 칸 아님."""
    g_m = fit.get("gamma_mid")
    g_t = fit.get("gamma_top")
    t_m = fit.get("theta_mid")
    t_t = fit.get("theta_top")

    def idx(g: float | None) -> float | None:
        if g is None:
            return None
        return _r(100.0 * math.exp(float(g)), 1)

    def add(a: Any, b: Any) -> float | None:
        if a is None:
            return None
        return float(a) + (float(b) if b is not None else 0.0)

    return {
        "base": 100,
        "no": {"1": 100.0, "mid": idx(g_m), "top": idx(g_t)},
        "yes": {"1": 100.0, "mid": idx(add(g_m, t_m)), "top": idx(add(g_t, t_t))},
        "note": "건물 안 1층=100. 2b γ+θ. 2a 수준 아님. 제품 칸 아님.",
    }


def _slice_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return pack_fit(fit_floor_fe(rows, interact_elev=True))


def _ok_dir(fit: dict[str, Any] | None, key: str) -> str | None:
    if not fit or not fit.get("ok"):
        return None
    d = str(fit.get(key) or "na")
    if d in {"plus", "minus", "ns"}:
        return d
    return None


def run_phase3(
    tx_rows: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    elev_by_key: dict[str, bool | None],
    purpose_by_key: dict[str, str] | None = None,
) -> dict[str, Any]:
    """같은 적격·승강기 기지 풀. 계수로 다시 고르지 않음."""
    rows = attach_meta(tx_rows, cells, elev_by_key)
    for r in rows:
        r["cap"] = cap_band(r.get("sido_name"))
        r["age_c"] = age_coarse(r.get("median_year"))
        if purpose_by_key:
            r["purpose"] = purpose_by_key.get(str(r.get("building_key") or "").strip()) or "other"
    eligible_keys = {str(c.get("building_key") or "").strip() for c in cells if c.get("eligible")}
    known = [r for r in rows if r.get("elevator") is True or r.get("elevator") is False]
    known_keys = {r["building_key"] for r in known}
    pooled = _slice_pack(known)
    by_floor: dict[str, Any] = {}
    for b in ("4", "5", "6plus"):
        by_floor[b] = _slice_pack([r for r in known if r.get("floor_bucket") == b])
    by_cap: dict[str, Any] = {}
    for b in ("capital", "noncapital"):
        by_cap[b] = _slice_pack([r for r in known if r.get("cap") == b])
    by_age: dict[str, Any] = {}
    for b in ("old", "new"):
        by_age[b] = _slice_pack([r for r in known if r.get("age_c") == b])
    by_n: dict[str, Any] = {}
    for t in N_SENSITIVITY:
        by_n[str(t)] = _slice_pack([r for r in known if int(r.get("n_building") or 0) >= t])
    by_purpose: dict[str, Any] = {}
    purpose_n: dict[str, int] = {}
    if purpose_by_key:
        for s in ("연립", "다세대", "both", "other"):
            keys = {r["building_key"] for r in known if r.get("purpose") == s}
            purpose_n[s] = len(keys)
            if s in {"연립", "다세대"} and keys:
                packed = _slice_pack([r for r in known if r.get("purpose") == s])
                if packed["n_buildings"] >= MIN_BUILDINGS:
                    by_purpose[s] = packed
    agree_items: list[tuple[str, dict[str, Any]]] = [
        ("4", by_floor.get("4") or {}),
        ("5", by_floor.get("5") or {}),
        ("capital", by_cap.get("capital") or {}),
        ("noncapital", by_cap.get("noncapital") or {}),
        ("old", by_age.get("old") or {}),
        ("new", by_age.get("new") or {}),
    ]
    for name, fit in by_purpose.items():
        agree_items.append((name, fit))
    dirs_top = [_ok_dir(fit, "dir_theta_top") for _, fit in agree_items]
    dirs_mid = [_ok_dir(fit, "dir_theta_mid") for _, fit in agree_items]
    used_top = [name for (name, fit), d in zip(agree_items, dirs_top) if d is not None]
    used_mid = [name for (name, fit), d in zip(agree_items, dirs_mid) if d is not None]
    return {
        "n_eligible": len(eligible_keys),
        "n_known": len(known_keys),
        "n_yes": len({r["building_key"] for r in known if r.get("elevator") is True}),
        "n_no": len({r["building_key"] for r in known if r.get("elevator") is False}),
        "pooled": pooled,
        "by_max_floor": by_floor,
        "by_cap": by_cap,
        "by_age": by_age,
        "by_n": by_n,
        "by_purpose": by_purpose,
        "purpose_n": purpose_n,
        "agree_theta_top": dirs_agree([d for d in dirs_top if d is not None]),
        "agree_theta_mid": dirs_agree([d for d in dirs_mid if d is not None]),
        "agree_slices_top": used_top,
        "agree_slices_mid": used_mid,
        "sketch": lab_sketch(pooled),
        "reselected": False,
    }

