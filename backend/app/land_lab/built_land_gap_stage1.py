# -*- coding: utf-8 -*-
"""1차: 토지 단독거래 단가와 건부지 배분단가.

제품 원장과 간이 신축원가표 기본값은 읽기만 한다.
결과는 docs/lab/land_built_alloc_gap_stage1.json
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.built.db import get_built_engine
from app.built.time_scope import period_bounds_for_window
from app.db import engine as land_engine
from app.land_lab.area_elasticity_screen import latest_as_of_month
from app.land_lab.road_jimok_ratio import ZONE_LABEL, canonical_zone
from app.region_canonical import region_codes_join_on_canonical

ROOT = Path(__file__).resolve().parents[3]
DEFAULTS_TS = ROOT / "frontend-built" / "src" / "utils" / "allocationDefaults.ts"
OUT = ROOT / "docs" / "lab" / "land_built_alloc_gap_stage1.json"
MIN_N = 20
BAND_N = 10
BOOT = 2000
SEED = 20261103
MIN_RESIDUAL = 0.1
AREA_BINS = (
    (0.0, 100.0, "100㎡ 미만"),
    (100.0, 200.0, "100~200㎡"),
    (200.0, 300.0, "200~300㎡"),
    (300.0, 500.0, "300~500㎡"),
    (500.0, math.inf, "500㎡ 이상"),
)
STRATA = ("서울", "경기·인천", "광역시", "그 외 시", "읍·면")
LABEL_TO_CODE = {label: code for code, label in ZONE_LABEL.items()}


def canon_any(raw: object) -> str:
    s = str(raw or "").strip().replace(" ", "")
    if not s or s == "nan":
        return ""
    aliased = canonical_zone(s)
    if aliased != s:
        return aliased
    trimmed = s[1:] if s.startswith("제") else s
    for suffix in ("지역", "구역"):
        if trimmed.endswith(suffix):
            trimmed = trimmed[: -len(suffix)]
    if trimmed in LABEL_TO_CODE:
        return LABEL_TO_CODE[trimmed]
    if s in LABEL_TO_CODE:
        return LABEL_TO_CODE[s]
    return s
METRO = ("부산", "대구", "광주", "대전", "울산")


def _median_py(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (float(ordered[mid - 1]) + float(ordered[mid])) / 2


def _quantile(values: np.ndarray, p: float) -> float | None:
    if values.size == 0:
        return None
    ordered = np.sort(values)
    if ordered.size == 1:
        return float(ordered[0])
    k = (ordered.size - 1) * p
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return float(ordered[lo])
    return float(ordered[lo] * (hi - k) + ordered[hi] * (k - lo))


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def load_bands() -> dict[tuple[str, str], tuple[float, float, float]]:
    text_src = DEFAULTS_TS.read_text(encoding="utf-8")
    rows = re.findall(
        r'use:\s*"([^"]+)",\s*structure:\s*"([^"]+)",\s*low:\s*([0-9.]+),\s*high:\s*([0-9.]+),\s*life:\s*([0-9.]+)',
        text_src,
    )
    if len(rows) != 112:
        raise RuntimeError(f"원가표 기본값 {len(rows)}개. 112개여야 한다.")
    return {(use, structure): (float(low), float(high), float(life)) for use, structure, low, high, life in rows}


def envelope(use: str, bands: dict[tuple[str, str], tuple[float, float, float]]) -> tuple[float, float, float] | None:
    rows = [band for (u, _), band in bands.items() if u == use]
    if not rows:
        return None
    life_mid = _median_py([life for _, _, life in rows])
    life = life_mid if float(life_mid).is_integer() else float(_round_half_up(life_mid / 5.0) * 5)
    return (min(low for low, _, _ in rows), max(high for _, high, _ in rows), life)


def resolve_cost(use: str, structure: str, bands: dict) -> tuple[float, float, float] | None:
    if structure and (use, structure) in bands:
        return bands[(use, structure)]
    if structure:
        return None
    return envelope(use, bands)


def allocate_three(
    price: float,
    gross: float,
    land: float,
    age: float | None,
    cost: tuple[float, float, float],
) -> tuple[float | None, float | None, float | None]:
    low, high, life = cost
    if life <= 0:
        return None, None, None
    if age is None:
        residual = MIN_RESIDUAL
    else:
        residual = max(MIN_RESIDUAL, 1.0 - max(0.0, age) / life)
    out = []
    for unit_cost in (low, (low + high) / 2.0, high):
        land_unit = (price - gross * unit_cost * residual) / land
        out.append(land_unit if land_unit > 0 else None)
    # 원가 하한 → 배분단가 높음, 원가 상한 → 배분단가 낮음
    return out[0], out[1], out[2]


def leaf_name(addr3: object, addr4: object) -> str:
    a4 = str(addr4 or "").strip()
    a3 = str(addr3 or "").strip()
    if a4.endswith(("동", "읍", "면", "가", "로")):
        return a4
    if a3.endswith(("동", "읍", "면", "가")):
        return a3
    return a4 or a3


def stratum_of(sido: str, emd: str) -> str:
    if emd.endswith(("읍", "면")):
        return "읍·면"
    if sido.startswith("서울"):
        return "서울"
    if sido.startswith("경기") or sido.startswith("인천"):
        return "경기·인천"
    if any(sido.startswith(name) for name in METRO):
        return "광역시"
    return "그 외 시"


def iqr_overlap(a: np.ndarray, b: np.ndarray) -> float | None:
    a25, a75 = _quantile(a, 0.25), _quantile(a, 0.75)
    b25, b75 = _quantile(b, 0.25), _quantile(b, 0.75)
    if None in (a25, a75, b25, b75):
        return None
    inter = max(0.0, min(a75, b75) - max(a25, b25))
    mean_len = ((a75 - a25) + (b75 - b25)) / 2.0
    if mean_len <= 0:
        return None
    return inter / mean_len


def inside_share(values: np.ndarray, other: np.ndarray) -> float | None:
    lo, hi = _quantile(other, 0.25), _quantile(other, 0.75)
    if values.size == 0 or lo is None or hi is None:
        return None
    return float(np.mean((values >= lo) & (values <= hi)))


def price_summary(values: np.ndarray) -> dict:
    return {
        "n": int(values.size),
        "p25": _round(_quantile(values, 0.25)),
        "p50": _round(_quantile(values, 0.50)),
        "p75": _round(_quantile(values, 0.75)),
    }


def _round(value: float | None, ndigits: int = 1) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), ndigits)


def gap(land_p50: float | None, built_p50: float | None) -> float | None:
    if land_p50 is None or built_p50 is None or land_p50 == 0:
        return None
    return (land_p50 - built_p50) / land_p50 * 100.0


def sign_of(value: float | None) -> int | None:
    if value is None:
        return None
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def bootstrap_gap(land: np.ndarray, built: np.ndarray, rng: np.random.Generator) -> dict:
    if land.size == 0 or built.size == 0:
        return {"low": None, "high": None, "includes_zero": None}
    draws = np.empty(BOOT, dtype=float)
    for i in range(BOOT):
        land_s = land[rng.integers(0, land.size, land.size)]
        built_s = built[rng.integers(0, built.size, built.size)]
        draws[i] = (float(np.median(land_s)) - float(np.median(built_s))) / float(np.median(land_s)) * 100.0
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"low": _round(float(lo), 1), "high": _round(float(hi), 1), "includes_zero": bool(lo <= 0 <= hi)}


def area_bands(land_area: np.ndarray, land_price: np.ndarray, built_area: np.ndarray, built_price: np.ndarray) -> list[dict]:
    rows = []
    for lo, hi, label in AREA_BINS:
        land_m = (land_area >= lo) & (land_area < hi)
        built_m = (built_area >= lo) & (built_area < hi)
        if int(land_m.sum()) < BAND_N or int(built_m.sum()) < BAND_N:
            continue
        lp = land_price[land_m]
        bp = built_price[built_m]
        d = gap(float(np.median(lp)), float(np.median(bp)))
        rows.append(
            {
                "band": label,
                "n_land": int(land_m.sum()),
                "n_built": int(built_m.sum()),
                "land_p50": _round(float(np.median(lp))),
                "built_p50": _round(float(np.median(bp))),
                "d_mid": _round(d, 1),
            }
        )
    return rows


def verdict(d_low_cost: float | None, d_mid: float | None, d_high_cost: float | None, ci_zero: bool | None, area_ref: bool) -> str:
    signs = [sign_of(d_low_cost), sign_of(d_mid), sign_of(d_high_cost)]
    if any(item is None for item in signs) or len(set(signs)) != 1:
        return "유보"
    if ci_zero:
        return "표본으로 구분되지 않음"
    if area_ref:
        return "면적 구성이 달라 참고"
    return "원가 폭 밖에 남음"


def main() -> None:
    bands = load_bands()
    uses = {use for use, _ in bands}
    built_engine = get_built_engine()
    if built_engine is None:
        raise RuntimeError("복합 DB 엔진이 없다.")
    with land_engine.connect() as conn:
        as_of = latest_as_of_month(conn)
    start, end = period_bounds_for_window(as_of, 5)
    print(f"window {start} .. {end} as_of {as_of}", flush=True)

    built_sql = text(
        """
        SELECT t.id, t.addr1, t.addr2, t.addr3, t.addr4, t.zone_type, t.building_use,
               t.price::float8 AS price, t.gross_area::float8 AS gross_area,
               t.land_area::float8 AS land_area, t.building_age::float8 AS building_age,
               t.contract_year::int AS contract_year, t.road_width_label,
               e.structure_group, e.approve_year::int AS approve_year
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
        """
    )
    built = pd.read_sql(built_sql, built_engine, params={"p_start": start, "p_end": end})
    built = built.drop_duplicates(subset=["id"])
    print(f"built rows {len(built)}", flush=True)

    low_u, mid_u, high_u, enveloped = [], [], [], []
    for row in built.itertuples(index=False):
        use = str(row.building_use or "").strip()
        structure = str(row.structure_group or "").strip()
        cost = resolve_cost(use, structure, bands) if use in uses else None
        if cost is None:
            low_u.append(np.nan)
            mid_u.append(np.nan)
            high_u.append(np.nan)
            enveloped.append(False)
            continue
        age = None
        if pd.notna(row.building_age):
            age = max(0.0, float(row.building_age))
        elif pd.notna(row.approve_year) and pd.notna(row.contract_year) and 1900 <= int(row.approve_year) <= 2100:
            age = max(0.0, float(int(row.contract_year) - int(row.approve_year)))
        a, b, c = allocate_three(float(row.price), float(row.gross_area), float(row.land_area), age, cost)
        low_u.append(np.nan if a is None else a)
        mid_u.append(np.nan if b is None else b)
        high_u.append(np.nan if c is None else c)
        enveloped.append(not structure)
    built["unit_low_cost"] = low_u
    built["unit_mid"] = mid_u
    built["unit_high_cost"] = high_u
    built["envelope"] = enveloped
    built["leaf"] = [leaf_name(a, b) for a, b in zip(built.addr3, built.addr4)]
    built["zone"] = built.zone_type.map(canon_any)
    built["sido"] = built.addr1.fillna("").map(lambda s: str(s).strip())
    built["sigungu"] = built.addr2.fillna("").map(lambda s: str(s).strip())
    valid = built[np.isfinite(built.unit_mid)].copy()
    print(f"built valid mid {len(valid)}", flush=True)

    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    land_sql = text(
        f"""
        SELECT btrim(r.sido_name::text) AS sido,
               btrim(r.sigungu_name::text) AS sigungu,
               btrim(r.eupmyeondong_name::text) AS emd,
               btrim(r.eupmyeondong_code::text) AS code,
               btrim(lt.zone_type_resolved::text) AS zone,
               COUNT(*)::int AS n,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY lt.area_sqm) AS area_p50,
               percentile_cont(0.25) WITHIN GROUP (ORDER BY lt.area_sqm) AS area_p25,
               percentile_cont(0.75) WITHIN GROUP (ORDER BY lt.area_sqm) AS area_p75
        FROM land_transactions_resolved lt
        {join_sql}
        WHERE lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.unit_price_per_sqm > 0
          AND btrim(lt.land_category_resolved::text) = '대'
          AND btrim(COALESCE(lt.zone_type_resolved::text, '')) <> ''
          AND btrim(COALESCE(r.eupmyeondong_name::text, '')) <> ''
        GROUP BY 1, 2, 3, 4, 5
        HAVING COUNT(*) >= :min_n
        """
    )
    with land_engine.connect() as conn:
        land_cells = pd.read_sql(land_sql, conn, params={"p_start": start, "p_end": end, "min_n": MIN_N})
    land_cells["zone"] = land_cells.zone.map(canon_any)
    land_cells = (
        land_cells.groupby(["sido", "sigungu", "emd", "code", "zone"], as_index=False)
        .agg(n=("n", "sum"), area_p50=("area_p50", "median"), area_p25=("area_p25", "median"), area_p75=("area_p75", "median"))
    )
    print(f"land cells n>=20 {len(land_cells)}", flush=True)

    built_cells = (
        valid.groupby(["sido", "sigungu", "leaf", "zone"], as_index=False)
        .agg(n=("id", "size"), area_p50=("land_area", "median"), area_p25=("land_area", lambda s: s.quantile(0.25)), area_p75=("land_area", lambda s: s.quantile(0.75)))
    )
    built_cells = built_cells[built_cells.n >= MIN_N]
    merged = land_cells.merge(
        built_cells,
        left_on=["sido", "sigungu", "emd", "zone"],
        right_on=["sido", "sigungu", "leaf", "zone"],
        suffixes=("_land", "_built"),
    )
    print(f"matched cells {len(merged)}", flush=True)
    if merged.empty:
        raise RuntimeError("이름·용도지역이 맞는 칸이 없다.")

    merged["min_n"] = merged[["n_land", "n_built"]].min(axis=1)
    merged["area_ratio"] = merged[["area_p50_land", "area_p50_built"]].max(axis=1) / merged[["area_p50_land", "area_p50_built"]].min(axis=1)
    merged["area_iqr_overlap"] = [
        max(0.0, min(r.area_p75_land, r.area_p75_built) - max(r.area_p25_land, r.area_p25_built)) > 0
        for r in merged.itertuples(index=False)
    ]
    merged["area_bad"] = (merged.area_ratio > 2) | (~merged.area_iqr_overlap)
    merged["stratum"] = [stratum_of(s, e) for s, e in zip(merged.sido, merged.emd)]

    picked_idx: list[int] = []
    for name in STRATA:
        pool = merged[merged.stratum == name].sort_values(["area_bad", "min_n"], ascending=[True, False])
        take = 2 if (~pool.area_bad).sum() >= 2 else 1
        picked_idx.extend(pool.head(take).index.tolist())
    picked = merged.loc[list(dict.fromkeys(picked_idx))].head(10)
    if len(picked) < 5:
        rest = merged.drop(index=picked.index, errors="ignore").sort_values(["area_bad", "min_n"], ascending=[True, False])
        picked = pd.concat([picked, rest.head(5 - len(picked))])
    print("picked", len(picked), flush=True)

    codes = sorted(set(picked.code.tolist()))
    params = {f"c{i}": code for i, code in enumerate(codes)}
    in_sql = ", ".join(f":c{i}" for i in range(len(codes)))
    land_rows_sql = text(
        f"""
        SELECT btrim(r.sido_name::text) AS sido,
               btrim(r.sigungu_name::text) AS sigungu,
               btrim(r.eupmyeondong_name::text) AS emd,
               btrim(lt.zone_type_resolved::text) AS zone,
               lt.area_sqm::float8 AS area_sqm,
               lt.unit_price_per_sqm::float8 AS unit_price,
               lt.road_condition AS road
        FROM land_transactions_resolved lt
        {join_sql}
        WHERE lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.unit_price_per_sqm > 0
          AND btrim(lt.land_category_resolved::text) = '대'
          AND btrim(r.eupmyeondong_code::text) IN ({in_sql})
        """
    )
    params.update({"p_start": start, "p_end": end})
    with land_engine.connect() as conn:
        land_rows = pd.read_sql(land_rows_sql, conn, params=params)
    land_rows["zone"] = land_rows.zone.map(canon_any)

    rng = np.random.default_rng(SEED)
    results = []
    for row in picked.itertuples(index=False):
        land_part = land_rows[
            (land_rows.sido == row.sido)
            & (land_rows.sigungu == row.sigungu)
            & (land_rows.emd == row.emd)
            & (land_rows.zone == row.zone)
        ]
        built_part = valid[
            (valid.sido == row.sido)
            & (valid.sigungu == row.sigungu)
            & (valid.leaf == row.emd)
            & (valid.zone == row.zone)
        ]
        land_price = land_part.unit_price.to_numpy(dtype=float)
        land_area = land_part.area_sqm.to_numpy(dtype=float)
        mid = built_part.unit_mid.to_numpy(dtype=float)
        low_cost = built_part.unit_low_cost.to_numpy(dtype=float)
        high_cost = built_part.unit_high_cost.to_numpy(dtype=float)
        low_cost = low_cost[np.isfinite(low_cost)]
        high_cost = high_cost[np.isfinite(high_cost)]
        d_mid = gap(float(np.median(land_price)), float(np.median(mid))) if land_price.size and mid.size else None
        d_low_cost = gap(float(np.median(land_price)), float(np.median(low_cost))) if land_price.size and low_cost.size else None
        d_high_cost = gap(float(np.median(land_price)), float(np.median(high_cost))) if land_price.size and high_cost.size else None
        ci = bootstrap_gap(land_price, mid, rng)
        area_ref = bool(row.area_bad)
        land_roads = land_part.road.fillna("").astype(str).value_counts().head(6).to_dict()
        built_roads = built_part.road_width_label.fillna("").astype(str).value_counts().head(6).to_dict()
        results.append(
            {
                "stratum": row.stratum,
                "sido": row.sido,
                "sigungu": row.sigungu,
                "emd": row.emd,
                "zone": row.zone,
                "n_land": int(land_price.size),
                "n_built": int(mid.size),
                "n_built_low_cost": int(low_cost.size),
                "n_built_high_cost": int(high_cost.size),
                "envelope_share": _round(float(built_part.envelope.mean()) if len(built_part) else None, 3),
                "land_area": price_summary(land_area),
                "built_area": price_summary(built_part.land_area.to_numpy(dtype=float)),
                "area_ratio": _round(float(row.area_ratio), 2),
                "area_reference_only": area_ref,
                "land_price": price_summary(land_price),
                "built_mid": price_summary(mid),
                "built_low_cost": price_summary(low_cost),
                "built_high_cost": price_summary(high_cost),
                "d_low_cost": _round(d_low_cost, 1),
                "d_mid": _round(d_mid, 1),
                "d_high_cost": _round(d_high_cost, 1),
                "bootstrap95_mid": ci,
                "iqr_overlap": _round(iqr_overlap(land_price, mid), 3),
                "land_inside_built_iqr": _round(inside_share(land_price, mid), 3),
                "built_inside_land_iqr": _round(inside_share(mid, land_price), 3),
                "area_bands": area_bands(
                    land_area,
                    land_price,
                    built_part.land_area.to_numpy(dtype=float),
                    mid,
                ),
                "land_roads": land_roads,
                "built_roads": built_roads,
                "road_controlled": False,
                "verdict": verdict(d_low_cost, d_mid, d_high_cost, ci["includes_zero"], area_ref),
            }
        )

    empty_strata = [name for name in STRATA if name not in set(merged.stratum)]
    payload = {
        "stage": 1,
        "as_of_month": as_of.isoformat(),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "unit": "만원/㎡",
        "min_n": MIN_N,
        "bootstrap": BOOT,
        "seed": SEED,
        "matched_cells": int(len(merged)),
        "empty_strata": empty_strata,
        "qualifying_by_stratum": merged.stratum.value_counts().to_dict(),
        "notes": [
            "토지 단독거래는 확인된 나지가 아니다.",
            "건부지 가격은 기준 재조달원가로 배분한 추정치다.",
            "d_low_cost는 재조달원가 하한, d_high_cost는 재조달원가 상한이다.",
            "부트스트랩 구간은 기준 원가의 표본 불확실성만 담는다.",
            "도로조건 표기는 토지와 복합의 코드가 달라 1차에서 통제한 비교로 쓰지 않았다.",
        ],
        "cells": results,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)
    for cell in results:
        print(
            cell["stratum"],
            cell["sido"],
            cell["sigungu"],
            cell["emd"],
            cell["zone"],
            cell["n_land"],
            cell["n_built"],
            cell["d_mid"],
            cell["verdict"],
            flush=True,
        )


if __name__ == "__main__":
    main()
