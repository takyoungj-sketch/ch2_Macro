# -*- coding: utf-8 -*-
"""2차: 1차에서 원가 폭 밖에 남은 칸만 맞춰 본다.

맞춤 키는 계약연도, 대지면적, 도로구간, 개별공시지가다.
공시지가는 입지를 맞추는 데만 쓰고 계수로 읽지 않는다.
칸 안에서는 지역·용도지역이 같으므로 그 더미는 식에 넣지 않는다.
결과는 docs/lab/land_built_alloc_gap_stage2.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.built.db import get_built_engine
from app.db import engine as land_engine
from app.land_lab.built_land_gap_stage1 import (
    OUT as STAGE1,
    allocate_three,
    canon_any,
    gap,
    leaf_name,
    load_bands,
    resolve_cost,
)
from app.region_canonical import region_codes_join_on_canonical

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "land_built_alloc_gap_stage2.json"
# 같은 연도·같은 도로에서 면적과 공시지가가 1.5배를 넘으면 짝을 짓지 않는다.
CALIPER = math.log(1.5)
MIN_PAIRS = 15
ASSESSED_COVERAGE = 0.70
ROADS = ("8미만", "12미만", "25미만", "25이상")


def road_bucket(raw: object) -> str:
    s = str(raw or "").strip().replace(" ", "").replace("m", "").replace("M", "")
    return s if s in ROADS else ""


def _finite_pos(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(number) and number > 0:
        return number
    return None


def _median(values: np.ndarray) -> float | None:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return None
    return float(np.median(clean))


def _coverage(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    return float(np.mean(np.isfinite(values) & (values > 0)))


def match_pairs(land: pd.DataFrame, built: pd.DataFrame, use_assessed: bool) -> list[tuple[int, int]]:
    """같은 연도·도로, 면적·공시지가 1.5배 이내. 비용 최소 배정."""
    if land.empty or built.empty:
        return []
    land_i = land.index.to_numpy()
    built_i = built.index.to_numpy()
    cost = np.full((len(built_i), len(land_i)), 1.0e6)
    l_year = land.year.to_numpy()
    b_year = built.year.to_numpy()
    l_road = land.road.to_numpy()
    b_road = built.road.to_numpy()
    l_area = np.log(land.area.to_numpy(dtype=float))
    b_area = np.log(built.area.to_numpy(dtype=float))
    l_ass = np.log(land.assessed.to_numpy(dtype=float)) if use_assessed else None
    b_ass = np.log(built.assessed.to_numpy(dtype=float)) if use_assessed else None
    for i in range(len(built_i)):
        for j in range(len(land_i)):
            if b_year[i] != l_year[j] or b_road[i] != l_road[j] or not b_road[i]:
                continue
            area_gap = abs(float(b_area[i] - l_area[j]))
            if area_gap > CALIPER:
                continue
            extra = 0.0
            if use_assessed:
                if not math.isfinite(b_ass[i]) or not math.isfinite(l_ass[j]):
                    continue
                price_gap = abs(float(b_ass[i] - l_ass[j]))
                if price_gap > CALIPER:
                    continue
                extra = price_gap
            cost[i, j] = area_gap + extra
    try:
        from scipy.optimize import linear_sum_assignment

        rows, cols = linear_sum_assignment(cost)
        chosen = [(int(built_i[i]), int(land_i[j])) for i, j in zip(rows, cols) if cost[i, j] < 1.0e5]
    except Exception:
        chosen = _greedy(cost, built_i, land_i)
    return chosen


def _greedy(cost: np.ndarray, built_i: np.ndarray, land_i: np.ndarray) -> list[tuple[int, int]]:
    pairs = [
        (float(cost[i, j]), i, j)
        for i in range(cost.shape[0])
        for j in range(cost.shape[1])
        if cost[i, j] < 1.0e5
    ]
    pairs.sort()
    used_b: set[int] = set()
    used_l: set[int] = set()
    out = []
    for _, i, j in pairs:
        if i in used_b or j in used_l:
            continue
        used_b.add(i)
        used_l.add(j)
        out.append((int(built_i[i]), int(land_i[j])))
    return out


def _t_crit(df: int) -> float:
    table = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 8: 2.31, 10: 2.23, 15: 2.13, 20: 2.09, 30: 2.04, 40: 2.02, 60: 2.00}
    if df <= 0:
        return table[1]
    keys = sorted(table)
    if df >= keys[-1]:
        return 1.96
    lo = max(k for k in keys if k <= df)
    hi = min(k for k in keys if k >= df)
    if lo == hi:
        return table[lo]
    w = (df - lo) / (hi - lo)
    return table[lo] * (1 - w) + table[hi] * w


def ols_land_only(frame: pd.DataFrame, price_col: str) -> dict:
    """ln(P) = a + b LandOnly + c ln(area) + 도로 + 연도. HC3."""
    work = frame[np.isfinite(frame[price_col]) & (frame[price_col] > 0)].copy()
    n = len(work)
    if n < MIN_PAIRS * 2:
        return {"status": "맞춤 표본이 작다", "n": n}
    y = np.log(work[price_col].to_numpy(dtype=float))
    land_only = work.land_only.to_numpy(dtype=float)
    log_area = np.log(work.area.to_numpy(dtype=float))
    columns = [np.ones(n), land_only, log_area]
    names = ["intercept", "land_only", "log_area"]
    roads = [r for r in ROADS if (work.road == r).any()]
    for road in roads[1:]:
        columns.append((work.road == road).to_numpy(dtype=float))
        names.append(f"road_{road}")
    years = sorted(int(v) for v in work.year.dropna().unique())
    for year in years[1:]:
        columns.append((work.year == year).to_numpy(dtype=float))
        names.append(f"year_{year}")
    x = np.column_stack(columns)
    keep = [i for i in range(x.shape[1]) if i < 3 or float(np.nanstd(x[:, i])) > 0]
    x = x[:, keep]
    names = [names[i] for i in keep]
    k = x.shape[1]
    if n < k + 8 or np.linalg.matrix_rank(x, tol=1e-8) < k:
        return {"status": "맞춤 표본이 작다", "n": n, "k": k}
    xtx = x.T @ x
    try:
        xtx_inv = np.linalg.inv(xtx)
    except np.linalg.LinAlgError:
        return {"status": "식을 추정하지 못함", "n": n, "k": k}
    beta = xtx_inv @ (x.T @ y)
    resid = y - x @ beta
    hat = np.sum((x @ xtx_inv) * x, axis=1)
    if np.any(hat >= 0.99):
        weight = resid**2 * (n / (n - k))
        cov_name = "HC1"
    else:
        weight = (resid / (1.0 - hat)) ** 2
        cov_name = "HC3"
    meat = x.T @ (x * weight[:, None])
    cov = xtx_inv @ meat @ xtx_inv
    se = float(math.sqrt(max(0.0, float(cov[1, 1]))))
    b = float(beta[1])
    pct = 100.0 * (math.exp(b) - 1.0)
    se_pct = 100.0 * math.exp(b) * se
    crit = _t_crit(n - k)
    lo = pct - crit * se_pct
    hi = pct + crit * se_pct
    return {
        "status": "estimated",
        "n": n,
        "n_land": int(land_only.sum()),
        "n_built": int(n - land_only.sum()),
        "k": k,
        "cov": cov_name,
        "beta_land_only": round(b, 4),
        "pct_vs_allocated": round(pct, 1),
        "ci95": [round(lo, 1), round(hi, 1)],
        "includes_zero": bool(lo <= 0 <= hi),
    }


def prepare_side(frame: pd.DataFrame, area_col: str, year_col: str, road_col: str, assessed_col: str) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "year": pd.to_numeric(frame[year_col], errors="coerce"),
            "area": pd.to_numeric(frame[area_col], errors="coerce"),
            "road": frame[road_col].map(road_bucket),
            "assessed": pd.to_numeric(frame[assessed_col], errors="coerce"),
        }
    )
    out = out[np.isfinite(out.year) & np.isfinite(out.area) & (out.area > 0) & (out.road != "")]
    out["year"] = out.year.astype(int)
    return out


def cell_result(cell: dict, land: pd.DataFrame, built: pd.DataFrame) -> dict:
    land_s = prepare_side(land, "area_sqm", "contract_year", "road", "assessed")
    built_s = prepare_side(built, "land_area", "contract_year", "road_width_label", "assessed")
    land_cov = _coverage(land_s.assessed.to_numpy(dtype=float)) if len(land_s) else 0.0
    built_cov = _coverage(built_s.assessed.to_numpy(dtype=float)) if len(built_s) else 0.0
    use_assessed = land_cov >= ASSESSED_COVERAGE and built_cov >= ASSESSED_COVERAGE
    land_med = _median(land_s.assessed.to_numpy(dtype=float))
    built_med = _median(built_s.assessed.to_numpy(dtype=float))
    unit_note = "둘 다 원/㎡"
    if use_assessed and land_med and built_med:
        ratio = built_med / land_med
        if not (0.2 <= ratio <= 5.0):
            use_assessed = False
            unit_note = f"공시지가 중앙 비가 {ratio:.2f}라 맞춤에서 뺐다"
    pairs = match_pairs(land_s, built_s, use_assessed)
    matched_rows = []
    for pair_id, (b_idx, l_idx) in enumerate(pairs):
        b_row = built.loc[b_idx]
        l_row = land.loc[l_idx]
        base = {
            "pair_id": pair_id,
            "year": int(land_s.loc[l_idx, "year"]),
            "road": land_s.loc[l_idx, "road"],
        }
        matched_rows.append(
            {
                **base,
                "land_only": 1.0,
                "area": float(l_row.area_sqm),
                "price_mid": float(l_row.unit_price),
                "price_low_cost": float(l_row.unit_price),
                "price_high_cost": float(l_row.unit_price),
            }
        )
        matched_rows.append(
            {
                **base,
                "land_only": 0.0,
                "area": float(b_row.land_area),
                "price_mid": _finite_pos(b_row.unit_mid),
                "price_low_cost": _finite_pos(b_row.unit_low_cost),
                "price_high_cost": _finite_pos(b_row.unit_high_cost),
            }
        )
    matched = pd.DataFrame(matched_rows)
    models = {}
    matched_d = {}
    if matched.empty:
        models = {key: {"status": "맞춤 쌍이 없다", "n": 0} for key in ("mid", "low_cost", "high_cost")}
    else:
        for key, col in (("mid", "price_mid"), ("low_cost", "price_low_cost"), ("high_cost", "price_high_cost")):
            present = matched[col].map(lambda v: _finite_pos(v) is not None)
            part = matched.loc[present].copy()
            both = part.groupby("pair_id").size()
            part = part[part.pair_id.isin(both[both == 2].index)].copy()
            part[col] = part[col].astype(float)
            models[key] = ols_land_only(part, col)
            land_p = part.loc[part.land_only == 1, col].to_numpy(dtype=float)
            built_p = part.loc[part.land_only == 0, col].to_numpy(dtype=float)
            matched_d[key] = None if land_p.size == 0 or built_p.size == 0 else round(gap(float(np.median(land_p)), float(np.median(built_p))), 1)
            models[key]["n_pairs"] = int(land_p.size)
    mid = models["mid"]
    signs = []
    for key in ("low_cost", "mid", "high_cost"):
        pct = models[key].get("pct_vs_allocated")
        if models[key].get("status") != "estimated" or pct is None:
            signs.append(None)
        else:
            signs.append(1 if pct > 0 else (-1 if pct < 0 else 0))
    if any(item is None for item in signs) or len(set(signs)) != 1:
        verdict = "유보" if pairs else "맞춤 쌍이 없다"
        if mid.get("status") != "estimated":
            verdict = mid.get("status") or "추정 불가"
    elif mid.get("includes_zero"):
        verdict = "맞춤 뒤 표본으로 구분되지 않음"
    else:
        verdict = "맞춤 뒤에도 남음"
    return {
        "sido": cell["sido"],
        "sigungu": cell["sigungu"],
        "emd": cell["emd"],
        "zone": cell["zone"],
        "stage1_d_mid": cell["d_mid"],
        "stage1_verdict": cell["verdict"],
        "n_land_in_cell": int(len(land)),
        "n_built_in_cell": int(len(built)),
        "n_land_with_road": int(len(land_s)),
        "n_built_with_road": int(len(built_s)),
        "assessed_coverage_land": round(land_cov, 3),
        "assessed_coverage_built": round(built_cov, 3),
        "assessed_used": use_assessed,
        "assessed_median_land_won": None if land_med is None else round(land_med, 1),
        "assessed_median_built_won": None if built_med is None else round(built_med, 1),
        "assessed_unit_note": unit_note,
        "n_pairs": len(pairs),
        "matched_d": matched_d,
        "models": models,
        "verdict": verdict,
    }


def allocate_frame(built: pd.DataFrame, bands: dict) -> pd.DataFrame:
    uses = {use for use, _ in bands}
    low_u, mid_u, high_u = [], [], []
    for row in built.itertuples(index=False):
        use = str(row.building_use or "").strip()
        structure = str(row.structure_group or "").strip()
        cost = resolve_cost(use, structure, bands) if use in uses else None
        age = None
        if cost is not None and pd.notna(row.building_age):
            age = max(0.0, float(row.building_age))
        elif cost is not None and pd.notna(row.approve_year) and pd.notna(row.contract_year) and 1900 <= int(row.approve_year) <= 2100:
            age = max(0.0, float(int(row.contract_year) - int(row.approve_year)))
        if cost is None:
            low_u.append(np.nan)
            mid_u.append(np.nan)
            high_u.append(np.nan)
            continue
        a, b, c = allocate_three(float(row.price), float(row.gross_area), float(row.land_area), age, cost)
        low_u.append(np.nan if a is None else a)
        mid_u.append(np.nan if b is None else b)
        high_u.append(np.nan if c is None else c)
    built = built.copy()
    built["unit_low_cost"] = low_u
    built["unit_mid"] = mid_u
    built["unit_high_cost"] = high_u
    built["leaf"] = [leaf_name(a, b) for a, b in zip(built.addr3, built.addr4)]
    built["zone"] = built.zone_type.map(canon_any)
    return built


def main() -> None:
    stage1 = json.loads(STAGE1.read_text(encoding="utf-8"))
    cells = [c for c in stage1["cells"] if c.get("verdict") == "원가 폭 밖에 남음"]
    if not cells:
        raise RuntimeError("2차 대상 칸이 없다.")
    bands = load_bands()
    start = stage1["period_start"]
    end = stage1["period_end"]
    names = sorted({c["emd"] for c in cells})
    built_engine = get_built_engine()
    if built_engine is None:
        raise RuntimeError("복합 DB 엔진이 없다.")
    name_params = {f"n{i}": name for i, name in enumerate(names)}
    in_sql = ", ".join(f":n{i}" for i in range(len(names)))
    built_sql = text(
        f"""
        SELECT t.id, t.addr1, t.addr2, t.addr3, t.addr4, t.zone_type, t.building_use,
               t.price::float8 AS price, t.gross_area::float8 AS gross_area,
               t.land_area::float8 AS land_area, t.building_age::float8 AS building_age,
               t.contract_year::int AS contract_year, t.road_width_label,
               e.structure_group, e.approve_year::int AS approve_year,
               e.assessed_land_price::float8 AS assessed
        FROM built_transactions t
        LEFT JOIN built_transaction_enrichment e
          ON e.transaction_hash = t.transaction_hash
         AND e.supply_hold IS NULL
        WHERE t.contract_date >= :p_start
          AND t.contract_date <= :p_end
          AND t.is_partial_ownership IS NOT TRUE
          AND t.price > 0
          AND t.land_area > 0
          AND t.gross_area > 0
          AND (btrim(t.addr3::text) IN ({in_sql}) OR btrim(t.addr4::text) IN ({in_sql}))
        """
    )
    params = {"p_start": start, "p_end": end, **name_params}
    built = pd.read_sql(built_sql, built_engine, params=params)
    built = built.drop_duplicates(subset=["id"])
    built = allocate_frame(built, bands)
    built = built[np.isfinite(built.unit_mid)].copy()
    print(f"built rows in target names {len(built)}", flush=True)

    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    wheres = []
    land_params = {"p_start": start, "p_end": end}
    for i, cell in enumerate(cells):
        wheres.append(
            f"(btrim(r.sido_name::text) = :s{i} AND btrim(r.sigungu_name::text) = :g{i} AND btrim(r.eupmyeondong_name::text) = :e{i})"
        )
        land_params[f"s{i}"] = cell["sido"]
        land_params[f"g{i}"] = cell["sigungu"]
        land_params[f"e{i}"] = cell["emd"]
    land_sql = text(
        f"""
        SELECT lt.id::bigint AS id,
               btrim(r.sido_name::text) AS sido,
               btrim(r.sigungu_name::text) AS sigungu,
               btrim(r.eupmyeondong_name::text) AS emd,
               btrim(lt.zone_type_resolved::text) AS zone,
               lt.contract_year::int AS contract_year,
               lt.area_sqm::float8 AS area_sqm,
               lt.unit_price_per_sqm::float8 AS unit_price,
               lt.road_condition AS road,
               tl.official_price_won::float8 AS assessed
        FROM land_transactions_resolved lt
        {join_sql}
        LEFT JOIN land_transaction_trait_link tl
          ON tl.transaction_hash = lt.transaction_hash
        WHERE lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.unit_price_per_sqm > 0
          AND btrim(lt.land_category_resolved::text) = '대'
          AND ({' OR '.join(wheres)})
        """
    )
    with land_engine.connect() as conn:
        land = pd.read_sql(land_sql, conn, params=land_params)
    land = land.drop_duplicates(subset=["id"])
    land["zone"] = land.zone.map(canon_any)
    print(f"land rows {len(land)}", flush=True)

    results = []
    for cell in cells:
        land_part = land[
            (land.sido == cell["sido"])
            & (land.sigungu == cell["sigungu"])
            & (land.emd == cell["emd"])
            & (land.zone == cell["zone"])
        ].copy()
        built_part = built[
            (built.addr1.fillna("").str.strip() == cell["sido"])
            & (built.addr2.fillna("").str.strip() == cell["sigungu"])
            & (built.leaf == cell["emd"])
            & (built.zone == cell["zone"])
        ].copy()
        results.append(cell_result(cell, land_part.reset_index(drop=True), built_part.reset_index(drop=True)))
        print(cell["emd"], results[-1]["n_pairs"], results[-1]["verdict"], flush=True)

    payload = {
        "stage": 2,
        "period_start": start,
        "period_end": end,
        "caliper": "같은 연도, 같은 도로구간, 면적·공시지가 각각 1.5배 이내",
        "formula": "ln(㎡당 가격) = 절편 + LandOnly + ln(대지면적) + 도로 + 연도",
        "pct_meaning": "100(exp(beta)-1)은 배분단가 대비 토지 단독거래가 높은 비율이다. 1차 D는 토지 단독거래 대비라 분모가 다르다.",
        "notes": [
            "토지 단독거래는 확인된 나지가 아니다.",
            "개별공시지가는 맞춤 키이고 원인 계수가 아니다.",
            "칸 안에서는 지역과 용도지역이 같아 더미를 넣지 않았다.",
            "부호가 원가 하한·기준·상한에서 갈리면 유보한다.",
        ],
        "cells": results,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
