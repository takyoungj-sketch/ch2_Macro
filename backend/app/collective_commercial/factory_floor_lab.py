# -*- coding: utf-8 -*-
"""집합공장 클러스터 안 층 지수. 제품 층 식은 읽기만 한다.

계획: docs/lab/COLLECTIVE_COMPLEX_GAP_LAB.md §7
결과: docs/lab/collective_factory_floor_lab.json

1층이 있는 클러스터만 1층=100으로 비교한다. 전국 회귀 하나를 본표로 두지 않는다.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import text

from app.collective.db import get_collective_engine
from app.collective.regression.engine import _factory_floor_code
from app.collective_commercial.cluster_stats_query import latest_mart_snapshot
from app.v2_stats_windows import period_bounds_for_window

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "collective_factory_floor_lab.json"
MIN_CLUSTER = 30
MIN_BAND = 10
BANDS = ("fac_b", "fac_2", "fac_3p")
BAND_LABEL = {"fac_b": "지하", "fac_1": "1층", "fac_2": "2층", "fac_3p": "3층 이상"}


def _r(value, ndigits: int = 1):
    if value is None or not isinstance(value, (int, float, np.floating)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, ndigits)


def hat_diag(x_values: np.ndarray) -> np.ndarray:
    q, _ = np.linalg.qr(x_values, mode="reduced")
    return np.sum(q * q, axis=1)


def load_trades(conn, start: date, end: date) -> pd.DataFrame:
    frame = pd.read_sql(
        text(
            """
            SELECT t.cluster_key, c.display_label, t.building_use, t.contract_year,
                   t.building_age, t.gross_area, t.unit_price, t.floor
            FROM collective_commercial_transactions t
            LEFT JOIN commercial_clusters c ON c.cluster_key = t.cluster_key
            WHERE t.is_valid = true
              AND t.asset_type = 'collective_factory'
              AND t.contract_date BETWEEN :start AND :end
              AND t.price > 0
              AND t.gross_area > 0
              AND t.unit_price > 0
            """
        ),
        conn,
        params={"start": start, "end": end},
    )
    frame["cluster_key"] = frame["cluster_key"].astype(str).str.strip()
    for col in ("contract_year", "building_age", "gross_area", "unit_price", "floor"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["floor_code"] = frame["floor"].map(_factory_floor_code)
    frame["building_use"] = frame["building_use"].fillna("").astype(str).str.strip()
    frame["display_label"] = frame["display_label"].fillna("").astype(str).str.strip()
    return frame


def design(frame: pd.DataFrame, bands: list[str]) -> tuple[pd.DataFrame, list[str]]:
    parts = [pd.Series(1.0, index=frame.index, name="const")]
    controls = []
    area = np.log(frame["gross_area"].astype(float))
    if int(pd.Series(area).nunique(dropna=True)) >= 2:
        parts.append(pd.Series(area, index=frame.index, name="ln_area"))
        controls.append("ln_area")
    age = frame["building_age"]
    if int(age.nunique(dropna=True)) >= 2:
        parts.append(age.astype(float).rename("age"))
        controls.append("age")
    years = sorted(int(y) for y in frame["contract_year"].dropna().unique())
    if len(years) >= 2:
        for year in years[1:]:
            parts.append((frame["contract_year"].astype(int) == year).astype(float).rename(f"yr_{year}"))
        controls.append("year")
    for code in bands:
        parts.append((frame["floor_code"] == code).astype(float).rename(code))
    matrix = pd.concat(parts, axis=1)
    keep = [col for col in matrix.columns if col == "const" or col in bands or float(matrix[col].std(ddof=0) or 0) > 0]
    return matrix[keep], controls


def fit_cluster(frame: pd.DataFrame) -> dict | None:
    work = frame.dropna(subset=["floor_code", "unit_price", "gross_area", "contract_year"]).copy()
    work = work[(work["unit_price"] > 0) & (work["gross_area"] > 0)]
    if len(work) < MIN_CLUSTER:
        return None
    counts = work["floor_code"].value_counts()
    if int(counts.get("fac_1", 0)) < MIN_BAND:
        return None
    bands = [code for code in BANDS if int(counts.get(code, 0)) >= MIN_BAND]
    if not bands:
        return None
    matrix, controls = design(work, bands)
    y = np.log(work["unit_price"].astype(float).to_numpy())
    x_values = matrix.to_numpy(dtype=float)
    ok = np.isfinite(y) & np.isfinite(x_values).all(axis=1)
    y = y[ok]
    x_values = x_values[ok]
    matrix = matrix.iloc[np.flatnonzero(ok)]
    if len(y) <= x_values.shape[1] + 1 or len(y) < MIN_CLUSTER:
        return None
    try:
        rank = int(np.linalg.matrix_rank(x_values))
    except np.linalg.LinAlgError:
        return None
    if rank < x_values.shape[1] and "age" in matrix.columns:
        matrix = matrix.drop(columns=["age"])
        controls = [name for name in controls if name != "age"]
        x_values = matrix.to_numpy(dtype=float)
        try:
            rank = int(np.linalg.matrix_rank(x_values))
        except np.linalg.LinAlgError:
            return None
    if rank < x_values.shape[1]:
        return None
    try:
        model = sm.OLS(y, x_values, missing="drop")
        leverage = hat_diag(x_values)
        cov = "HC1" if np.any(leverage >= 0.99) else "HC3"
        robust = model.fit(cov_type=cov)
    except (np.linalg.LinAlgError, ValueError):
        return None
    names = list(matrix.columns)
    params = {name: float(value) for name, value in zip(names, robust.params)}
    ses = {name: float(value) for name, value in zip(names, robust.bse)}
    cells = []
    for code in bands:
        est = params.get(code)
        se = ses.get(code)
        if est is None or se is None or not math.isfinite(est) or not math.isfinite(se) or se < 1e-6:
            continue
        index = 100 * math.exp(est)
        lo = 100 * math.exp(est - 1.96 * se)
        hi = 100 * math.exp(est + 1.96 * se)
        index_r, lo_r, hi_r = _r(index, 1), _r(lo, 1), _r(hi, 1)
        cells.append(
            {
                "band": BAND_LABEL[code],
                "code": code,
                "n": int(counts.get(code, 0)),
                "index": index_r,
                "lo": lo_r,
                "hi": hi_r,
                "above": bool(index_r is not None and index_r > 100),
                "ci_excludes_100": bool(hi_r is not None and lo_r is not None and (hi_r < 100 or lo_r > 100)),
                "cov": cov,
            }
        )
    if not cells:
        return None
    use = str(work["building_use"].mode().iloc[0]) if work["building_use"].ne("").any() else ""
    label = str(work["display_label"].mode().iloc[0]) if work["display_label"].ne("").any() else ""
    return {
        "label": label,
        "building_use": use,
        "n": int(len(work)),
        "n_floor_1": int(counts.get("fac_1", 0)),
        "controls": controls,
        "cells": cells,
    }


def summarize(rows: list[dict], band: str) -> dict:
    cells = []
    for row in rows:
        for cell in row["cells"]:
            if cell["band"] == band:
                cells.append(cell)
    indexes = [cell["index"] for cell in cells if cell["index"] is not None]
    if not indexes:
        return {"band": band, "n_clusters": 0}
    above = [cell for cell in cells if cell["above"]]
    decided = [cell for cell in cells if cell["ci_excludes_100"]]
    decided_above = [cell for cell in decided if cell["above"]]
    return {
        "band": band,
        "n_clusters": len(cells),
        "median": _r(float(np.median(indexes)), 1),
        "p25": _r(float(np.percentile(indexes, 25)), 1),
        "p75": _r(float(np.percentile(indexes, 75)), 1),
        "share_above_100": _r(len(above) / len(cells), 3),
        "share_ci_excludes_100": _r(len(decided) / len(cells), 3),
        "share_ci_above": _r(len(decided_above) / len(cells), 3),
        "share_ci_below": _r((len(decided) - len(decided_above)) / len(cells), 3),
    }


def use_counts(frame: pd.DataFrame) -> list[dict]:
    counts = frame.loc[frame["building_use"] != "", "building_use"].value_counts()
    return [{"building_use": str(name), "n": int(n)} for name, n in counts.head(12).items()]


def main() -> None:
    eng = get_collective_engine()
    if eng is None:
        raise SystemExit("COLLECTIVE_DATABASE_URL 없음")
    with eng.connect() as conn:
        as_of, _ = latest_mart_snapshot(conn)
        if as_of is None:
            raise SystemExit("집합공장 기준월이 없습니다")
        start, end = period_bounds_for_window(as_of, 5)
        trades = load_trades(conn, start, end)
    uses = use_counts(trades)
    knowledge = any("지식산업" in row["building_use"] for row in uses)
    fitted = []
    funnel = {"clusters": 0, "n_below_30": 0, "no_first_floor": 0, "no_other_band": 0, "not_identified": 0, "entered": 0}
    for _, grp in trades.groupby("cluster_key", sort=False):
        funnel["clusters"] += 1
        work = grp.dropna(subset=["floor_code", "unit_price", "gross_area"]).copy()
        work = work[(work["unit_price"] > 0) & (work["gross_area"] > 0)]
        counts = work["floor_code"].value_counts()
        if len(work) < MIN_CLUSTER:
            funnel["n_below_30"] += 1
            continue
        if int(counts.get("fac_1", 0)) < MIN_BAND:
            funnel["no_first_floor"] += 1
            continue
        if not any(int(counts.get(code, 0)) >= MIN_BAND for code in BANDS):
            funnel["no_other_band"] += 1
            continue
        result = fit_cluster(grp)
        if result is None:
            funnel["not_identified"] += 1
            continue
        funnel["entered"] += 1
        fitted.append(result)
    tables = [summarize(fitted, BAND_LABEL[code]) for code in BANDS]
    knowledge_tables = None
    other_tables = None
    n_knowledge = 0
    if knowledge:
        know_rows = [row for row in fitted if "지식산업" in row["building_use"]]
        other_rows = [row for row in fitted if "지식산업" not in row["building_use"]]
        n_knowledge = len(know_rows)
        knowledge_tables = [summarize(know_rows, BAND_LABEL[code]) for code in BANDS]
        other_tables = [summarize(other_rows, BAND_LABEL[code]) for code in BANDS]
    payload = {
        "status": "executed",
        "as_of": as_of.isoformat(),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "window_years": 5,
        "unit": "집합공장 상품군 클러스터. 도로·용도·연식·면적구간 단위이고 건물 키 하나는 아니다.",
        "reference": "1층=100. 표본에 1층이 10건 미만이면 그 클러스터는 본표에서 뺀다.",
        "bands": "지하, 1층, 2층, 3층 이상. 상가의 고층·초고층 구간은 쓰지 않는다.",
        "entry": {"cluster_n": MIN_CLUSTER, "band_n": MIN_BAND},
        "n_trades": int(len(trades)),
        "funnel": funnel,
        "n_clusters_entered": len(fitted),
        "entered": [
            {"label": row["label"], "building_use": row["building_use"], "n": row["n"], "cells": row["cells"]}
            for row in fitted
        ],
        "tables": tables,
        "building_use_top": uses,
        "knowledge_split": knowledge,
        "n_knowledge_clusters": n_knowledge,
        "knowledge_tables": knowledge_tables,
        "other_tables": other_tables,
        "notes": [
            "지수는 클러스터 안 로그 ㎡당 가격 회귀다. 연면적 로그, 연식, 계약연도 더미를 넣을 수 있으면 넣는다.",
            "표준오차는 HC3다. 레버리지가 0.99 이상인 클러스터만 HC1이다.",
            "신뢰구간이 100을 가로지르면 그 클러스터의 방향은 정해지지 않은 것으로 센다.",
            "아파트 층 지수, 집합상가 1층=100과 더하지 않는다. 집합상가는 다시 추정하지 않는다.",
            "클러스터 키와 지번은 스냅샷에 넣지 않는다.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT),
                "trades": payload["n_trades"],
                "clusters": payload["n_clusters_entered"],
                "tables": tables,
                "knowledge": knowledge,
                "n_knowledge": n_knowledge,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
