"""Satisfaction grade lookup — domain config JSON (R2)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

GRADE_ORDER = ("excellent", "good", "fair", "poor")


@dataclass(frozen=True)
class GradeLookupResult:
    grade: str
    stars: int
    label_ko: str
    proceed_twin: bool
    note: str | None = None


def _config_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "satisfaction" / f"{name}.json"


@lru_cache(maxsize=4)
def _load_built_config() -> dict[str, Any]:
    with _config_path("built").open(encoding="utf-8") as fh:
        return json.load(fh)


def _merged_grade_row(config: dict[str, Any], grade: str, asset_slice: str) -> dict[str, Any]:
    base = dict((config.get("grades") or {}).get(grade) or {})
    overrides = ((config.get("slices") or {}).get(asset_slice) or {}).get(grade) or {}
    base.update(overrides)
    return base


def _normalize_slice(asset_slice: str) -> str:
    s = (asset_slice or "commercial").strip().lower()
    if s in {"all", "unified"}:
        return "unified"
    if "," in s:
        return "unified"
    return s


def lookup_built_satisfaction(
    *,
    cv_mape: float | None,
    selection_n: int,
    asset_slice: str,
) -> GradeLookupResult:
    config = _load_built_config()
    slice_key = _normalize_slice(asset_slice)
    proceed_cutoff = str(config.get("proceed_twin_when_grade_at_or_below") or "fair").lower()

    if cv_mape is None:
        return GradeLookupResult(
            grade="insufficient_cv",
            stars=0,
            label_ko="CV 미산출",
            proceed_twin=True,
            note="CV-MAPE 산출 불가 — Twin pool 검토 권장",
        )

    chosen = "poor"
    stars = 2
    label_ko = "미흡"
    for grade in GRADE_ORDER:
        row = _merged_grade_row(config, grade, slice_key)
        max_cv = float(row.get("max_cv_mape", 999))
        min_n = int(row.get("min_selection_n", 0))
        if cv_mape <= max_cv and selection_n >= min_n:
            chosen = grade
            stars = int(row.get("stars", 2))
            label_ko = str(row.get("label_ko", grade))
            break

    try:
        proceed_twin = GRADE_ORDER.index(chosen) >= GRADE_ORDER.index(proceed_cutoff)
    except ValueError:
        proceed_twin = chosen in {"fair", "poor", "insufficient_cv"}

    return GradeLookupResult(
        grade=chosen,
        stars=stars,
        label_ko=label_ko,
        proceed_twin=proceed_twin,
    )


def built_min_local_n() -> int:
    return int(_load_built_config().get("min_local_n") or 15)


def built_min_fit_n() -> int:
    return int(_load_built_config().get("min_fit_n") or 10)
