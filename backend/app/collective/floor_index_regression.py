"""주거 단지 회귀 기반 효용지수 — 층·동·면적형·권리 (변수 통제 semi-log OLS)."""

from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.collective.analysis_gates import MIN_RELIABLE_BUILDING_STATS
from app.collective.area_buckets import label_for_gross_area
from app.collective.floor_index import _area_bucket, _area_label, _dong_label
from app.collective.regression.engine import (
    _FACTORY_FLOOR_LABELS,
    _REL_FLOOR_LABELS,
    _ROWHOUSE_FLOOR_LABELS,
    _factory_floor_code,
    _floor_group_label,
    relative_floor_group,
    rowhouse_floor_group,
)
from app.collective_commercial.floor_index_regression import SHOP_FLOOR_GROUPS, shop_floor_group
from app.stats_utils import _rnd_price

COMMERCIAL_ASSET_TYPES = frozenset({"collective_shop", "collective_factory"})
SHOP_FLOOR_SPECS: list[tuple[str, str, float]] = [
    (label, f"shop_{code}", sort_key) for label, code, sort_key in SHOP_FLOOR_GROUPS
]
SHOP_FLOOR_LABELS: dict[str, str] = {code: label for label, code, _ in SHOP_FLOOR_SPECS}
SHOP_DISPLAY_CODE = "shop_f1"

REFERENCE_FLOOR_CODE = "floor_rel_1"
REFERENCE_FLOOR_LABEL = "1층"
DISPLAY_FLOOR_CODE = "floor_rel_1"
DISPLAY_FLOOR_LABEL = "1층"
MIN_GROUP_FOR_DUMMY = 5

# (label, code, sort_key)
RESIDENTIAL_FLOOR_GROUPS: list[tuple[str, str, float]] = [
    ("1층", "floor_rel_1", 1),
    ("저층부", "floor_rel_low", 2),
    ("중층부", "floor_rel_mid", 3),
    ("고층부", "floor_rel_high", 4),
    ("관측 최상층", "floor_rel_top", 5),
]

GROUPED_FLOOR_GROUPS: list[tuple[str, str, float]] = [
    ("1–5층", "floor_grp_1-5", 1),
    ("6–15층", "floor_grp_6-15", 6),
    ("16층+", "floor_grp_16+", 16),
]

GROUPED_FLOOR_LABELS: dict[str, str] = {code: label for label, code, _ in GROUPED_FLOOR_GROUPS}

FACTORY_FLOOR_SPECS: list[tuple[str, str, float]] = [
    (_FACTORY_FLOOR_LABELS[code], code, sort)
    for code, sort in (("fac_b", -1), ("fac_1", 1), ("fac_2", 2), ("fac_3p", 3))
]
ROWHOUSE_FLOOR_SPECS: list[tuple[str, str, float]] = [
    ("1층", "floor_rh_1", 1),
    ("중간층", "floor_rh_mid", 2),
    ("관측 최상층", "floor_rh_top", 3),
]
FLOOR_INDEX_MODES = frozenset({"relative", "dummy", "grouped", "rowhouse", "shop", "factory"})


def _ensure_building_age(work: pd.DataFrame) -> None:
    if "building_age" not in work.columns:
        work["building_age"] = np.nan
    mask = work["building_age"].isna() & work.get("building_year", pd.Series(dtype=float)).notna()
    if mask.any() and "contract_year" in work.columns:
        work.loc[mask, "building_age"] = (
            work.loc[mask, "contract_year"].astype(float) - work.loc[mask, "building_year"].astype(float)
        )


def _max_floor_by_building(work: pd.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    if "building_key" in work.columns:
        for bk, grp in work.groupby("building_key"):
            fl = grp["floor"].dropna().astype(float)
            out[str(bk)] = float(fl.max()) if len(fl) else 1.0
    else:
        fl = work["floor"].dropna().astype(float)
        out["__single__"] = float(fl.max()) if len(fl) else 1.0
    return out


def _relative_floor_code(row: pd.Series, max_by_bk: dict[str, float]) -> str | None:
    fl = row.get("floor")
    if fl is None or (isinstance(fl, float) and pd.isna(fl)):
        return None
    try:
        f = float(fl)
    except (TypeError, ValueError):
        return None
    bk = str(row.get("building_key", "__single__"))
    mx = max_by_bk.get(bk, f)
    return relative_floor_group(f, mx)


def _dong_code(label: str) -> str:
    s = re.sub(r"[^\w가-힣]+", "_", str(label).strip())
    return f"dong_{s[:48]}" if s else "dong_unknown"


def _area_code(bucket: float) -> str:
    return f"area_{int(bucket) if bucket == int(bucket) else bucket:g}"


def _rights_code(label: str) -> str:
    s = re.sub(r"[^\w가-힣]+", "_", str(label).strip())
    return f"rights_{s[:48]}" if s else "rights_unknown"


def _floor_dummy_code(floor: float) -> str:
    if floor == int(floor):
        return f"floor_{int(floor)}"
    return f"floor_{float(floor):g}"


def _floor_dummy_label(floor: float) -> str:
    if float(floor) == 1:
        return "1층"
    if float(floor) == int(floor):
        return f"{int(floor)}층"
    return f"{float(floor)}층"


def _shop_floor_index_code(floor: object) -> str | None:
    grp = shop_floor_group(floor)
    if grp is None:
        return None
    return f"shop_{grp[1]}"


def _factory_floor_index_code(floor: object) -> str | None:
    return _factory_floor_code(floor)


def _rowhouse_floor_code(row: pd.Series, max_by_bk: dict[str, float]) -> str | None:
    fl = row.get("floor")
    if fl is None or (isinstance(fl, float) and pd.isna(fl)):
        return None
    try:
        f = float(fl)
    except (TypeError, ValueError):
        return None
    bk = str(row.get("building_key", "__single__"))
    mx = max_by_bk.get(bk, f)
    return rowhouse_floor_group(f, mx)


def _display_reference_for_mode(floor_mode: str) -> tuple[str, str]:
    if floor_mode == "shop":
        return SHOP_DISPLAY_CODE, "1층"
    if floor_mode == "factory":
        return "fac_1", "1층"
    if floor_mode == "rowhouse":
        return "floor_rh_1", "1층"
    if floor_mode == "grouped":
        return "floor_grp_1-5", "1–5층"
    if floor_mode == "dummy":
        return "floor_1", "1층"
    return DISPLAY_FLOOR_CODE, DISPLAY_FLOOR_LABEL


def _build_floor_dimension_groups(
    work: pd.DataFrame,
    floor_mode: str,
) -> tuple[list[tuple[str, str, float | None]], pd.DataFrame, list[str]]:
    """층 탭 분석 차원 — floor_mode별 구간·더미 spec."""
    warnings: list[str] = []
    if floor_mode == "shop":
        specs = [(label, code, float(sort)) for label, code, sort in SHOP_FLOOR_SPECS]
        work = work.copy()
        work["index_group_code"] = work["floor"].apply(_shop_floor_index_code)
        work["index_group_label"] = work["index_group_code"].map(SHOP_FLOOR_LABELS)
        return specs, work, warnings

    if floor_mode == "factory":
        specs = list(FACTORY_FLOOR_SPECS)
        work = work.copy()
        work["index_group_code"] = work["floor"].apply(_factory_floor_index_code)
        work["index_group_label"] = work["index_group_code"].map(_FACTORY_FLOOR_LABELS)
        return specs, work, warnings

    if floor_mode == "rowhouse":
        specs = list(ROWHOUSE_FLOOR_SPECS)
        work = work.copy()
        work["index_group_code"] = work["floor_index_code"]
        work["index_group_label"] = work["floor_index_code"].map(_ROWHOUSE_FLOOR_LABELS)
        return specs, work, warnings

    mode = floor_mode if floor_mode in FLOOR_INDEX_MODES else "relative"

    if mode == "relative":
        specs = list(RESIDENTIAL_FLOOR_GROUPS)
        work = work.copy()
        work["index_group_code"] = work["floor_index_code"]
        work["index_group_label"] = work["floor_index_code"].map(_REL_FLOOR_LABELS)
        return specs, work, warnings

    if mode == "grouped":
        specs = list(GROUPED_FLOOR_GROUPS)
        work = work.copy()
        work["index_group_code"] = work["floor"].apply(
            lambda x: _floor_group_label(float(x)) if x is not None and not pd.isna(x) else None
        )
        work["index_group_label"] = work["index_group_code"].map(GROUPED_FLOOR_LABELS)
        return specs, work, warnings

    # dummy — 개별 층
    work = work.copy()
    floors = sorted({float(f) for f in work["floor"].dropna().astype(float)})
    specs: list[tuple[str, str, float | None]] = [
        (_floor_dummy_label(f), _floor_dummy_code(f), f) for f in floors
    ]
    work["index_group_code"] = work["floor"].apply(
        lambda x: _floor_dummy_code(float(x)) if x is not None and not pd.isna(x) else None
    )
    work["index_group_label"] = work["index_group_code"].map(
        {code: label for label, code, _ in specs}
    )
    return specs, work, warnings


def _pick_regression_reference(
    group_counts: dict[str, int],
    group_specs: list[tuple[str, str, float | None]],
) -> tuple[str, str] | None:
    """회귀 omitted category = 거래 건수가 가장 많은 구간 (최소 표본 충족)."""
    eligible = [
        (label, code)
        for label, code, _ in group_specs
        if group_counts.get(code, 0) >= MIN_GROUP_FOR_DUMMY
    ]
    if not eligible:
        return None
    label, code = max(eligible, key=lambda pair: group_counts.get(pair[1], 0))
    return code, label


def _pick_floor_regression_reference(group_counts: dict[str, int]) -> tuple[str, str] | None:
    return _pick_regression_reference(group_counts, RESIDENTIAL_FLOOR_GROUPS)


def _period_code(year: float | None, month: float | None) -> str | None:
    """거래 시점 → 반기 코드(예: 2025H1). 월 결측이면 연도 코드로 폴백."""
    if year is None or pd.isna(year):
        return None
    y = int(year)
    if month is None or pd.isna(month):
        return f"{y}"
    m = int(month)
    return f"{y}H{1 if m <= 6 else 2}"


def _add_time_dummies(reg: pd.DataFrame, parts: list[pd.DataFrame], controls: list[str]) -> None:
    """거래 시점(반기) 통제 — 표본 최다 반기를 기준(omitted)으로 더미화.

    선택 구간이 수년이면 시장 추세가 층·면적 분포와 교란되므로, 효용지수에서
    시장 상승/하락분을 제거하기 위한 통제. 더미 자체는 cell로 노출하지 않는다.
    """
    if "contract_year" not in reg.columns:
        return
    months = reg["contract_month"] if "contract_month" in reg.columns else pd.Series(np.nan, index=reg.index)
    reg["_period_code"] = [
        _period_code(y, m) for y, m in zip(reg["contract_year"], months)
    ]
    counts = reg["_period_code"].dropna().value_counts()
    if len(counts) < 2:
        return
    ref = str(counts.idxmax())
    added = False
    for code, cnt in counts.items():
        if code == ref or cnt < MIN_GROUP_FOR_DUMMY:
            continue
        col = f"time_{code}"
        reg[col] = (reg["_period_code"] == code).astype(float)
        parts.append(reg[[col]])
        added = True
    if added:
        controls.append("contract_period")


def _collinearity_diagnostics(x_const: pd.DataFrame) -> tuple[dict, list[str]]:
    """설계행렬 다중공선성 진단 — VIF(연속·차원 더미) + 조건수(스케일 불변).

    면적·층 등 통제변수가 분석 차원과 실제로 겹치는지는 이론이 아니라 VIF로 판정한다.
    time_*·bldg_* 더미는 통제 목적상 공선성이 자연스러우므로 경고 대상에서 제외한다.
    """
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    warnings: list[str] = []
    arr = x_const.to_numpy(dtype=float)
    cols = list(x_const.columns)

    vif_targets = [
        c
        for c in cols
        if c in ("ln_exclusive_area", "building_age")
        or c.startswith("idx_")
        or c.startswith("ctrl_")
    ]
    vifs: dict[str, float] = {}
    for c in vif_targets:
        try:
            v = float(variance_inflation_factor(arr, cols.index(c)))
        except Exception:
            continue
        if np.isfinite(v):
            vifs[c] = round(v, 2)

    cond_no: float | None = None
    try:
        norms = np.linalg.norm(arr, axis=0)
        norms[norms == 0] = 1.0
        cond_no = float(np.linalg.cond(arr / norms))
    except Exception:
        cond_no = None

    # 헤드라인 경고는 관심 변수(연속 통제·차원 더미) 기준. 층 통제 더미(ctrl_*)는
    # 상호배타 더미 특성상 공선성이 자연스러우므로 표시만 하고 경고에서는 제외.
    primary = {c: v for c, v in vifs.items() if not c.startswith("ctrl_")}
    max_vif = max(primary.values()) if primary else None
    max_vif_term = max(primary, key=lambda k: primary[k]) if primary else None
    diag = {
        "max_vif": max_vif,
        "max_vif_term": max_vif_term,
        "condition_number": round(cond_no, 1) if cond_no is not None else None,
        "vifs": vifs,
    }

    if max_vif is not None and max_vif >= 10:
        warnings.append(f"다중공선성 높음 — 최대 VIF {max_vif} ({max_vif_term}), 통제변수 해석 주의")
    elif max_vif is not None and max_vif >= 5:
        warnings.append(f"다중공선성 주의 — 최대 VIF {max_vif} ({max_vif_term})")
    if cond_no is not None and cond_no >= 100:
        warnings.append(f"설계행렬 조건수 {round(cond_no)} — 수치 불안정·공선성 가능")

    return diag, warnings


def _add_floor_control_dummies(
    reg: pd.DataFrame,
    parts: list[pd.DataFrame],
    controls: list[str],
    *,
    floor_mode: str = "relative",
) -> None:
    """층 구간을 통제변수로. 빠진 기준은 표본이 있는 1층, 없으면 거래가 많은 구간."""
    if "floor_index_code" not in reg.columns or reg.empty:
        return
    if floor_mode == "shop":
        groups: list[tuple[str, str, float | None]] = list(SHOP_FLOOR_SPECS)
        ref = SHOP_DISPLAY_CODE
        control_name = "shop_floor"
    elif floor_mode == "factory":
        groups = list(FACTORY_FLOOR_SPECS)
        ref = "fac_1"
        control_name = "factory_floor"
    elif floor_mode == "rowhouse":
        groups = list(ROWHOUSE_FLOOR_SPECS)
        ref = "floor_rh_1"
        control_name = "rowhouse_floor"
    else:
        groups = list(RESIDENTIAL_FLOOR_GROUPS)
        ref = REFERENCE_FLOOR_CODE
        control_name = "relative_floor"
    counts = reg["floor_index_code"].astype(str).value_counts()
    eligible = [code for _, code, _ in groups if int(counts.get(code, 0)) >= MIN_GROUP_FOR_DUMMY]
    if len(eligible) < 2:
        return
    omit = ref if ref in eligible else max(eligible, key=lambda c: int(counts.get(c, 0)))
    added = False
    for code in eligible:
        if code == omit:
            continue
        col = f"ctrl_{code}"
        reg[col] = (reg["floor_index_code"].astype(str) == code).astype(float)
        parts.append(reg[[col]])
        added = True
    if added:
        controls.append(control_name)


def _add_building_fe(
    reg: pd.DataFrame,
    parts: list[pd.DataFrame],
    controls: list[str],
    *,
    reference_key: str,
) -> list[str]:
    """코호트: 단지 고정효과 (표본 최다 단지 = 기준)."""
    if "building_key" not in reg.columns:
        return []
    keys = reg["building_key"].astype(str)
    if keys.nunique() < 2:
        return []
    dummy_keys = sorted(k for k in keys.unique() if k != reference_key)
    added: list[str] = []
    for bk in dummy_keys:
        col = f"bldg_{re.sub(r'[^a-zA-Z0-9]+', '_', bk)[:32]}"
        reg[col] = (keys == bk).astype(float)
        if reg[col].sum() >= MIN_GROUP_FOR_DUMMY:
            parts.append(reg[[col]])
            added.append(bk)
    if added:
        controls.append("building_fixed_effects")
    return added


def _add_building_use_dummies(reg: pd.DataFrame, parts: list[pd.DataFrame], controls: list[str]) -> None:
    if "building_use" not in reg.columns or not reg["building_use"].notna().any():
        return
    series = reg["building_use"].astype(str).str.strip().replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
    if series.dropna().nunique() < 2:
        return
    dummies = pd.get_dummies(series, prefix="use", drop_first=True)
    kept = [c for c in dummies.columns if float(dummies[c].sum()) >= MIN_GROUP_FOR_DUMMY]
    if not kept:
        return
    for col in kept:
        reg[col] = dummies[col].astype(float)
        parts.append(reg[[col]])
    controls.append("building_use")


_MISSING_INDEX_CODES = frozenset({"dong_missing", "area_missing", "rights_missing"})


def _period_series(reg: pd.DataFrame) -> pd.Series:
    if "contract_year" not in reg.columns:
        return pd.Series(np.nan, index=reg.index, dtype=object)
    months = (
        reg["contract_month"]
        if "contract_month" in reg.columns
        else pd.Series(np.nan, index=reg.index)
    )
    return pd.Series(
        [_period_code(y, m) for y, m in zip(reg["contract_year"], months)],
        index=reg.index,
        dtype=object,
    )


def _codes_at_least(series: pd.Series, minimum: int) -> set[str]:
    counts = series.dropna().astype(str).value_counts()
    return {str(code) for code, cnt in counts.items() if int(cnt) >= minimum}


def _age_collinear_with_time(reg: pd.DataFrame) -> bool:
    """연식이 절편 또는 반기 더미와 겹치면 True. 그 경우 연식은 통제에서 뺀다."""
    if "building_age" not in reg.columns or reg.empty:
        return True
    age = pd.to_numeric(reg["building_age"], errors="coerce")
    known = age.notna()
    if int(known.sum()) < 2 or int(age[known].nunique()) < 2:
        return True
    if "contract_year" not in reg.columns:
        return False
    period = _period_series(reg)[known]
    sub_age = age[known]
    counts = period.dropna().astype(str).value_counts()
    eligible = [str(code) for code, cnt in counts.items() if int(cnt) >= MIN_GROUP_FOR_DUMMY]
    if len(eligible) < 2:
        return False
    ref = str(counts.idxmax())
    columns = [
        (period.astype(str) == code).astype(float).to_numpy()
        for code in eligible
        if code != ref
    ]
    if not columns:
        return False
    y = sub_age.to_numpy(dtype=float)
    base = np.column_stack([np.ones(len(y)), *columns])
    full = np.column_stack([base, y])
    return int(np.linalg.matrix_rank(full)) == int(np.linalg.matrix_rank(base))


def _drop_sparse_levels(reg: pd.DataFrame, series: pd.Series) -> pd.DataFrame:
    """둘 이상의 범주가 있을 때 5건 미만·결측 행을 뺀다.

    더미를 생략한 채 남겨 두면 그 행이 기준 범주와 같은 효과가 된다.
    5건 이상인 범주가 하나도 없으면 통제를 만들지 않으므로 행은 그대로 둔다.
    """
    if reg.empty:
        return reg
    key = series.astype(str).where(series.notna(), other="__missing__")
    counts = key.value_counts()
    if len(counts) < 2:
        return reg
    keep = {
        str(code)
        for code, cnt in counts.items()
        if str(code) != "__missing__" and int(cnt) >= MIN_GROUP_FOR_DUMMY
    }
    if not keep:
        return reg
    if len(keep) == len(counts):
        return reg
    return reg.loc[key.isin(keep)]


def _regression_sample(
    work: pd.DataFrame,
    *,
    effective_dim: str,
    is_commercial: bool,
) -> tuple[pd.DataFrame, dict]:
    """결측·소표본 범주를 뺀 최종 회귀 표본.

    층·반기·건물·용도에서 더미를 만들지 않는 범주는 표본에서도 뺀다.
    빼는 동안 다른 범주가 5건 미만이 되면 다시 뺀다.
    """
    reg = work.copy()
    reg = reg[reg["index_group_code"].notna()]
    reg = reg[~reg["index_group_code"].astype(str).isin(_MISSING_INDEX_CODES)]
    reg = reg[pd.to_numeric(reg["exclusive_area"], errors="coerce") > 0]
    reg = reg[pd.to_numeric(reg["unit_price"], errors="coerce") > 0]
    notes: dict = {
        "use_time": False,
        "use_fe": False,
        "use_use": False,
        "use_floor_control": False,
        "use_age": False,
        "age_note": None,
        "reference_key": "",
    }
    if reg.empty:
        return reg, notes

    for _ in range(200):
        before_n = len(reg)
        before_codes = tuple(sorted(reg["index_group_code"].astype(str).unique()))
        group = reg["index_group_code"].astype(str)
        reg = reg.loc[group.isin(_codes_at_least(group, MIN_GROUP_FOR_DUMMY))]
        if reg.empty:
            break
        reg = _drop_sparse_levels(reg, _period_series(reg))
        if "building_key" in reg.columns:
            reg = _drop_sparse_levels(reg, reg["building_key"])
        if is_commercial and "building_use" in reg.columns:
            uses = (
                reg["building_use"]
                .astype(str)
                .str.strip()
                .replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
            )
            reg = _drop_sparse_levels(reg, uses)
        if effective_dim != "floor" and "floor_index_code" in reg.columns:
            reg = _drop_sparse_levels(reg, reg["floor_index_code"])
        if reg.empty:
            break
        if not _age_collinear_with_time(reg):
            reg = reg.loc[pd.to_numeric(reg["building_age"], errors="coerce").notna()]
            group = reg["index_group_code"].astype(str)
            reg = reg.loc[group.isin(_codes_at_least(group, MIN_GROUP_FOR_DUMMY))]
        if reg.empty:
            break
        after_codes = tuple(sorted(reg["index_group_code"].astype(str).unique()))
        if len(reg) == before_n and after_codes == before_codes:
            break

    if reg.empty:
        return reg, notes

    notes["use_time"] = len(_codes_at_least(_period_series(reg), MIN_GROUP_FOR_DUMMY)) >= 2
    if "building_key" in reg.columns:
        key_keep = _codes_at_least(reg["building_key"].astype(str), MIN_GROUP_FOR_DUMMY)
        if len(key_keep) >= 2:
            notes["use_fe"] = True
            notes["reference_key"] = str(reg["building_key"].astype(str).value_counts().idxmax())
    if is_commercial and "building_use" in reg.columns:
        uses = (
            reg["building_use"]
            .astype(str)
            .str.strip()
            .replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
        )
        notes["use_use"] = len(_codes_at_least(uses, MIN_GROUP_FOR_DUMMY)) >= 2
    if effective_dim != "floor" and "floor_index_code" in reg.columns:
        notes["use_floor_control"] = (
            len(_codes_at_least(reg["floor_index_code"].astype(str), MIN_GROUP_FOR_DUMMY)) >= 2
        )
    notes["use_age"] = not _age_collinear_with_time(reg)
    if "building_age" in work.columns and work["building_age"].notna().any() and not notes["use_age"]:
        age = pd.to_numeric(work["building_age"], errors="coerce")
        if int(age.nunique(dropna=True)) < 2:
            notes["age_note"] = "연식이 한 값뿐이라 통제에서 뺐습니다."
        else:
            notes["age_note"] = "연식이 거래시점과 겹쳐 통제에서 뺐습니다."
    return reg, notes


def _group_count_maps(
    frame: pd.DataFrame,
) -> tuple[dict[str, int], dict[str, list[float]]]:
    counts: dict[str, int] = defaultdict(int)
    prices: dict[str, list[float]] = defaultdict(list)
    if frame.empty or "index_group_code" not in frame.columns:
        return counts, prices
    for code, price in zip(frame["index_group_code"], frame["unit_price"]):
        key = str(code)
        counts[key] += 1
        prices[key].append(float(price))
    return counts, prices


def _reference_on_sample(
    reg: pd.DataFrame,
    reg_counts: dict[str, int],
    group_specs: list[tuple[str, str, float | None]],
    *,
    effective_dim: str,
) -> tuple[str, str] | None:
    if reg.empty:
        return None
    if effective_dim == "area":
        areas = pd.to_numeric(reg["exclusive_area"], errors="coerce")
        med = float(areas.median())
        nearest = (areas - med).abs().idxmin()
        code = str(reg.loc[nearest, "index_group_code"])
        label = str(reg.loc[nearest, "index_group_label"])
        if reg_counts.get(code, 0) >= MIN_GROUP_FOR_DUMMY:
            return code, label
    return _pick_regression_reference(reg_counts, group_specs)


def _design_rank(x_const: pd.DataFrame) -> int:
    arr = x_const.to_numpy(dtype=float)
    if arr.size == 0:
        return 0
    return int(np.linalg.matrix_rank(arr))


def _contrast_against_base(
    model,
    code: str,
    base_code: str,
    omitted_code: str,
) -> dict | None:
    """exp(β_code − β_base)×100 과 그 대비의 HC3 신뢰구간·p."""
    if code == base_code:
        return None
    names = list(model.params.index)
    row = np.zeros(len(names))

    def _pos(group: str) -> int | None:
        name = f"idx_{group}"
        return names.index(name) if name in names else None

    if code != omitted_code:
        pos = _pos(code)
        if pos is None:
            return None
        row[pos] += 1.0
    if base_code != omitted_code:
        pos = _pos(base_code)
        if pos is None:
            return None
        row[pos] -= 1.0
    if not np.any(row):
        return None
    tested = model.t_test(row.reshape(1, -1))
    effect = float(np.asarray(tested.effect).reshape(-1)[0])
    se = float(np.asarray(tested.sd).reshape(-1)[0])
    p_value = float(np.asarray(tested.pvalue).reshape(-1)[0])
    if not np.isfinite(effect) or not np.isfinite(se):
        return None
    return {
        "gamma": round(effect, 4),
        "p_value": round(p_value, 4) if np.isfinite(p_value) else None,
        "index": round(float(np.exp(effect) * 100), 1),
        "index_lo": round(float(np.exp(effect - 1.96 * se) * 100), 1),
        "index_hi": round(float(np.exp(effect + 1.96 * se) * 100), 1),
    }


def compute_residential_floor_index_regression(
    df: pd.DataFrame,
    *,
    asset_type: str,
    dimension: str = "floor",
    floor_mode: str = "relative",
) -> dict:
    """ln(㎡당단가) ~ ln(전용면적) + 연식 + (층 통제) + 차원 더미 + (코호트 단지 FE)."""
    warnings: list[str] = []
    controls: list[str] = []
    is_commercial = asset_type in COMMERCIAL_ASSET_TYPES
    effective_dim = dimension
    effective_floor_mode = floor_mode if floor_mode in FLOOR_INDEX_MODES else "relative"
    if dimension == "floor":
        if asset_type == "collective_shop" and effective_floor_mode in ("relative", "shop"):
            effective_floor_mode = "shop"
        elif asset_type == "collective_factory" and effective_floor_mode in ("relative", "shop", "factory"):
            effective_floor_mode = "factory"
        elif asset_type == "rowhouse" and effective_floor_mode == "relative":
            effective_floor_mode = "rowhouse"
        elif floor_mode == "linear":
            warnings.append("층 선형은 효용지수 탭에서 지원하지 않습니다. 상대·개별·구간 중 선택하세요.")
            effective_floor_mode = "rowhouse" if asset_type == "rowhouse" else "relative"

    work = df.dropna(subset=["unit_price"]).copy()
    work = work[work["unit_price"].astype(float) > 0]
    n_total = len(work)
    if n_total == 0:
        return _empty_result(dimension, warnings=["유효 거래가 없습니다."])

    _ensure_building_age(work)
    if asset_type == "collective_shop":
        control_floor_mode = "shop"
        work["floor_index_code"] = work["floor"].apply(_shop_floor_index_code)
    elif asset_type == "collective_factory":
        control_floor_mode = "factory"
        work["floor_index_code"] = work["floor"].apply(_factory_floor_index_code)
    elif asset_type == "rowhouse":
        control_floor_mode = "rowhouse"
        max_by_bk = _max_floor_by_building(work)
        work["floor_index_code"] = work.apply(lambda r: _rowhouse_floor_code(r, max_by_bk), axis=1)
    else:
        control_floor_mode = "relative"
        max_by_bk = _max_floor_by_building(work)
        work["floor_index_code"] = work.apply(lambda r: _relative_floor_code(r, max_by_bk), axis=1)

    if dimension == "dong" and asset_type in ("officetel", "presale"):
        effective_dim = "floor"

    group_specs: list[tuple[str, str, float | None]] = []
    reference_code = ""
    reference_label = ""

    if effective_dim == "floor":
        work = work[work["floor_index_code"].notna()].copy()
        if work.empty:
            return _empty_result(effective_dim, warnings=["층 정보가 있는 거래가 없습니다."])
        group_specs, work, mode_warnings = _build_floor_dimension_groups(work, effective_floor_mode)
        warnings.extend(mode_warnings)
        work = work[work["index_group_code"].notna()].copy()
        if work.empty:
            return _empty_result(effective_dim, warnings=["층 정보가 있는 거래가 없습니다."])
        reference_code = ""
        reference_label = ""

    elif effective_dim == "dong":
        codes: list[str] = []
        labels: list[str] = []
        dong_labels: dict[str, str] = {}
        for _, row in work.iterrows():
            dong = row.get("dong")
            if dong is None or (isinstance(dong, float) and pd.isna(dong)):
                lbl = "—"
            else:
                lbl = _dong_label(str(dong))
            code = _dong_code(lbl) if lbl != "—" else "dong_missing"
            dong_labels[code] = lbl
            codes.append(code)
            labels.append(lbl)
        work["index_group_code"] = codes
        work["index_group_label"] = labels
        counts = work["index_group_code"].value_counts()
        valid = counts[counts.index != "dong_missing"]
        if valid.empty:
            return _empty_result(effective_dim, warnings=["동 정보가 있는 거래가 없습니다."])
        reference_code = str(valid.idxmax())
        reference_label = dong_labels.get(reference_code, reference_code)
        for code, cnt in counts.items():
            if code == "dong_missing":
                continue
            group_specs.append((dong_labels[code], code, None))

    elif effective_dim == "area":
        codes: list[str] = []
        labels: list[str] = []
        area_meta: dict[str, tuple[str, float | None]] = {}
        ledger_area = asset_type in ("collective_factory", "collective_shop")
        area_prefix = "fac" if asset_type == "collective_factory" else "shop"
        for _, row in work.iterrows():
            ea = row.get("exclusive_area")
            if ea is None or (isinstance(ea, float) and pd.isna(ea)) or float(ea) <= 0:
                code, lbl, sort_v = "area_missing", "—", None
            elif ledger_area:
                lbl, sort_v = label_for_gross_area(asset_type, float(ea))
                code = f"area_{area_prefix}_{int(sort_v) if sort_v is not None else 'x'}"
            else:
                bucket = _area_bucket(float(ea))
                lbl = _area_label(bucket)
                code = _area_code(bucket)
                sort_v = bucket
            area_meta[code] = (lbl, sort_v)
            codes.append(code)
            labels.append(lbl)
        work["index_group_code"] = codes
        work["index_group_label"] = labels
        valid = work[work["index_group_code"] != "area_missing"]
        if valid.empty:
            return _empty_result(effective_dim, warnings=["면적 정보가 있는 거래가 없습니다."])
        med = float(valid["exclusive_area"].astype(float).median())
        if ledger_area:
            ref_lbl, ref_sort = label_for_gross_area(asset_type, med)
            reference_code = f"area_{area_prefix}_{int(ref_sort) if ref_sort is not None else 'x'}"
            reference_label = ref_lbl
        else:
            ref_bucket = _area_bucket(med)
            reference_code = _area_code(ref_bucket)
            reference_label = _area_label(ref_bucket)
        for code in sorted(area_meta.keys(), key=lambda c: (area_meta[c][1] is None, area_meta[c][1] or 0)):
            if code == "area_missing":
                continue
            lbl, sort_v = area_meta[code]
            group_specs.append((lbl, code, sort_v))

    elif effective_dim == "rights":
        codes: list[str] = []
        labels: list[str] = []
        rights_meta: dict[str, str] = {}
        for _, row in work.iterrows():
            hs = row.get("housing_subtype")
            if hs is None or (isinstance(hs, float) and pd.isna(hs)):
                lbl = "—"
            else:
                lbl = str(hs).strip() or "—"
            code = _rights_code(lbl) if lbl != "—" else "rights_missing"
            rights_meta[code] = lbl
            codes.append(code)
            labels.append(lbl)
        work["index_group_code"] = codes
        work["index_group_label"] = labels
        counts = work["index_group_code"].value_counts()
        valid = counts[counts.index != "rights_missing"]
        if valid.empty:
            return _empty_result(effective_dim, warnings=["권리 정보가 있는 거래가 없습니다."])
        reference_code = str(valid.idxmax())
        reference_label = rights_meta.get(reference_code, reference_code)
        for code, _ in counts.items():
            if code == "rights_missing":
                continue
            group_specs.append((rights_meta[code], code, None))

    else:
        return _empty_result(dimension, warnings=[f"지원하지 않는 dimension: {dimension}"])

    n_total = len(work)
    baseline = float(np.median(work["unit_price"].astype(float)))
    raw_counts, raw_prices = _group_count_maps(work)
    reg, sample_meta = _regression_sample(
        work,
        effective_dim=effective_dim,
        is_commercial=is_commercial,
    )
    if sample_meta.get("age_note"):
        warnings.append(sample_meta["age_note"])
    reg_counts, _ = _group_count_maps(reg)

    for label, code, _ in group_specs:
        raw_n = int(raw_counts.get(code, 0))
        reg_n = int(reg_counts.get(code, 0))
        if raw_n <= 0 or reg_n >= MIN_GROUP_FOR_DUMMY:
            continue
        if raw_n < MIN_GROUP_FOR_DUMMY:
            warnings.append(f"{label} n={raw_n} — 표본 부족으로 회귀에서 제외, 지수 미산출")
        else:
            warnings.append(f"{label} 원자료 {raw_n}건 — 최종 회귀 표본에 남지 않아 지수 미산출")

    def _blank(ref_label: str):
        return _result_with_cells(
            effective_dim,
            ref_label,
            [],
            n_total,
            0,
            None,
            baseline,
            _cells_from_regression(
                group_specs,
                reg_counts,
                raw_prices,
                "",
                {},
                effective_dim,
                raw_counts=raw_counts,
                publish=False,
            ),
            list(warnings),
            floor_mode=effective_floor_mode if effective_dim == "floor" else None,
        )

    picked = _reference_on_sample(
        reg,
        reg_counts,
        group_specs,
        effective_dim=effective_dim,
    )
    if picked is None:
        if effective_dim == "floor":
            _, unavailable_label = _display_reference_for_mode(effective_floor_mode)
        else:
            unavailable_label = reference_label or "기준"
        warnings.append(f"비교할 구간이 {MIN_GROUP_FOR_DUMMY}건 미만이라 지수 산출 불가")
        return _blank(unavailable_label)

    reference_code, reference_label = picked
    if effective_dim == "floor":
        display_code, display_label = _display_reference_for_mode(effective_floor_mode)
    else:
        display_code, display_label = reference_code, reference_label
    if int(reg_counts.get(display_code, 0)) >= MIN_GROUP_FOR_DUMMY:
        base_code, base_label = display_code, display_label
    else:
        base_code, base_label = reference_code, reference_label
        if effective_dim == "floor":
            warnings.append(
                f"{display_label}이 최종 회귀 표본에 없습니다. 지수·신뢰구간·p는 {base_label}=100 대비입니다."
            )

    reg = reg.copy()
    reg["ln_unit_price"] = np.log(reg["unit_price"].astype(float))
    parts: list[pd.DataFrame] = []

    if effective_dim != "area":
        ln_area = np.log(reg["exclusive_area"].astype(float))
        if int(pd.Series(ln_area).nunique(dropna=True)) >= 2:
            reg["ln_exclusive_area"] = ln_area
            parts.append(reg[["ln_exclusive_area"]])
            controls.append("ln_gross_area" if is_commercial else "ln_exclusive_area")
        else:
            warnings.append("면적이 한 값뿐이라 ln(면적) 통제를 뺐습니다.")

    if sample_meta["use_age"] and "building_age" in reg.columns:
        parts.append(reg[["building_age"]].astype(float))
        controls.append("building_age")

    if sample_meta["use_time"]:
        _add_time_dummies(reg, parts, controls)

    if sample_meta["use_floor_control"]:
        _add_floor_control_dummies(reg, parts, controls, floor_mode=control_floor_mode)

    if sample_meta["use_use"]:
        _add_building_use_dummies(reg, parts, controls)

    if sample_meta["use_fe"] and sample_meta["reference_key"]:
        _add_building_fe(reg, parts, controls, reference_key=sample_meta["reference_key"])

    dummy_codes = [
        code
        for _, code, _ in group_specs
        if code != reference_code and int(reg_counts.get(code, 0)) >= MIN_GROUP_FOR_DUMMY
    ]
    for code in dummy_codes:
        col = f"idx_{code}"
        reg[col] = (reg["index_group_code"].astype(str) == code).astype(float)
        parts.append(reg[[col]])

    if not dummy_codes or not parts:
        warnings.append("비교할 구간이 기준 하나만 남아 지수 산출 불가")
        return _blank(base_label)

    X = pd.concat(parts, axis=1).astype(float)
    y = reg["ln_unit_price"]
    valid = X.notna().all(axis=1) & y.notna()
    X = X.loc[valid]
    y = y.loc[valid]
    fitted_counts, _ = _group_count_maps(reg.loc[valid])
    identified_codes = [reference_code, *dummy_codes]
    if any(int(fitted_counts.get(code, 0)) < MIN_GROUP_FOR_DUMMY for code in identified_codes):
        warnings.append("결측을 뺀 뒤 구간 표본이 부족해 지수 산출 불가")
        reg_counts = fitted_counts
        return _blank(base_label)

    varying = [col for col in X.columns if int(X[col].nunique(dropna=True)) >= 2]
    if any(col.startswith("idx_") and col not in varying for col in X.columns):
        warnings.append("층 구간이 다른 항과 겹쳐 지수 산출 불가")
        return _blank(base_label)
    X = X[varying]
    X = sm.add_constant(X, has_constant="add")
    if _design_rank(X) < X.shape[1] and "building_age" in X.columns:
        warnings.append("연식이 다른 항과 겹쳐 통제에서 뺐습니다.")
        controls[:] = [name for name in controls if name != "building_age"]
        X = X.drop(columns=["building_age"])
    if _design_rank(X) < X.shape[1] or len(y) - _design_rank(X) < 1:
        warnings.append("설계행렬 순위 또는 잔여 자유도가 부족해 지수 산출 불가")
        return _blank(base_label)

    if len(y) < 30:
        warnings.append(f"회귀 표본 n={len(y)} — 참고용 (권장 n≥30)")

    try:
        model = sm.OLS(y, X, missing="drop").fit(cov_type="HC3")
    except Exception as exc:
        warnings.append(f"회귀 실패: {exc}")
        return _blank(base_label)
    if not np.isfinite(np.asarray(model.params, dtype=float)).all():
        warnings.append("계수가 식별되지 않아 지수 산출 불가")
        return _blank(base_label)

    diagnostics, diag_warnings = _collinearity_diagnostics(X)
    warnings.extend(diag_warnings)

    coef_map: dict[str, dict] = {}
    for code in identified_codes:
        if code == base_code:
            continue
        try:
            contrast = _contrast_against_base(model, code, base_code, reference_code)
        except Exception:
            contrast = None
        if contrast is None:
            warnings.append("기준 대비를 계산하지 못해 지수 산출 불가")
            return _blank(base_label)
        coef_map[code] = contrast

    cells = _cells_from_regression(
        group_specs,
        reg_counts,
        raw_prices,
        base_code,
        coef_map,
        effective_dim,
        raw_counts=raw_counts,
        publish=True,
    )
    regression_reference_floor = None
    if effective_dim == "floor" and reference_code != base_code:
        regression_reference_floor = reference_label
        warnings.append(
            f"회귀에서 뺀 구간은 {reference_label}입니다. 지수·신뢰구간·p는 {base_label}=100 대비입니다."
        )

    return _result_with_cells(
        effective_dim,
        base_label,
        controls,
        n_total,
        int(model.nobs),
        round(float(model.rsquared), 4) if model.rsquared is not None else None,
        baseline,
        cells,
        list(warnings),
        regression_reference_floor=regression_reference_floor,
        floor_mode=effective_floor_mode if effective_dim == "floor" else None,
        diagnostics=diagnostics,
    )


def _empty_result(dimension: str, *, warnings: list[str]) -> dict:
    return {
        "method": "regression_semilog",
        "reference_floor": REFERENCE_FLOOR_LABEL,
        "controls": [],
        "n_total": 0,
        "n_regression": 0,
        "r_squared": None,
        "baseline_median": None,
        "dimension": dimension,
        "cells": [],
        "warnings": warnings,
    }


def _result_with_cells(
    dimension: str,
    reference_label: str,
    controls: list[str],
    n_total: int,
    n_regression: int,
    r_squared: float | None,
    baseline: float,
    cells: list[dict],
    warnings: list[str],
    *,
    regression_reference_floor: str | None = None,
    floor_mode: str | None = None,
    diagnostics: dict | None = None,
) -> dict:
    out: dict = {
        "method": "regression_semilog" if n_regression > 0 else "reference_only",
        "reference_floor": reference_label,
        "controls": controls,
        "n_total": n_total,
        "n_regression": n_regression,
        "r_squared": r_squared,
        "baseline_median": _rnd_price(baseline) if baseline > 0 else None,
        "dimension": dimension,
        "cells": cells,
        "warnings": warnings,
    }
    if regression_reference_floor:
        out["regression_reference_floor"] = regression_reference_floor
    if floor_mode:
        out["floor_mode"] = floor_mode
    if diagnostics:
        out["diagnostics"] = diagnostics
    return out


def _cells_from_regression(
    group_specs: list[tuple[str, str, float | None]],
    group_counts: dict[str, int],
    group_prices: dict[str, list[float]],
    reference_code: str,
    coef_map: dict[str, dict],
    dimension: str,
    *,
    raw_counts: dict[str, int] | None = None,
    publish: bool = True,
) -> list[dict]:
    cells = []
    for label, code, sort_key in group_specs:
        count = int(group_counts.get(code, 0))
        count_raw = int(raw_counts.get(code, count)) if raw_counts is not None else count
        prices = group_prices.get(code, [])
        mean_p = float(np.mean(prices)) if prices else None
        is_ref = publish and code == reference_code and count >= MIN_GROUP_FOR_DUMMY
        coef = coef_map.get(code)
        if is_ref:
            index_val = 100.0
            gamma = p_value = index_lo = index_hi = None
        elif publish and coef and count >= MIN_GROUP_FOR_DUMMY:
            index_val = coef["index"]
            gamma = coef["gamma"]
            p_value = coef["p_value"]
            index_lo = coef["index_lo"]
            index_hi = coef["index_hi"]
        else:
            index_val = gamma = p_value = index_lo = index_hi = None

        cell: dict = {
            "label": label,
            "count": count,
            "count_raw": count_raw,
            "mean_unit_price": _rnd_price(mean_p) if mean_p is not None else None,
            "index": index_val,
            "is_reliable": count >= MIN_RELIABLE_BUILDING_STATS,
            "is_reference": is_ref,
            "gamma": gamma,
            "p_value": p_value,
            "index_lo": index_lo,
            "index_hi": index_hi,
        }
        if dimension == "floor":
            cell["floor"] = sort_key
        elif dimension == "dong" and label != "—":
            cell["dong"] = label
        elif dimension == "area":
            cell["area"] = sort_key
        cells.append(cell)

    def _sort_key(c: dict):
        if dimension == "area" and c.get("area") is not None:
            return (0, c["area"])
        if dimension == "floor" and c.get("floor") is not None:
            return (0, c["floor"])
        if c["label"] == "—":
            return (2, 0)
        return (1, c["label"])

    cells.sort(key=_sort_key)
    return cells

