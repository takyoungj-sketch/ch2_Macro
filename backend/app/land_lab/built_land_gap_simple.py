# -*- coding: utf-8 -*-
"""시·군·구 × 용도지역 × 도로폭. 중앙값과 평균값을 따로 비교한다.

제품 원장과 간이 신축원가표는 읽기만 한다.
결과는 docs/lab/land_built_alloc_gap_simple.json
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.built.db import get_built_engine
from app.built.enrichment_join import canonical_zone_label
from app.built.time_scope import period_bounds_for_window
from app.db import engine as land_engine
from app.land_lab.area_elasticity_screen import latest_as_of_month
from app.land_lab.built_land_gap_stage1 import (
    allocate_three,
    canon_any,
    load_bands,
    resolve_cost,
)
from app.region_canonical import region_codes_join_on_canonical

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "land_built_alloc_gap_simple.json"
MIN_N = 30
ROADS = ("8미만", "12미만", "25미만", "25이상")
RESIDENTIAL = {"1전", "2전", "1주", "2주", "3주", "준주"}
METRO = ("부산", "대구", "인천", "대전", "울산")
HEUNGDEOK = ("충청북도", "청주시 흥덕구", "1주")


def road_bucket(raw: object) -> str:
    s = str(raw or "").strip().replace(" ", "").replace("m", "").replace("M", "")
    return s if s in ROADS else ""


def display_zone(ledger: object, contract: object) -> str:
    """원장 용도지역. 비어 있으면 계약연도 용도지역. 화면 표시와 같다."""
    led = canonical_zone_label([str(ledger)]) if pd.notna(ledger) and str(ledger).strip() else None
    if led:
        return led
    if pd.notna(contract) and str(contract).strip():
        filled = canonical_zone_label([str(contract)])
        return filled or ""
    return ""


def place_built(addr2: object, addr3: object) -> str:
    a2 = str(addr2 or "").strip()
    a3 = str(addr3 or "").strip()
    if a3.endswith("구") and a2.endswith(("시", "군")):
        return f"{a2} {a3}"
    return a2


def stratum_of(sido: str, place: str) -> str:
    if sido.startswith("서울"):
        return "서울"
    if any(sido.startswith(name) for name in METRO):
        return "광역시"
    last = place.split()[-1] if place else ""
    if sido.startswith("전남광주") and last.endswith("구"):
        return "광역시"
    if last.endswith("군"):
        return "군"
    return "시"


def _r(value: float | None, ndigits: int = 1) -> float | None:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return round(float(value), ndigits)


def _d(land: float | None, built: float | None) -> float | None:
    if land is None or built is None or land == 0 or not math.isfinite(land) or not math.isfinite(built):
        return None
    return (land - built) / land * 100.0


def _ratio(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return max(a, b) / min(a, b)


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
        elif (
            cost is not None
            and pd.notna(row.approve_year)
            and pd.notna(row.contract_year)
            and 1900 <= int(row.approve_year) <= 2100
        ):
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
    out = built.copy()
    out["unit_low"] = low_u
    out["unit_mid"] = mid_u
    out["unit_high"] = high_u
    out["place"] = [place_built(a, b) for a, b in zip(out.addr2, out.addr3)]
    out["zone"] = [canon_any(display_zone(a, b)) for a, b in zip(out.zone_type, out.zone_contract_year)]
    out["road"] = out.road_width_label.map(road_bucket)
    out["sido"] = out.addr1.fillna("").map(lambda s: str(s).strip())
    out["detached"] = out.asset_type.fillna("").map(lambda s: str(s).strip() == "detached")
    return out


def built_cells(frame: pd.DataFrame) -> pd.DataFrame:
    base = frame[frame.road.isin(ROADS) & frame.place.ne("") & frame.zone.ne("")].copy()
    keys = ["sido", "place", "zone", "road"]
    raw_n = base.groupby(keys).size().rename("n_raw")
    parts = []
    for name, col in (("low", "unit_low"), ("mid", "unit_mid"), ("high", "unit_high")):
        part = base[np.isfinite(base[col])]
        grouped = part.groupby(keys)[col].agg(n="count", med="median", mean="mean")
        grouped.columns = [f"n_{name}", f"med_{name}", f"mean_{name}"]
        parts.append(grouped)
    area = (
        base[np.isfinite(base.unit_mid)]
        .groupby(keys)["land_area"]
        .agg(area_med="median", area_mean="mean")
    )
    out = parts[0].join(parts[1:], how="outer").join(area, how="left").join(raw_n, how="left")
    return out.reset_index()


def fetch_land(start: str, end: str) -> pd.DataFrame:
    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    sql = text(
        f"""
        SELECT btrim(r.sido_name::text) AS sido,
               btrim(r.sigungu_name::text) AS place,
               btrim(lt.zone_type_resolved::text) AS zone,
               replace(replace(btrim(lt.road_condition::text), 'm', ''), 'M', '') AS road,
               COUNT(*)::int AS n_land,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY lt.unit_price_per_sqm) AS land_med,
               avg(lt.unit_price_per_sqm)::float8 AS land_mean,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY lt.area_sqm) AS land_area_med,
               avg(lt.area_sqm)::float8 AS land_area_mean
        FROM land_transactions_resolved lt
        {join_sql}
        WHERE lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND COALESCE(lt.is_partial_ownership, FALSE) = FALSE
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.unit_price_per_sqm > 0
          AND btrim(lt.land_category_resolved::text) = '대'
          AND btrim(COALESCE(lt.zone_type_resolved::text, '')) <> ''
          AND replace(replace(btrim(COALESCE(lt.road_condition::text, '')), 'm', ''), 'M', '')
              IN ('8미만', '12미만', '25미만', '25이상')
        GROUP BY 1, 2, 3, 4
        """
    )
    with land_engine.connect() as conn:
        land = pd.read_sql(sql, conn, params={"p_start": start, "p_end": end})
    land["zone"] = land.zone.map(canon_any)
    land = (
        land.groupby(["sido", "place", "zone", "road"], as_index=False)
        .agg(
            n_land=("n_land", "sum"),
            land_med=("land_med", "median"),
            land_mean=("land_mean", "mean"),
            land_area_med=("land_area_med", "median"),
            land_area_mean=("land_area_mean", "mean"),
        )
    )
    return land


def merge_cells(land: pd.DataFrame, built: pd.DataFrame) -> pd.DataFrame:
    merged = land.merge(built, on=["sido", "place", "zone", "road"], how="outer")
    for col in ("n_land", "n_raw", "n_low", "n_mid", "n_high"):
        if col in merged.columns:
            merged[col] = merged[col].fillna(0).astype(int)
    merged["stratum"] = [stratum_of(s, p) for s, p in zip(merged.sido.fillna(""), merged.place.fillna(""))]
    merged["area_med_ratio"] = [
        _ratio(_num(a), _num(b)) for a, b in zip(merged.land_area_med, merged.area_med)
    ]
    merged["area_mean_ratio"] = [
        _ratio(_num(a), _num(b)) for a, b in zip(merged.land_area_mean, merged.area_mean)
    ]
    merged["area_gap"] = [
        (r is not None and r > 2) or (m is not None and m > 2)
        for r, m in zip(merged.area_med_ratio, merged.area_mean_ratio)
    ]
    for kind, bmed, bmean in (
        ("low", "med_low", "mean_low"),
        ("mid", "med_mid", "mean_mid"),
        ("high", "med_high", "mean_high"),
    ):
        merged[f"d_med_{kind}"] = [
            _d(_num(a), _num(b)) for a, b in zip(merged.land_med, merged[bmed])
        ]
        merged[f"d_mean_{kind}"] = [
            _d(_num(a), _num(b)) for a, b in zip(merged.land_mean, merged[bmean])
        ]
    return merged


def _num(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(number):
        return number
    return None


def _quantile(series: pd.Series, p: float) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    return _r(float(np.quantile(clean.to_numpy(dtype=float), p)))


def _share_block(frame: pd.DataFrame, col: str, weight: pd.Series) -> dict:
    sub = frame[pd.to_numeric(frame[col], errors="coerce").notna()].copy()
    if sub.empty:
        return {"n": 0, "n_pos": 0, "share": None, "share_w": None, "p25": None, "p50": None, "p75": None}
    values = sub[col].astype(float)
    pos = values > 0
    w = weight.loc[sub.index].astype(float)
    wsum = float(w.sum())
    return {
        "n": int(len(sub)),
        "n_pos": int(pos.sum()),
        "share": _r(float(pos.mean()) * 100),
        "share_w": _r(float(w[pos].sum()) / wsum * 100) if wsum else None,
        "p25": _quantile(values, 0.25),
        "p50": _quantile(values, 0.50),
        "p75": _quantile(values, 0.75),
    }


def _gu_votes(frame: pd.DataFrame, col: str) -> dict:
    votes = {"양수": 0, "반반": 0, "비양수": 0}
    for _, group in frame.groupby(["sido", "place"]):
        values = pd.to_numeric(group[col], errors="coerce").dropna()
        if values.empty:
            continue
        pos = int((values > 0).sum())
        other = int(len(values) - pos)
        if pos > other:
            votes["양수"] += 1
        elif pos == other:
            votes["반반"] += 1
        else:
            votes["비양수"] += 1
    total = sum(votes.values())
    return {
        "n_gu": total,
        "n_pos": votes["양수"],
        "n_tie": votes["반반"],
        "n_nonpos": votes["비양수"],
        "share": _r(votes["양수"] / total * 100) if total else None,
    }


def summarize(frame: pd.DataFrame) -> dict:
    headline = frame[(frame.n_land >= MIN_N) & (frame.n_mid >= MIN_N)].copy()
    weight = headline[["n_land", "n_mid"]].min(axis=1)
    both_tails = headline[(headline.n_low >= MIN_N) & (headline.n_high >= MIN_N)]
    med_all = (both_tails.d_med_low > 0) & (both_tails.d_med_mid > 0) & (both_tails.d_med_high > 0)
    mean_all = (both_tails.d_mean_low > 0) & (both_tails.d_mean_mid > 0) & (both_tails.d_mean_high > 0)
    sign_gap = headline[
        headline.d_med_mid.notna()
        & headline.d_mean_mid.notna()
        & (np.sign(headline.d_med_mid.astype(float)) != np.sign(headline.d_mean_mid.astype(float)))
    ]
    area_ok = headline[~headline.area_gap.astype(bool)]
    return {
        "n_cells": int(len(headline)),
        "median": _share_block(headline, "d_med_mid", weight),
        "mean": _share_block(headline, "d_mean_mid", weight),
        "sign_disagree": int(len(sign_gap)),
        "tail_eligible": int(len(both_tails)),
        "tail_dropped": int(len(headline) - len(both_tails)),
        "all_three_positive_median": {
            "n": int(med_all.sum()),
            "share": _r(float(med_all.mean()) * 100) if len(both_tails) else None,
        },
        "all_three_positive_mean": {
            "n": int(mean_all.sum()),
            "share": _r(float(mean_all.mean()) * 100) if len(both_tails) else None,
        },
        "gu_median": _gu_votes(headline, "d_med_mid"),
        "gu_mean": _gu_votes(headline, "d_mean_mid"),
        "area_ok_cells": int(len(area_ok)),
        "area_ok_median": _share_block(area_ok, "d_med_mid", area_ok[["n_land", "n_mid"]].min(axis=1) if len(area_ok) else weight),
        "area_ok_mean": _share_block(area_ok, "d_mean_mid", area_ok[["n_land", "n_mid"]].min(axis=1) if len(area_ok) else weight),
    }


def heungdeok_rows(frame: pd.DataFrame) -> list[dict]:
    sido, place, zone = HEUNGDEOK
    part = frame[(frame.sido == sido) & (frame.place == place) & (frame.zone == zone)].copy()
    rows = []
    for road in ROADS:
        hit = part[part.road == road]
        if hit.empty:
            rows.append({"road": road, "n_land": 0, "n_built_raw": 0, "n_built_mid": 0})
            continue
        row = hit.iloc[0]
        rows.append(
            {
                "road": road,
                "n_land": int(row.n_land),
                "n_built_raw": int(row.n_raw),
                "n_built_mid": int(row.n_mid),
                "n_built_low": int(row.n_low),
                "n_built_high": int(row.n_high),
                "land_med": _r(_num(row.land_med)),
                "land_mean": _r(_num(row.land_mean)),
                "built_med_low_cost": _r(_num(row.med_low)),
                "built_med_mid": _r(_num(row.med_mid)),
                "built_med_high_cost": _r(_num(row.med_high)),
                "built_mean_low_cost": _r(_num(row.mean_low)),
                "built_mean_mid": _r(_num(row.mean_mid)),
                "built_mean_high_cost": _r(_num(row.mean_high)),
                "d_med_low_cost": _r(row.d_med_low),
                "d_med_mid": _r(row.d_med_mid),
                "d_med_high_cost": _r(row.d_med_high),
                "d_mean_low_cost": _r(row.d_mean_low),
                "d_mean_mid": _r(row.d_mean_mid),
                "d_mean_high_cost": _r(row.d_mean_high),
                "area_med_ratio": _r(_num(row.area_med_ratio), 2),
                "area_mean_ratio": _r(_num(row.area_mean_ratio), 2),
                "enters_table": bool(row.n_land >= MIN_N and row.n_mid >= MIN_N),
            }
        )
    return rows


def main() -> None:
    bands = load_bands()
    built_engine = get_built_engine()
    if built_engine is None:
        raise RuntimeError("복합 DB 엔진이 없다.")
    with land_engine.connect() as conn:
        as_of = latest_as_of_month(conn)
    start, end = period_bounds_for_window(as_of, 5)
    print(f"window {start} .. {end} as_of {as_of}", flush=True)

    built_sql = text(
        """
        SELECT t.id, t.asset_type, t.addr1, t.addr2, t.addr3, t.zone_type, t.building_use,
               t.price::float8 AS price, t.gross_area::float8 AS gross_area,
               t.land_area::float8 AS land_area, t.building_age::float8 AS building_age,
               t.contract_year::int AS contract_year, t.road_width_label,
               e.structure_group, e.approve_year::int AS approve_year,
               e.zone_contract_year
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
    built = allocate_frame(built, bands)
    print(f"built mid {int(np.isfinite(built.unit_mid).sum())}", flush=True)

    land = fetch_land(start.isoformat(), end.isoformat())
    print(f"land groups {len(land)}", flush=True)

    all_cells = merge_cells(land, built_cells(built))
    detached_cells = merge_cells(land, built_cells(built[built.detached]))
    residential = detached_cells[detached_cells.zone.isin(RESIDENTIAL)]

    def pack(frame: pd.DataFrame) -> dict:
        block = summarize(frame)
        by = {}
        for name in ("서울", "광역시", "시", "군"):
            by[name] = summarize(frame[frame.stratum == name])
        block["by_stratum"] = by
        return block

    payload = {
        "stage": "simple",
        "as_of_month": as_of.isoformat(),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "min_n": MIN_N,
        "unit": "만원/㎡",
        "notes": [
            "토지 단독거래는 확인된 나지가 아니다.",
            "건부지 가격은 배분 추정치다.",
            "중앙값 차이와 평균값 차이는 분모가 각 통계량이다.",
            "원가 하한은 배분단가를 높여 D를 작게 한다.",
            "구 과반은 칸 수 기준이다. 양수 칸과 그 밖이 같으면 반반이다.",
            "면적 비가 2배를 넘는 칸은 본표에 두고, 그 칸을 뺀 비율을 따로 둔다.",
            "전남광주통합특별시의 구는 광역시 층, 그 안의 시·군은 시·군 층이다.",
            "복합 용도지역은 원장이 비면 계약연도 용도지역으로 채운다. 단독·다가구는 원장이 비어 있다.",
        ],
        "heungdeok_detached": heungdeok_rows(detached_cells),
        "heungdeok_all": heungdeok_rows(all_cells),
        "national_all": pack(all_cells),
        "national_detached_residential": pack(residential),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)
    nat = payload["national_all"]
    print(
        "cells",
        nat["n_cells"],
        "med",
        nat["median"]["share"],
        nat["median"]["p50"],
        "mean",
        nat["mean"]["share"],
        nat["mean"]["p50"],
        flush=True,
    )


if __name__ == "__main__":
    main()
