"""집합상가 2층 — 연식·용도·도로 고정효과.

2차의 55·68을 바꾸지 않는다. 3층 이상은 넣지 않는다.
재실행 (backend에서): python -m app.shop_floor_lab.fe
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.collective.db import get_collective_engine
from app.land_lab.area_elasticity_screen import period_bounds_for_window
from app.shop_floor_lab.ratio import (
    AREA_BAND,
    AS_OF,
    WINDOW_YEARS,
    fetch_bin_rows,
    rows_to_clusters,
)

ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "lab" / "shop_floor_utility_fe.json"

USE_MIN = 30
OTHER_USE = "기타"
Z_95 = 1.959963984540054

BASE_EQUAL = 55.2
BASE_WEIGHTED = 68.1

TRADE_SQL = """
    WITH tx AS (
        SELECT
            t.cluster_key,
            t.floor,
            t.unit_price,
            t.gross_area,
            t.building_age,
            t.building_year,
            t.contract_date,
            t.building_use
        FROM collective_commercial_transactions t
        WHERE t.asset_type = 'collective_shop'
          AND t.is_valid IS TRUE
          AND t.contract_date >= :p_start
          AND t.contract_date <= :p_end
          AND t.unit_price > 0
          AND t.gross_area > 0
          AND t.floor >= 1
          AND t.cluster_key IS NOT NULL
          AND t.cluster_key <> ''
    ),
    scoped AS (
        SELECT
            tx.cluster_key,
            tx.floor,
            tx.unit_price,
            tx.gross_area,
            tx.building_age,
            tx.building_year,
            EXTRACT(YEAR FROM tx.contract_date)::int AS contract_year,
            tx.building_use,
            CASE
                WHEN tx.floor = 1 THEN 'f1'
                WHEN tx.floor = 2 THEN 'f2'
                WHEN tx.floor >= 3 AND tx.floor <= 4 THEN 'low'
                WHEN tx.floor >= 5 AND tx.floor <= 9 THEN 'mid'
                WHEN tx.floor >= 10 AND tx.floor <= 19 THEN 'high'
                WHEN tx.floor >= 20 THEN 'ultra'
                ELSE 'other'
            END AS bin
        FROM tx
    ),
    area AS (
        SELECT
            cluster_key,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gross_area) AS med_area
        FROM scoped
        WHERE bin <> 'other'
        GROUP BY cluster_key
    )
    SELECT
        s.cluster_key,
        s.floor,
        s.unit_price,
        s.gross_area,
        s.building_age,
        s.building_year,
        s.contract_year,
        s.building_use
    FROM scoped s
    JOIN area a ON a.cluster_key = s.cluster_key
    WHERE s.bin IN ('f1', 'f2')
      AND s.gross_area >= a.med_area * (1 - :band)
      AND s.gross_area <= a.med_area * (1 + :band)
"""


def phase2_f2_keys(conn: Connection, p_start, p_end) -> set[str]:
    """2차에서 2층 지수가 있는 cluster. 55·68을 만든 89곳과 같은 집합."""
    eligible = {row["cluster_key"] for row in rows_to_clusters(fetch_bin_rows(conn, p_start, p_end, area_band=False))}
    area_rows = rows_to_clusters(fetch_bin_rows(conn, p_start, p_end, area_band=True), min_cluster_n=0)
    return {row["cluster_key"] for row in area_rows if row["cluster_key"] in eligible and row["idx_f2"] is not None}


def fill_age(frame: pd.DataFrame) -> pd.Series:
    age = pd.to_numeric(frame["building_age"], errors="coerce")
    year = pd.to_numeric(frame["building_year"], errors="coerce")
    contract_year = pd.to_numeric(frame["contract_year"], errors="coerce")
    fill = age.isna() & year.notna() & contract_year.notna()
    out = age.copy()
    out.loc[fill] = contract_year.loc[fill] - year.loc[fill]
    return out


def group_use(series: pd.Series) -> tuple[pd.Series, str, int]:
    raw = series.fillna("").astype(str).str.strip()
    raw = raw.mask(raw.eq(""), OTHER_USE)
    counts = raw.value_counts()
    rare = {name for name, n in counts.items() if name != OTHER_USE and int(n) < USE_MIN}
    grouped = raw.where(~raw.isin(rare), OTHER_USE)
    reference = str(grouped.value_counts().idxmax())
    other_n = int((grouped == OTHER_USE).sum())
    return grouped, reference, other_n


def _index_row(gamma: float, se: float, p_value: float) -> dict[str, Any]:
    lo = float(np.exp(gamma - Z_95 * se) * 100.0)
    hi = float(np.exp(gamma + Z_95 * se) * 100.0)
    index = float(np.exp(gamma) * 100.0)
    return {
        "gamma": round(gamma, 4),
        "se": round(se, 4),
        "p": round(p_value, 4),
        "index": round(index, 1),
        "ci95": [round(lo, 1), round(hi, 1)],
        "includes_100": bool(lo <= 100.0 <= hi),
        "pct_vs_1f": round(index - 100.0, 1),
    }


def within_f2(work: pd.DataFrame, *, equal_cluster: bool, use_reference: str) -> dict[str, Any]:
    """도로 평균을 뺀 2층 계수. equal_cluster면 cluster 가중 합이 1이다."""
    frame = work.copy()
    frame["ln_p"] = np.log(frame["unit_price"].astype(float))
    frame["ln_a"] = np.log(frame["gross_area"].astype(float))
    frame["f2"] = (frame["floor"].astype(float) == 2).astype(float)
    frame["age"] = frame["age"].astype(float)
    dummies: list[tuple[str, str]] = []
    reference = use_reference
    for name in sorted(set(frame["use_group"].astype(str)) - {reference}):
        col = f"use_{len(dummies)}"
        frame[col] = (frame["use_group"] == name).astype(float)
        dummies.append((col, name))
    dummy_cols = [col for col, _name in dummies]
    xcols = ["f2", "ln_a", "age", *dummy_cols]
    size = frame.groupby("cluster_key")["ln_p"].transform("size").astype(float)
    frame["w"] = (1.0 / size) if equal_cluster else 1.0
    cols = ["ln_p", *xcols]
    dem = frame[cols] - frame.groupby("cluster_key")[cols].transform("mean")
    keep = [col for col in xcols if float(dem[col].std(ddof=0)) > 1e-10]
    if "f2" not in keep:
        return {"ok": False, "reason": "2층 더미가 도로 안에서 움직이지 않음"}
    y = dem["ln_p"].to_numpy(dtype=float)
    x = dem[keep].to_numpy(dtype=float)
    groups = pd.factorize(frame["cluster_key"])[0]
    weights = frame["w"].to_numpy(dtype=float)
    if equal_cluster:
        model = sm.WLS(y, x, weights=weights).fit(cov_type="cluster", cov_kwds={"groups": groups})
    else:
        model = sm.OLS(y, x, hasconst=False).fit(cov_type="cluster", cov_kwds={"groups": groups})
    idx = keep.index("f2")
    row = _index_row(float(model.params[idx]), float(model.bse[idx]), float(model.pvalues[idx]))
    both = frame.groupby("cluster_key")["floor"].nunique()
    return {
        "ok": True,
        "weight": "cluster" if equal_cluster else "trade",
        "n_trades": int(len(frame)),
        "n_clusters": int(frame["cluster_key"].nunique()),
        "n_clusters_both_floors": int((both >= 2).sum()),
        "controls_kept": [col for col in keep if col != "f2"],
        "uses_kept": [name for col, name in dummies if col in keep],
        **row,
    }


def prepare_regression(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    work = frame.copy()
    work["age"] = fill_age(work)
    dropped = int(work["age"].isna().sum())
    work = work.loc[work["age"].notna()].copy()
    if work.empty:
        grouped, reference, other_n = pd.Series(dtype=str), None, 0
    else:
        grouped, reference, other_n = group_use(work["building_use"])
        work["use_group"] = grouped.to_numpy()
    meta = {
        "n_trades_in": int(len(frame)),
        "n_age_dropped": dropped,
        "n_regression": int(len(work)),
        "n_clusters": int(work["cluster_key"].nunique()) if len(work) else 0,
        "use_reference": reference if len(work) else None,
        "use_other_n": other_n if len(work) else 0,
    }
    return work, meta


def fit_both(frame: pd.DataFrame) -> dict[str, Any]:
    work, meta = prepare_regression(frame)
    if meta["n_regression"] == 0:
        return {**meta, "fits": [], "index_gap_trade_minus_cluster": None, "base_equal": BASE_EQUAL, "base_weighted": BASE_WEIGHTED}
    fits = [
        within_f2(work, equal_cluster=False, use_reference=str(meta["use_reference"])),
        within_f2(work, equal_cluster=True, use_reference=str(meta["use_reference"])),
    ]
    gap = None
    if fits[0].get("ok") and fits[1].get("ok"):
        gap = round(float(fits[0]["index"]) - float(fits[1]["index"]), 1)
    return {
        "base_equal": BASE_EQUAL,
        "base_weighted": BASE_WEIGHTED,
        "note": "exp(beta)*100은 2차의 55.2·68.1을 대체하지 않는다. 새 층 지수가 아니다.",
        **meta,
        "fits": fits,
        "index_gap_trade_minus_cluster": gap,
    }


def fetch_band_trades(conn: Connection, p_start, p_end) -> pd.DataFrame:
    rows = conn.execute(
        text(TRADE_SQL),
        {"p_start": p_start, "p_end": p_end, "band": AREA_BAND},
    ).mappings()
    return pd.DataFrame([dict(row) for row in rows])


def run_fe(engine: Engine) -> dict[str, Any]:
    from datetime import date

    p_start, p_end = period_bounds_for_window(AS_OF, WINDOW_YEARS)
    with engine.connect() as conn:
        keys = phase2_f2_keys(conn, p_start, p_end)
        trades = fetch_band_trades(conn, p_start, p_end)
    trades = trades[trades["cluster_key"].isin(keys)].copy()
    payload = fit_both(trades)
    payload.update(
        {
            "as_of": AS_OF.isoformat(),
            "period_start": p_start.isoformat() if isinstance(p_start, date) else str(p_start),
            "period_end": p_end.isoformat() if isinstance(p_end, date) else str(p_end),
            "area_band": AREA_BAND,
            "phase2_f2_clusters": len(keys),
            "question": "1층 대비 2층 차이가 면적·연식·용도로 설명되는가. 같은 도로 안.",
        }
    )
    return payload


def main() -> None:
    payload = run_fe(get_collective_engine())
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_JSON),
                "phase2_f2_clusters": payload["phase2_f2_clusters"],
                "n_age_dropped": payload["n_age_dropped"],
                "n_regression": payload["n_regression"],
                "use_reference": payload["use_reference"],
                "fits": payload["fits"],
                "index_gap_trade_minus_cluster": payload["index_gap_trade_minus_cluster"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
