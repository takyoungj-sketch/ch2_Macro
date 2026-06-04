"""단지 내 층·동·면적형 ㎡당가 효용지수 (기준=단지 중앙값 100)."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from app.collective.analysis_gates import MIN_RELIABLE_BUILDING_STATS
from app.stats_utils import _rnd_price

AREA_BUCKET_M2 = 30


def _area_bucket(v: float) -> float:
    return round(v / AREA_BUCKET_M2) * AREA_BUCKET_M2


def _area_label(v: float) -> str:
    if v == int(v):
        return f"{int(v)}㎡"
    return f"{v:g}㎡"


def _floor_label(v: float) -> str:
    if v == int(v):
        return f"{int(v)}층"
    return f"{v:g}층"


def _dong_label(v: str) -> str:
    s = str(v).strip()
    return s if s else "—"


def compute_floor_index(
    df: pd.DataFrame,
    *,
    asset_type: str,
    dimension: str = "floor",
) -> dict:
    """dimension: floor | dong | area (area = 30㎡ 구간 area_bucket)"""
    work = df.dropna(subset=["unit_price"]).copy()
    work = work[work["unit_price"].astype(float) > 0]
    n_total = len(work)
    if n_total == 0:
        return {
            "n_total": 0,
            "baseline_median": None,
            "dimension": dimension,
            "cells": [],
        }

    baseline = float(np.median(work["unit_price"].astype(float)))
    if baseline <= 0:
        baseline = float(np.mean(work["unit_price"].astype(float)))

    groups: dict[str, list[float]] = defaultdict(list)
    area_sort: dict[str, float | None] = {}

    if dimension == "area":
        for _, row in work.iterrows():
            ea = row.get("exclusive_area")
            if ea is None or (isinstance(ea, float) and pd.isna(ea)):
                key = "—"
                area_sort[key] = None
            else:
                try:
                    fv = float(ea)
                    if fv <= 0:
                        key = "—"
                        area_sort[key] = None
                    else:
                        bucket = _area_bucket(fv)
                        key = _area_label(bucket)
                        area_sort[key] = bucket
                except (TypeError, ValueError):
                    key = "—"
                    area_sort[key] = None
            groups[key].append(float(row["unit_price"]))
    elif dimension == "dong":
        if asset_type == "officetel":
            dimension = "floor"
        else:
            for _, row in work.iterrows():
                dong = row.get("dong")
                if dong is None or (isinstance(dong, float) and pd.isna(dong)):
                    key = "—"
                else:
                    key = _dong_label(str(dong))
                groups[key].append(float(row["unit_price"]))
    if dimension == "floor":
        for _, row in work.iterrows():
            fl = row.get("floor")
            if fl is None or (isinstance(fl, float) and pd.isna(fl)):
                key = "—"
            else:
                try:
                    fv = float(fl)
                    key = _floor_label(fv)
                except (TypeError, ValueError):
                    key = "—"
            groups[key].append(float(row["unit_price"]))

    cells = []
    for label, prices in groups.items():
        arr = np.asarray(prices, dtype=float)
        n = int(len(arr))
        mean_p = float(np.mean(arr))
        index_val = round(mean_p / baseline * 100, 1) if baseline > 0 else None
        cells.append(
            {
                "label": label,
                "floor": _parse_floor_key(label) if dimension == "floor" else None,
                "dong": label if dimension == "dong" and label != "—" else None,
                "area": area_sort.get(label) if dimension == "area" else None,
                "count": n,
                "mean_unit_price": _rnd_price(mean_p),
                "index": index_val,
                "is_reliable": n >= MIN_RELIABLE_BUILDING_STATS,
            }
        )

    def _sort_key(c: dict):
        if dimension == "area":
            if c.get("area") is not None:
                return (0, c["area"])
            return (1, 0)
        if dimension == "floor" and c.get("floor") is not None:
            return (0, c["floor"])
        if dimension == "floor" and c["label"] == "—":
            return (2, 0)
        return (1, c["label"])

    cells.sort(key=_sort_key)

    return {
        "n_total": n_total,
        "baseline_median": _rnd_price(baseline),
        "dimension": dimension,
        "cells": cells,
    }


def _parse_floor_key(label: str) -> float | None:
    if label == "—":
        return None
    s = label.replace("층", "").strip()
    try:
        return float(s)
    except ValueError:
        return None
