"""시도별 현재 지역회귀식(시도당 1회)으로 신축 연식=0 잔차를 스택.

전국 한 식은 만들지 않는다. ŷ에 프리미엄 % 보정 없음.

재실행 (backend에서):
  python -m app.collective.regional_regression.age0_residual_lab

숫자는 `docs/lab/age0_residual_run.json`의 national/sidos를 덮어쓴다.
verdict·next·daejeon은 기존 스냅샷을 유지한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import text

from app.collective.building_stats_query import latest_mart_snapshot, stats_as_of_label
from app.collective.danji_attributes import ATTRIBUTES_TABLE
from app.collective.db import get_collective_engine
from app.collective.regional_regression.engine import (
    _design,
    _eligible_mask,
    _fit_ols,
    _flags,
)
from app.collective.regional_regression.schemas import RegionalRegressionVariables

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs" / "lab" / "age0_residual_run.json"
KEEP_LAB_KEYS = (
    "run_id",
    "date",
    "decision",
    "status",
    "product_change",
    "verdict",
    "answers",
    "next",
    "limits",
    "resume",
    "daejeon",
)
WINDOW = 5
MODEL = "log"
WEIGHT = "equal"
N_BOOT = 5000
SEED = 42
VARS = RegionalRegressionVariables(
    households=True,
    max_floor=True,
    building_age=True,
    parking=True,
    structure=False,
    builder=False,
    asset_type_dummy=False,
    assessed_land_price=False,
)


def _pct(x: float | None, d: int = 1) -> float | None:
    if x is None or not np.isfinite(x):
        return None
    return round(float(x) * 100, d)


def _opt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _summarize(y: np.ndarray, yhat: np.ndarray, yhat0: np.ndarray) -> dict:
    n = int(len(y))
    if n == 0:
        return {"n": 0}
    err0 = (y - yhat0) / y
    err_act = (y - yhat) / y
    prem0 = y / yhat0 - 1.0
    under0 = y > yhat0
    rng = np.random.default_rng(SEED)

    def boot_ci(arr: np.ndarray) -> dict:
        if len(arr) < 2:
            return {
                "mean": round(float(arr.mean()) * 100, 2) if len(arr) else None,
                "ci95": None,
            }
        means = np.array(
            [arr[rng.integers(0, len(arr), len(arr))].mean() for _ in range(N_BOOT)]
        )
        return {
            "mean": round(float(arr.mean()) * 100, 2),
            "ci95": [
                round(float(np.percentile(means, 2.5)) * 100, 2),
                round(float(np.percentile(means, 97.5)) * 100, 2),
            ],
        }

    try:
        from scipy.stats import wilcoxon

        w = wilcoxon(y - yhat0, alternative="greater", zero_method="wilcox")
        wil = {"stat": round(float(w.statistic), 3), "p": float(w.pvalue)}
    except Exception as exc:  # noqa: BLE001
        wil = {"error": str(exc)}

    return {
        "n": n,
        "mean_residual_rate_actual_age": _pct(float(err_act.mean()), 2),
        "median_residual_rate_actual_age": _pct(float(np.median(err_act)), 2),
        "mean_residual_rate_age0": _pct(float(err0.mean()), 2),
        "median_residual_rate_age0": _pct(float(np.median(err0)), 2),
        "mean_ape_actual_age": _pct(float(np.mean(np.abs(err_act))), 2),
        "median_ape_actual_age": _pct(float(np.median(np.abs(err_act))), 2),
        "mean_ape_age0": _pct(float(np.mean(np.abs(err0))), 2),
        "median_ape_age0": _pct(float(np.median(np.abs(err0))), 2),
        "mean_y_over_yhat0_minus_1": _pct(float(prem0.mean()), 2),
        "median_y_over_yhat0_minus_1": _pct(float(np.median(prem0)), 2),
        "underpred_share_age0": _pct(float(under0.mean()), 1),
        "mean_y": round(float(y.mean()), 1),
        "mean_yhat_actual_age": round(float(yhat.mean()), 1),
        "mean_yhat0": round(float(yhat0.mean()), 1),
        "bootstrap_mean_residual_rate_age0_pct": boot_ci(err0),
        "bootstrap_mean_premium_vs_age0_pct": boot_ci(prem0),
        "wilcoxon_y_minus_yhat0_greater": wil,
    }


def _mw(a: np.ndarray, b: np.ndarray) -> dict | None:
    if len(a) < 3 or len(b) < 3:
        return None
    try:
        from scipy.stats import mannwhitneyu

        r = mannwhitneyu(a, b, alternative="two-sided")
        return {"u": round(float(r.statistic), 1), "p": float(r.pvalue)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _prepare(df: pd.DataFrame, as_of_year: int) -> pd.DataFrame:
    out = df.copy()
    appr = pd.to_numeric(out["approved_year"], errors="coerce")
    by = pd.to_numeric(out["building_year"], errors="coerce")
    vintage = appr.fillna(by)
    out["building_age"] = as_of_year - vintage
    out.loc[(out["building_age"] < 0) | (out["building_age"] > 80), "building_age"] = np.nan
    for col in ("households", "max_floor", "parking_per_household", "median"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["n_tx"] = pd.to_numeric(out["n_tx"], errors="coerce").fillna(0)
    out["asset_type"] = out["asset_type"].fillna("apartment").astype(str)
    flags = out["attr_quality_flags"].map(_flags)
    out.loc[flags.map(lambda s: "hh_zero" in s or "scale_inconsistent" in s), "households"] = np.nan
    out.loc[flags.map(lambda s: "floor_implausible" in s or "scale_inconsistent" in s), "max_floor"] = np.nan
    out.loc[flags.map(lambda s: "parking_implausible" in s), "parking_per_household"] = np.nan
    out.loc[out["households"] <= 0, "households"] = np.nan
    out.loc[out["max_floor"] <= 0, "max_floor"] = np.nan
    out.loc[out["parking_per_household"] < 0, "parking_per_household"] = np.nan
    return out


def fit_sido(df: pd.DataFrame, addr1: str) -> dict:
    elig = _eligible_mask(df, VARS)
    work = df.loc[elig].copy()
    if len(work) < 20:
        return {"ok": False, "addr1": addr1, "reason": f"eligible n={len(work)}", "n_pool": int(len(df))}
    x, _labels, _w = _design(work, VARS)
    fitted = _fit_ols(work, x, model_type=MODEL, weight_mode=WEIGHT, train_idx=work.index, hold_idx=None)
    if fitted is None:
        return {"ok": False, "addr1": addr1, "reason": "fit failed", "n_pool": int(len(df))}
    idx = fitted["work_index"]
    train = work.loc[idx]
    y = train["median"].astype(float).to_numpy()
    yhat = np.asarray(fitted["y_hat"], dtype=float)
    age = train["building_age"].astype(float).to_numpy()
    x0 = x.loc[idx].copy()
    x0["building_age"] = 0.0
    x0c = sm.add_constant(x0, has_constant="add").reindex(columns=fitted["x_cols"], fill_value=0.0)
    raw0 = np.asarray(fitted["model"].predict(x0c), dtype=float)
    yhat0 = np.exp(raw0) * fitted["smear"]
    coef_age = next(
        ({"coef": round(c.coef, 6), "p": c.p, "t": c.t} for c in fitted["coefficients"] if c.name == "building_age"),
        None,
    )
    rows = []
    for i, pos in enumerate(idx):
        r = train.loc[pos]
        rows.append(
            {
                "addr1": addr1,
                "addr2": str(r.get("addr2") or ""),
                "addr3": str(r.get("addr3") or ""),
                "name": str(r.get("display_name") or ""),
                "age": round(float(age[i]), 1),
                "y": round(float(y[i]), 1),
                "yhat": round(float(yhat[i]), 1),
                "yhat0": round(float(yhat0[i]), 1),
                "err_act_pct": _pct((y[i] - yhat[i]) / y[i], 1),
                "err0_pct": _pct((y[i] - yhat0[i]) / y[i], 1),
                "prem0_pct": _pct(y[i] / yhat0[i] - 1.0, 1),
                "hh": _opt(r.get("households")),
                "floor": _opt(r.get("max_floor")),
                "park": _opt(r.get("parking_per_household")),
                "n_tx": int(r["n_tx"]) if pd.notna(r.get("n_tx")) else None,
            }
        )
    m01 = age <= 1
    m03 = age <= 3
    m4 = age >= 4
    y03, h03, z03 = y[m03], yhat[m03], yhat0[m03]
    y4, h4, z4 = y[m4], yhat[m4], yhat0[m4]
    y01, h01, z01 = y[m01], yhat[m01], yhat0[m01]
    new_rows = [r for r in rows if r["age"] <= 3]
    new_rows.sort(key=lambda d: (d["age"], d["addr2"], d["name"]))
    err0_03 = (y03 - z03) / y03 if len(y03) else np.array([])
    err0_4 = (y4 - z4) / y4 if len(y4) else np.array([])
    prem_03 = y03 / z03 - 1.0 if len(y03) else np.array([])
    prem_4 = y4 / z4 - 1.0 if len(y4) else np.array([])
    return {
        "ok": True,
        "addr1": addr1,
        "n_pool": int(len(df)),
        "n_fit": int(fitted["n"]),
        "adj_r_squared": fitted.get("adj_r_squared"),
        "mape_in_sample": fitted.get("mape"),
        "age_coef": coef_age,
        "age_counts": {
            "0_1": int(m01.sum()),
            "0_3": int(m03.sum()),
            "4_plus": int(m4.sum()),
        },
        "summary_0_1": _summarize(y01, h01, z01),
        "summary_0_3": _summarize(y03, h03, z03),
        "summary_4_plus": _summarize(y4, h4, z4),
        "compare_0_3_vs_4plus": {
            "mannwhitney_residual_rate_age0": _mw(err0_03, err0_4),
            "mannwhitney_y_over_yhat0_minus_1": _mw(prem_03, prem_4),
        },
        "arrays": {
            "y": y.tolist(),
            "yhat": yhat.tolist(),
            "yhat0": yhat0.tolist(),
            "age": age.tolist(),
        },
        "new_0_3": new_rows,
    }


def main() -> None:
    eng = get_collective_engine()
    if eng is None:
        raise SystemExit("COLLECTIVE_DATABASE_URL 없음")
    with eng.connect() as conn:
        as_of, _ = latest_mart_snapshot(conn)
        snap = conn.execute(text(f"SELECT MAX(snapshot_ym) FROM {ATTRIBUTES_TABLE}")).scalar()
        df = pd.read_sql(
            text(
                f"""
                SELECT m.addr1, m.addr2, m.addr3, m.building_key, m.display_name,
                       m.median, m.count AS n_tx, m.building_year, m.asset_type,
                       a.match_tier, a.match_rule, a.households, a.max_floor,
                       a.parking_per_household, a.approved_year, a.attr_quality_flags
                FROM collective_building_stats m
                LEFT JOIN {ATTRIBUTES_TABLE} a
                  ON a.building_key = m.building_key
                 AND a.asset_type = m.asset_type
                 AND a.snapshot_ym = :snap
                WHERE m.as_of_month = :as_of
                  AND m.window_years = :window
                  AND m.asset_type = 'apartment'
                """
            ),
            conn,
            params={"as_of": as_of, "snap": snap, "window": WINDOW},
        )
    as_of_year = int(as_of.year)
    df = _prepare(df, as_of_year)

    sidos = []
    stacked_y, stacked_h, stacked_z, stacked_age = [], [], [], []
    all_new = []
    fails = []
    for addr1, sub in df.groupby(df["addr1"].astype(str), sort=True):
        one = fit_sido(sub.reset_index(drop=True), str(addr1))
        if not one.get("ok"):
            fails.append({"addr1": addr1, "reason": one.get("reason")})
            sidos.append({"addr1": addr1, "ok": False, "reason": one.get("reason"), "n_pool": one.get("n_pool")})
            continue
        arr = one.pop("arrays")
        stacked_y.append(np.asarray(arr["y"], dtype=float))
        stacked_h.append(np.asarray(arr["yhat"], dtype=float))
        stacked_z.append(np.asarray(arr["yhat0"], dtype=float))
        stacked_age.append(np.asarray(arr["age"], dtype=float))
        all_new.extend(one["new_0_3"])
        sm = one.get("summary_0_3") or {}
        sidos.append(
            {
                "addr1": addr1,
                "ok": True,
                "n_fit": one["n_fit"],
                "adj_r_squared": one["adj_r_squared"],
                "n_0_3": sm.get("n") or 0,
                "n_0_1": (one.get("age_counts") or {}).get("0_1"),
                "mean_residual_rate_age0": sm.get("mean_residual_rate_age0"),
                "underpred_share_age0": sm.get("underpred_share_age0"),
                "mean_y_over_yhat0_minus_1": sm.get("mean_y_over_yhat0_minus_1"),
                "ci_residual_age0": (sm.get("bootstrap_mean_residual_rate_age0_pct") or {}).get("ci95"),
                "age_coef": one.get("age_coef"),
            }
        )

    y = np.concatenate(stacked_y) if stacked_y else np.array([])
    yhat = np.concatenate(stacked_h) if stacked_h else np.array([])
    yhat0 = np.concatenate(stacked_z) if stacked_z else np.array([])
    age = np.concatenate(stacked_age) if stacked_age else np.array([])
    m01 = age <= 1
    m03 = age <= 3
    m4 = age >= 4
    y03, h03, z03 = y[m03], yhat[m03], yhat0[m03]
    y4, h4, z4 = y[m4], yhat[m4], yhat0[m4]
    y01, h01, z01 = y[m01], yhat[m01], yhat0[m01]
    err0_03 = (y03 - z03) / y03 if len(y03) else np.array([])
    err0_4 = (y4 - z4) / y4 if len(y4) else np.array([])
    prem_03 = y03 / z03 - 1.0 if len(y03) else np.array([])
    prem_4 = y4 / z4 - 1.0 if len(y4) else np.array([])

    sido_sign = []
    for s in sidos:
        if not s.get("ok"):
            continue
        n = s.get("n_0_3") or 0
        mu = s.get("mean_residual_rate_age0")
        if n and mu is not None:
            sido_sign.append({"addr1": s["addr1"], "n": n, "mean_err0": mu})
    n_pos = sum(1 for d in sido_sign if d["mean_err0"] > 0)
    n_neg = sum(1 for d in sido_sign if d["mean_err0"] < 0)

    sidos.sort(key=lambda r: -(r.get("n_0_3") or 0))
    payload = {
        "method": {
            "note": "시도마다 현재 변수로 1회 적합. 전국 한 식 없음. 잔차만 스택.",
            "window_years": WINDOW,
            "model": MODEL,
            "weight": WEIGHT,
            "variables": ["households", "max_floor", "building_age", "parking"],
            "as_of_month": as_of.isoformat(),
            "as_of_label": stats_as_of_label(as_of),
            "grain": "단지 1행 · 창 중앙값",
            "y": "창 중앙 단가(만원/㎡). 잔차율=(y-ŷ)/y",
            "age0": "적합 후 building_age만 0으로 바꿔 ŷ0",
            "fit_scope": "시도마다 1회 적합 후 잔차 스택. 전국 한 식 없음",
            "daejeon_first": "대전은 시 전체 1회 적합(구별 적합 아님)",
        },
        "national": {
            "sido_sign": {
                "n_sidos_with_new": len(sido_sign),
                "n_mean_residual_positive": n_pos,
                "n_mean_residual_negative": n_neg,
            },
            "n_fit_total": int(len(y)),
            "age_counts": {"0_1": int(m01.sum()), "0_3": int(m03.sum()), "4_plus": int(m4.sum())},
            "summary_0_1": _slim_sum(_summarize(y01, h01, z01)),
            "summary_0_3": _slim_sum(_summarize(y03, h03, z03)),
            "summary_4_plus": _slim_sum(_summarize(y4, h4, z4)),
        },
        "sidos": sidos,
    }
    payload = _merge_lab_envelope(payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    st = payload["national"]["summary_0_3"]
    print("wrote", OUT)
    print("sidos_ok", payload["national"]["sido_sign"]["n_sidos_with_new"], "fails", fails)
    print("n_0_3", st.get("n"), "mean_err0", st.get("mean_residual_rate_age0"), "under", st.get("underpred_share_age0"))
    print("ci", (st.get("bootstrap_mean_residual_rate_age0_pct") or {}).get("ci95"))


def _slim_sum(s: dict) -> dict:
    if not s or not s.get("n"):
        return {"n": s.get("n", 0) if s else 0}
    keys = (
        "n",
        "mean_residual_rate_age0",
        "median_residual_rate_age0",
        "mean_residual_rate_actual_age",
        "underpred_share_age0",
        "mean_y_over_yhat0_minus_1",
        "median_y_over_yhat0_minus_1",
        "mean_y",
        "mean_yhat0",
        "mean_yhat_actual_age",
        "bootstrap_mean_residual_rate_age0_pct",
        "bootstrap_mean_premium_vs_age0_pct",
        "wilcoxon_y_minus_yhat0_greater",
    )
    return {k: s[k] for k in keys if k in s}


def _merge_lab_envelope(payload: dict) -> dict:
    if not OUT.exists():
        return payload
    old = json.loads(OUT.read_text(encoding="utf-8"))
    for key in KEEP_LAB_KEYS:
        if key in old:
            payload[key] = old[key]
    return payload


if __name__ == "__main__":
    main()
