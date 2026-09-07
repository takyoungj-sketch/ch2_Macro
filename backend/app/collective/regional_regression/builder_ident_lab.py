"""공시지가 vs 지역 FE vs 시공사 잔차 식별 — 관리자 랩.

지역회귀 단지 그레인·변수 정의를 유지한다. 예측식·시공사 보정은 넣지 않는다.
면적·거래시점은 현재 지역회귀에 없으므로 넣지 않는다.

재실행 (backend에서):
  python -m app.collective.regional_regression.builder_ident_lab

숫자는 `docs/lab/builder_ident_run.json`의 method/fit/stability를 덮어쓴다.
verdict·next·answers는 기존 스냅샷을 유지한다(판정 문장은 사람이 고친다).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import text

from app.collective.building_stats_query import latest_mart_snapshot, stats_as_of_label
from app.collective.danji_attributes import ATTRIBUTES_TABLE
from app.collective.db import get_collective_engine
from app.collective.regional_regression.engine import (
    _assessed_land_price_sql,
    _eligible_mask,
    _flags,
)
from app.collective.regional_regression.schemas import RegionalRegressionVariables

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs" / "lab" / "builder_ident_run.json"
FEATURED_BUILDERS = [
    "현대건설",
    "HDC현대산업개발",
    "대우건설",
    "LH",
    "DL이앤씨",
    "삼성물산",
    "롯데건설",
    "GS건설",
    "한신공영",
    "금호건설",
    "부영주택",
    "포스코이앤씨",
    "한양",
    "두산건설",
]
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
    "within_gu",
    "runs",
)
WINDOW = 5
N_BOOT = 2000
SEED = 42
MIN_BUILDER_N = 30
MIN_BUILDER_REGIONS = 3


CORE = RegionalRegressionVariables(
    households=True,
    max_floor=True,
    building_age=True,
    parking=True,
    structure=False,
    builder=False,
    asset_type_dummy=False,
    assessed_land_price=False,
)
WITH_LAND = CORE.model_copy(update={"assessed_land_price": True})


def _prepare(df: pd.DataFrame, as_of_year: int) -> pd.DataFrame:
    out = df.copy()
    appr = pd.to_numeric(out["approved_year"], errors="coerce")
    by = pd.to_numeric(out["building_year"], errors="coerce")
    vintage = appr.fillna(by)
    out["building_age"] = as_of_year - vintage
    out.loc[(out["building_age"] < 0) | (out["building_age"] > 80), "building_age"] = np.nan
    for col in ("households", "max_floor", "parking_per_household", "assessed_land_price", "median"):
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
    a1 = out["addr1"].fillna("").astype(str)
    a2 = out["addr2"].fillna("").astype(str).replace("nan", "")
    out["region"] = np.where(a2.str.len() > 0, a1 + " " + a2, a1)
    bg = out["builder_group"].fillna("").astype(str).str.strip().replace({"": "(미상)", "nan": "(미상)"})
    out["builder_group"] = bg
    return out


def _core_x(work: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "households": work["households"].astype(float),
            "max_floor": work["max_floor"].astype(float),
            "building_age": work["building_age"].astype(float),
            "parking_per_household": work["parking_per_household"].astype(float),
        },
        index=work.index,
    )


def _region_dummies(work: pd.DataFrame) -> pd.DataFrame:
    dum = pd.get_dummies(work["region"].astype(str), prefix="r", drop_first=True, dtype=float)
    dum.index = work.index
    return dum


def _fit_log(y: np.ndarray, x: pd.DataFrame) -> dict:
    x_c = sm.add_constant(x, has_constant="add")
    keep = [c for c in x_c.columns if c == "const" or float(x_c[c].std(ddof=0) or 0) > 0]
    x_c = x_c[keep]
    model = sm.OLS(y, x_c, missing="drop").fit()
    fitted = np.asarray(model.fittedvalues, dtype=float)
    resid = np.asarray(model.resid, dtype=float)
    y_price = np.exp(y)
    yhat_price = np.exp(fitted)
    ape = np.abs(y_price - yhat_price) / y_price
    return {
        "model": model,
        "n": int(model.nobs),
        "k": int(model.df_model),
        "adj_r2": round(float(model.rsquared_adj), 4),
        "r2": round(float(model.rsquared), 4),
        "mape": round(float(ape.mean()) * 100, 2),
        "resid": resid,
        "index": model.model.data.row_labels,
    }


def _boot_mean_ci(arr: np.ndarray, rng: np.random.Generator) -> list[float] | None:
    if len(arr) < 2:
        return None
    means = np.array([arr[rng.integers(0, len(arr), len(arr))].mean() for _ in range(N_BOOT)])
    return [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)]


def _builder_resid_table(work: pd.DataFrame, resid: np.ndarray, rng: np.random.Generator) -> list[dict]:
    s = pd.Series(resid, index=work.index)
    rows = []
    for name, idx in work.groupby("builder_group").groups.items():
        r = s.loc[idx].to_numpy(dtype=float)
        r = r[np.isfinite(r)]
        n = int(len(r))
        if n == 0:
            continue
        regs = work.loc[idx, "region"]
        vc = regs.value_counts()
        top_share = float(vc.iloc[0] / n) if n else None
        rows.append(
            {
                "builder": str(name),
                "n": n,
                "n_regions": int(regs.nunique()),
                "mean_log_resid": round(float(r.mean()), 4),
                "median_log_resid": round(float(np.median(r)), 4),
                "sd_log_resid": round(float(r.std(ddof=1)), 4) if n > 1 else None,
                "mean_pct": round(float((np.exp(r.mean()) - 1) * 100), 2),
                "median_pct": round(float((np.exp(np.median(r)) - 1) * 100), 2),
                "mean_ci95": _boot_mean_ci(r, rng),
                "top_region_share": round(top_share, 3) if top_share is not None else None,
                "top_region": str(vc.index[0]) if len(vc) else None,
            }
        )
    rows.sort(key=lambda d: -d["n"])
    return rows


def _second_stage(resid: pd.ndarray, work: pd.DataFrame, *, with_region: bool) -> dict:
    bg = work["builder_group"].astype(str)
    counts = bg.value_counts()
    keep = set(counts[counts >= MIN_BUILDER_N].index) - {"(미상)"}
    term = bg.where(bg.isin(keep), "기타")
    dum = pd.get_dummies(term, prefix="b", drop_first=False, dtype=float)
    ref = "b_기타" if "b_기타" in dum.columns else dum.columns[0]
    dum = dum.drop(columns=[ref])
    x = dum
    if with_region:
        x = pd.concat([x, _region_dummies(work)], axis=1)
    x_c = sm.add_constant(x, has_constant="add")
    keep_c = [c for c in x_c.columns if c == "const" or float(x_c[c].std(ddof=0) or 0) > 0]
    x_c = x_c[keep_c]
    model = sm.OLS(resid, x_c, missing="drop").fit()
    coefs = []
    for col in dum.columns:
        if col not in model.params.index:
            continue
        name = col.replace("b_", "", 1)
        b = float(model.params[col])
        se = float(model.bse[col])
        p = float(model.pvalues[col])
        n = int((term == name).sum())
        n_reg = int(work.loc[term == name, "region"].nunique())
        ci = model.conf_int().loc[col]
        coefs.append(
            {
                "builder": name,
                "n": n,
                "n_regions": n_reg,
                "coef_log": round(b, 4),
                "se": round(se, 4),
                "p": float(p),
                "pct": round(float((np.exp(b) - 1) * 100), 2),
                "ci95_pct": [
                    round(float((np.exp(float(ci.iloc[0])) - 1) * 100), 2),
                    round(float((np.exp(float(ci.iloc[1])) - 1) * 100), 2),
                ],
            }
        )
    coefs.sort(key=lambda d: -d["n"])
    return {
        "n": int(model.nobs),
        "adj_r2": round(float(model.rsquared_adj), 4),
        "r2": round(float(model.rsquared), 4),
        "reference": ref.replace("b_", "", 1),
        "n_builder_dummies": len(coefs),
        "coefs": coefs,
    }


def _fit_metrics(label: str, fit: dict) -> dict:
    return {
        "model": label,
        "n": fit["n"],
        "k": fit["k"],
        "adj_r2": fit["adj_r2"],
        "r2": fit["r2"],
        "mape": fit["mape"],
    }


def _pct_ci_from_log(ci: list[float] | None) -> list[float] | None:
    if not ci or len(ci) != 2:
        return None
    return [round((math.exp(ci[0]) - 1) * 100, 1), round((math.exp(ci[1]) - 1) * 100, 1)]


def _resid_compact(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "mean_pct": row["mean_pct"],
        "median_pct": row["median_pct"],
        "sd_log_resid": row["sd_log_resid"],
        "mean_ci95_log": row["mean_ci95"],
        "mean_ci95_pct": _pct_ci_from_log(row["mean_ci95"]),
        "top_region": row["top_region"],
        "top_region_share": row["top_region_share"],
    }


def _featured_rows(stability: list[dict], resid_a: list[dict], resid_b: list[dict]) -> list[dict]:
    by_s = {r["builder"]: r for r in stability}
    by_a = {r["builder"]: r for r in resid_a}
    by_b = {r["builder"]: r for r in resid_b}
    rows = []
    for name in FEATURED_BUILDERS:
        s = by_s.get(name)
        if not s:
            continue
        a, b = s.get("land_only_pct"), s.get("land_plus_fe_pct")
        kept = (
            a is not None
            and b is not None
            and a != 0
            and ((a > 0 and b > 0) or (a < 0 and b < 0))
            and s.get("land_plus_fe_p") is not None
            and s["land_plus_fe_p"] < 0.05
        )
        rows.append(
            {
                "builder": name,
                "n": s["n"],
                "n_regions": s["n_regions"],
                "land_only_pct": s["land_only_pct"],
                "land_only_ci": s["land_only_ci"],
                "land_only_p": s["land_only_p"],
                "land_plus_fe_pct": s["land_plus_fe_pct"],
                "land_plus_fe_ci": s["land_plus_fe_ci"],
                "land_plus_fe_p": s["land_plus_fe_p"],
                "ratio_fe_over_land": s["ratio_fe_over_land"],
                "kept_after_fe": kept,
                "resid_A": _resid_compact(by_a.get(name)),
                "resid_B": _resid_compact(by_b.get(name)),
            }
        )
    return rows


def _merge_lab_envelope(payload: dict) -> dict:
    if not OUT.exists():
        return payload
    old = json.loads(OUT.read_text(encoding="utf-8"))
    for key in KEEP_LAB_KEYS:
        if key in old:
            payload[key] = old[key]
    return payload


def main() -> None:
    eng = get_collective_engine()
    if eng is None:
        raise SystemExit("COLLECTIVE_DATABASE_URL 없음")
    with eng.connect() as conn:
        as_of, _ = latest_mart_snapshot(conn)
        snap = conn.execute(text(f"SELECT MAX(snapshot_ym) FROM {ATTRIBUTES_TABLE}")).scalar()
        land_select, land_join = _assessed_land_price_sql(conn)
        df = pd.read_sql(
            text(
                f"""
                SELECT m.addr1, m.addr2, m.addr3, m.building_key, m.display_name,
                       m.median, m.count AS n_tx, m.building_year, m.asset_type,
                       a.match_tier, a.match_rule, a.households, a.max_floor,
                       a.parking_per_household, a.approved_year, a.attr_quality_flags,
                       a.builder_group,
                       {land_select}
                FROM collective_building_stats m
                LEFT JOIN {ATTRIBUTES_TABLE} a
                  ON a.building_key = m.building_key
                 AND a.asset_type = m.asset_type
                 AND a.snapshot_ym = :snap
                {land_join}
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
    elig = _eligible_mask(df, WITH_LAND)
    work = df.loc[elig].copy()
    if len(work) < 50:
        raise SystemExit(f"eligible n={len(work)}")

    y = np.log(work["median"].astype(float).to_numpy())
    x_core = _core_x(work)
    x_land = x_core.copy()
    x_land["assessed_land_price"] = work["assessed_land_price"].astype(float)
    x_reg = _region_dummies(work)

    fit_d = _fit_log(y, x_core)
    fit_a = _fit_log(y, x_land)
    fit_c = _fit_log(y, pd.concat([x_core, x_reg], axis=1))
    fit_b = _fit_log(y, pd.concat([x_land, x_reg], axis=1))

    # 잔차는 적합에 남은 행 기준. 네 모형 모두 같은 work라 행이 같아야 한다.
    for name, fit in (("A", fit_a), ("B", fit_b), ("C", fit_c), ("D", fit_d)):
        if fit["n"] != len(work):
            print("warn", name, "nobs", fit["n"], "work", len(work))

    rng = np.random.default_rng(SEED)
    builder_resid = {
        "A": _builder_resid_table(work, fit_a["resid"], rng),
        "B": _builder_resid_table(work, fit_b["resid"], rng),
        "C": _builder_resid_table(work, fit_c["resid"], rng),
        "D": _builder_resid_table(work, fit_d["resid"], rng),
    }

    stage = {
        "A_builder": _second_stage(fit_a["resid"], work, with_region=False),
        "A_builder_region": _second_stage(fit_a["resid"], work, with_region=True),
        "B_builder": _second_stage(fit_b["resid"], work, with_region=False),
        "D_builder": _second_stage(fit_d["resid"], work, with_region=False),
        "D_builder_region": _second_stage(fit_d["resid"], work, with_region=True),
    }

    def coef_map(block: dict) -> dict[str, dict]:
        return {c["builder"]: c for c in block["coefs"]}

    a0 = coef_map(stage["A_builder"])
    a1 = coef_map(stage["A_builder_region"])
    stability = []
    names = sorted(set(a0) | set(a1), key=lambda n: -(a0.get(n) or a1.get(n))["n"])
    for name in names:
        c0, c1 = a0.get(name), a1.get(name)
        if not c0:
            continue
        ratio = None
        if c0 and c1 and c0["pct"] != 0:
            ratio = round(c1["pct"] / c0["pct"], 3)
        stability.append(
            {
                "builder": name,
                "n": c0["n"],
                "n_regions": c0["n_regions"],
                "land_only_pct": c0["pct"],
                "land_only_ci": c0["ci95_pct"],
                "land_only_p": c0["p"],
                "land_plus_fe_pct": c1["pct"] if c1 else None,
                "land_plus_fe_ci": c1["ci95_pct"] if c1 else None,
                "land_plus_fe_p": c1["p"] if c1 else None,
                "ratio_fe_over_land": ratio,
                "sufficient": c0["n"] >= MIN_BUILDER_N and c0["n_regions"] >= MIN_BUILDER_REGIONS,
            }
        )

    ge30 = [s for s in stability if s["sufficient"]]
    ratios = [abs(s["ratio_fe_over_land"]) for s in ge30 if s["ratio_fe_over_land"] is not None]
    sign_keep = 0
    for s in ge30:
        a, b = s["land_only_pct"], s["land_plus_fe_pct"]
        if a is None or b is None:
            continue
        if a == 0:
            continue
        if (a > 0 and b > 0) or (a < 0 and b < 0):
            if s["land_plus_fe_p"] is not None and s["land_plus_fe_p"] < 0.05:
                sign_keep += 1

    featured = _featured_rows(ge30, builder_resid["A"], builder_resid["B"])
    payload = {
        "method": {
            "note": (
                "단지 1행·창 중앙값·log(단가). 현재 지역회귀 변수만 사용. "
                "면적·거래시점은 지역회귀에 없어 넣지 않음. 전국 동일 표본 1회 적합(hold 없음). "
                "예측식·시공사 보정은 적용하지 않음."
            ),
            "window_years": WINDOW,
            "as_of_month": as_of.isoformat(),
            "as_of_label": stats_as_of_label(as_of),
            "y": "log(단지 창 중앙 단가, 만원/㎡)",
            "core": ["households", "max_floor", "building_age", "parking_per_household"],
            "land": "assessed_land_price 원/㎡ 원값 (지역회귀와 동일)",
            "region_fe": "시군구(addr1+addr2)",
            "min_builder_n": MIN_BUILDER_N,
            "min_builder_regions": MIN_BUILDER_REGIONS,
            "n_pool": int(len(df)),
            "n_eligible": int(len(work)),
            "n_regions": int(work["region"].nunique()),
            "n_builders_raw": int(work["builder_group"].nunique()),
        },
        "fit": {
            "A_land": _fit_metrics("A", fit_a),
            "B_land_fe": _fit_metrics("B", fit_b),
            "C_fe": _fit_metrics("C", fit_c),
            "D_core": _fit_metrics("D", fit_d),
            "delta_adj_r2": {
                "B_minus_A_fe_given_land": round(fit_b["adj_r2"] - fit_a["adj_r2"], 4),
                "C_minus_D_fe_given_no_land": round(fit_c["adj_r2"] - fit_d["adj_r2"], 4),
                "A_minus_D_land_given_no_fe": round(fit_a["adj_r2"] - fit_d["adj_r2"], 4),
                "B_minus_C_land_given_fe": round(fit_b["adj_r2"] - fit_c["adj_r2"], 4),
            },
        },
        "second_stage": {
            "A_resid_on_builder": {
                "adj_r2": stage["A_builder"]["adj_r2"],
                "n_dummies": stage["A_builder"]["n_builder_dummies"],
                "reference": stage["A_builder"]["reference"],
            },
            "A_resid_on_builder_region": {
                "adj_r2": stage["A_builder_region"]["adj_r2"],
                "n_dummies": stage["A_builder_region"]["n_builder_dummies"],
                "reference": stage["A_builder_region"]["reference"],
            },
            "B_resid_on_builder": {
                "adj_r2": stage["B_builder"]["adj_r2"],
                "n_dummies": stage["B_builder"]["n_builder_dummies"],
            },
        },
        "stability_land_then_fe": stability[:40],
        "stability_sufficient": ge30,
        "stability_summary": {
            "n_builders_ge30_ge3regions": len(ge30),
            "median_abs_ratio_fe_over_land": round(float(np.median(ratios)), 3) if ratios else None,
            "n_sign_and_p05_after_fe": sign_keep,
        },
        "builder_resid_A_top": [r for r in builder_resid["A"] if r["n"] >= MIN_BUILDER_N][:25],
        "builder_resid_B_top": [r for r in builder_resid["B"] if r["n"] >= MIN_BUILDER_N][:25],
        "featured": featured,
    }
    payload = _merge_lab_envelope(payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("n", len(work), "regions", work["region"].nunique())
    print("fit", payload["fit"])
    print("stability_summary", payload["stability_summary"])


if __name__ == "__main__":
    main()
