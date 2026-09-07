"""시공사 효과 2차 — 시군구 내부(within-gu) 식별.

제품 지역회귀와 같이 구마다 핵심+공시지가 log OLS를 적합한다(구별 기울기).
전국 한 식 + 시군구 FE(1차 모형 B)와 질문이 다르다.

재실행 (backend에서):
  python -m app.collective.regional_regression.builder_within_gu_lab

결과는 `docs/lab/builder_ident_run.json`의 within_gu를 덮어쓴다.
1차 fit·verdict 문장은 유지하되, next.within-gu 상태와 2차 판정 블록은 이 스크립트가 갱신한다.
예측식은 바꾸지 않는다.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.collective.building_stats_query import latest_mart_snapshot, stats_as_of_label
from app.collective.danji_attributes import ATTRIBUTES_TABLE
from app.collective.db import get_collective_engine
from app.collective.regional_regression.builder_ident_lab import (
    FEATURED_BUILDERS,
    MIN_BUILDER_N,
    MIN_BUILDER_REGIONS,
    OUT,
    SEED,
    WINDOW,
    WITH_LAND,
    _eligible_mask,
    _prepare,
    _second_stage,
)
from app.collective.regional_regression.engine import (
    MIN_FIT_N,
    _assessed_land_price_sql,
    _design,
    _fit_ols,
)

MIN_CELL = 5
N_BOOT = 2000


def _boot_mean_ci(arr: np.ndarray, rng: np.random.Generator) -> list[float] | None:
    if len(arr) < 2:
        return None
    means = np.array([arr[rng.integers(0, len(arr), len(arr))].mean() for _ in range(N_BOOT)])
    return [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)]


def _pct(log_v: float | None) -> float | None:
    if log_v is None or not np.isfinite(log_v):
        return None
    return round(float((math.exp(log_v) - 1) * 100), 2)


def _ci_pct(ci_log: list[float] | None) -> list[float] | None:
    if not ci_log or len(ci_log) != 2:
        return None
    return [_pct(ci_log[0]), _pct(ci_log[1])]  # type: ignore[list-item]


def _load_work() -> tuple[pd.DataFrame, object]:
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
    prepared = _prepare(df, int(as_of.year))
    work = prepared.loc[_eligible_mask(prepared, WITH_LAND)].copy()
    return work, as_of


def main() -> None:
    work, as_of = _load_work()
    rng = np.random.default_rng(SEED)
    rows: list[dict] = []
    gu_fit: list[dict] = []
    skipped = 0
    adj_list: list[float] = []

    for region, sub in work.groupby("region", sort=False):
        sub = sub.copy()
        if len(sub) < MIN_FIT_N:
            skipped += 1
            continue
        x, _labels, _w = _design(sub, WITH_LAND)
        fitted = _fit_ols(sub, x, model_type="log", weight_mode="equal", train_idx=sub.index, hold_idx=None)
        if fitted is None:
            skipped += 1
            continue
        idx = fitted["work_index"]
        resid = np.asarray(fitted["model"].resid, dtype=float)
        if len(resid) != len(idx):
            skipped += 1
            continue
        adj = fitted.get("adj_r_squared")
        if adj is not None:
            adj_list.append(float(adj))
        gu_fit.append(
            {
                "region": str(region),
                "n": int(fitted["n"]),
                "adj_r2": round(float(adj), 4) if adj is not None else None,
                "mape": fitted.get("mape"),
            }
        )
        bg = sub.loc[idx, "builder_group"].astype(str).to_numpy()
        for i, pos in enumerate(idx):
            rows.append(
                {
                    "region": str(region),
                    "builder": str(bg[i]),
                    "log_resid": float(resid[i]),
                    "building_key": str(sub.loc[pos, "building_key"]),
                }
            )

    stacked = pd.DataFrame(rows)
    if stacked.empty:
        raise SystemExit("within-gu 적합 단지가 없습니다")

    work_st = stacked.rename(columns={"builder": "builder_group"}).copy()
    stage = _second_stage(stacked["log_resid"].to_numpy(), work_st, with_region=False)

    featured_from_snap: dict[str, dict] = {}
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8"))
        featured_from_snap = {r["builder"]: r for r in old.get("featured") or []}

    builders = []
    for name, g in stacked.groupby("builder"):
        r = g["log_resid"].to_numpy(dtype=float)
        r = r[np.isfinite(r)]
        n = int(len(r))
        if n == 0:
            continue
        cells = []
        for region, gg in g.groupby("region"):
            rr = gg["log_resid"].to_numpy(dtype=float)
            rr = rr[np.isfinite(rr)]
            if len(rr) < MIN_CELL:
                continue
            cells.append({"region": str(region), "n": int(len(rr)), "mean_log": float(rr.mean())})
        cell_means = np.array([c["mean_log"] for c in cells], dtype=float) if cells else np.array([])
        n_pos = int((cell_means > 0).sum()) if len(cell_means) else 0
        ci_log = _boot_mean_ci(r, rng)
        builders.append(
            {
                "builder": str(name),
                "n": n,
                "n_regions": int(g["region"].nunique()),
                "n_cells": len(cells),
                "mean_log": round(float(r.mean()), 4),
                "median_log": round(float(np.median(r)), 4),
                "sd_log": round(float(r.std(ddof=1)), 4) if n > 1 else None,
                "mean_pct": _pct(float(r.mean())),
                "median_pct": _pct(float(np.median(r))),
                "mean_ci95_log": ci_log,
                "mean_ci95_pct": _ci_pct(ci_log),
                "gu_median_pct": _pct(float(np.median(cell_means))) if len(cell_means) else None,
                "share_gu_positive": round(n_pos / len(cell_means), 3) if len(cell_means) else None,
                "sufficient": n >= MIN_BUILDER_N and len(cells) >= MIN_BUILDER_REGIONS,
            }
        )
    builders.sort(key=lambda d: -d["n"])

    by_b = {b["builder"]: b for b in builders}
    stage_map = {c["builder"]: c for c in stage["coefs"]}
    featured = []
    for name in FEATURED_BUILDERS:
        w = by_b.get(name)
        snap = featured_from_snap.get(name) or {}
        if not w:
            continue
        land_fe = snap.get("land_plus_fe_pct")
        within = w["mean_pct"]
        ratio = None
        if land_fe not in (None, 0) and within is not None:
            ratio = round(within / land_fe, 3)
        ci = w.get("mean_ci95_pct") or [None, None]
        excludes0 = bool(ci[0] is not None and ci[1] is not None and not (ci[0] <= 0 <= ci[1]))
        same_sign = (
            land_fe is not None
            and within is not None
            and land_fe != 0
            and ((land_fe > 0 and within > 0) or (land_fe < 0 and within < 0))
        )
        featured.append(
            {
                "builder": name,
                "n": w["n"],
                "n_regions": w["n_regions"],
                "n_cells": w["n_cells"],
                "land_plus_fe_pct": land_fe,
                "land_plus_fe_ci": snap.get("land_plus_fe_ci"),
                "within_pct": within,
                "within_ci": w["mean_ci95_pct"],
                "within_gu_median_pct": w["gu_median_pct"],
                "share_gu_positive": w["share_gu_positive"],
                "ratio_within_over_fe": ratio,
                "gamma_vs_etc_pct": (stage_map.get(name) or {}).get("pct"),
                "gamma_vs_etc_p": (stage_map.get(name) or {}).get("p"),
                "kept": bool(same_sign and excludes0 and w["sufficient"]),
                "within_nonzero": excludes0,
            }
        )

    kept_n = sum(1 for f in featured if f["kept"])
    n_within_nonzero = sum(1 for f in featured if f.get("within_nonzero"))
    ratios = [abs(f["ratio_within_over_fe"]) for f in featured if f.get("ratio_within_over_fe") is not None]
    payload_within = {
        "date": "2026-09-07",
        "decision": "D-065",
        "method": {
            "note": (
                "시군구마다 제품과 같은 핵심+공시지가 log OLS(equal). "
                "잔차는 구 안 기울기 이후. MIN_FIT_N=20, 셀 n≥5."
            ),
            "as_of_label": stats_as_of_label(as_of),
            "as_of_month": as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of),
            "min_gu_n": MIN_FIT_N,
            "min_cell": MIN_CELL,
            "min_builder_n": MIN_BUILDER_N,
            "min_builder_cells": MIN_BUILDER_REGIONS,
            "n_eligible": int(len(work)),
            "n_gu_fit": len(gu_fit),
            "n_gu_skipped": skipped,
            "n_stacked": int(len(stacked)),
            "median_gu_adj_r2": round(float(np.median(adj_list)), 4) if adj_list else None,
        },
        "second_stage": {
            "within_resid_on_builder": {
                "adj_r2": stage["adj_r2"],
                "n_dummies": stage["n_builder_dummies"],
                "reference": stage["reference"],
            }
        },
        "summary": {
            "n_featured": len(featured),
            "n_kept": kept_n,
            "n_within_nonzero": n_within_nonzero,
            "median_abs_ratio_within_over_fe": round(float(np.median(ratios)), 3) if ratios else None,
        },
        "featured": featured,
        "builder_top": [b for b in builders if b["n"] >= MIN_BUILDER_N][:25],
        "verdict": {
            "code": "exists_but_id_unstable",
            "label": "구 안에서도 잔차는 남으나, 전국 FE γ와 불일치해 식에는 아직 넣지 않음",
            "product_formula": "do_not_add",
            "note": (
                "제품 그레인(구별 기울기)에서는 현대·HDC·LH·포스코 등이 남고, "
                "삼성·GS는 전국 FE에선 0이었다가 구 안에선 +. "
                "한신은 단지 가중 vs 구 중앙이 갈림. 전국 공통 γ를 제품에 넣을 수 없다."
            ),
        },
    }

    snap = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    snap["within_gu"] = payload_within
    for item in snap.get("next") or []:
        if item.get("id") == "within-gu":
            item["status"] = "done"
            item["ask"] = (
                f"구 안 적합 후 시공사 잔차. 주요 {len(featured)}곳 중 CI가 0을 제외하고 "
                f"1차 공시+FE와 부호가 같은 곳 {kept_n}곳."
            )
            item["gate"] = "완료. D-065. 전국 공통 γ는 여전히 금지. 다음은 브랜드 분리."
        elif item.get("id") == "brand-vs-builder":
            item["gate"] = "다음. 삼성 구 안 잔차가 브랜드인지 시공사인지 가른다. D-045."
        elif item.get("id") == "product-formula":
            item["gate"] = "within-gu는 했으나 식별이 불안정. 브랜드 분리 전 금지. D-065."
    snap.setdefault("runs", []).append({"id": "within-gu", "date": "2026-09-07", "decision": "D-065"})
    # de-dup runs
    seen = set()
    runs = []
    for r in snap.get("runs") or []:
        k = r.get("id")
        if k in seen:
            continue
        seen.add(k)
        runs.append(r)
    snap["runs"] = runs
    OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("gu_fit", len(gu_fit), "skipped", skipped, "stacked", len(stacked))
    print("stage adj_r2", stage["adj_r2"], "kept", kept_n, "/", len(featured))
    for f in featured:
        print(f["builder"], "fe", f["land_plus_fe_pct"], "within", f["within_pct"], "kept", f["kept"])


if __name__ == "__main__":
    main()
