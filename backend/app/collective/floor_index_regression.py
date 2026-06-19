"""주거 단지 회귀 기반 효용지수 — 층·동·면적형·권리 (변수 통제 semi-log OLS)."""

from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.collective.analysis_gates import MIN_RELIABLE_BUILDING_STATS
from app.collective.floor_index import _area_bucket, _area_label, _dong_label
from app.collective.regression.engine import _REL_FLOOR_LABELS, _floor_group_label, relative_floor_group
from app.stats_utils import _rnd_price

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
    ("최상층", "floor_rel_top", 5),
]

GROUPED_FLOOR_GROUPS: list[tuple[str, str, float]] = [
    ("1–5층", "floor_grp_1-5", 1),
    ("6–15층", "floor_grp_6-15", 6),
    ("16층+", "floor_grp_16+", 16),
]

GROUPED_FLOOR_LABELS: dict[str, str] = {code: label for label, code, _ in GROUPED_FLOOR_GROUPS}

FLOOR_INDEX_MODES = frozenset({"relative", "dummy", "grouped"})


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


def _display_reference_for_mode(floor_mode: str) -> tuple[str, str]:
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


def _reg_index_for_code(
    code: str,
    regression_ref: str,
    coef_map: dict[str, dict],
) -> dict | None:
    """회귀 기준층 대비 지수(%)."""
    if code == regression_ref:
        return {"index": 100.0, "index_lo": 100.0, "index_hi": 100.0, "gamma": None, "p_value": None}
    return coef_map.get(code)


def _label_for_code(code: str, group_specs: list[tuple[str, str, float | None]] | None = None) -> str:
    if group_specs:
        for label, c, _ in group_specs:
            if c == code:
                return label
    for label, c, _ in RESIDENTIAL_FLOOR_GROUPS:
        if c == code:
            return label
    return GROUPED_FLOOR_LABELS.get(code, code)


def _apply_floor_display_reference(
    cells: list[dict],
    *,
    regression_ref: str,
    coef_map: dict[str, dict],
    group_specs: list[tuple[str, str, float | None]],
    group_counts: dict[str, int],
    display_code: str,
    display_label: str,
) -> tuple[list[dict], list[str], str]:
    """회귀 결과를 화면 기준(예: 1층=100)으로 환산. 표본 없으면 — 표시."""
    extra_warnings: list[str] = []
    code_by_label = {label: code for label, code, _ in group_specs}
    reg_label = _label_for_code(regression_ref, group_specs)
    display_count = group_counts.get(display_code, 0)

    if display_count == 0:
        extra_warnings.append(f"{display_label} 거래 없음 — 지수는 회귀 기준({reg_label})=100 대비")
        for cell in cells:
            code = code_by_label.get(cell["label"])
            if code == display_code:
                cell["index"] = None
                cell["index_lo"] = None
                cell["index_hi"] = None
                cell["gamma"] = None
                cell["p_value"] = None
                cell["is_reference"] = False
            else:
                cell["is_reference"] = code == regression_ref
        return cells, extra_warnings, reg_label

    base = _reg_index_for_code(display_code, regression_ref, coef_map)
    if base is None or not base.get("index"):
        extra_warnings.append(
            f"{display_label} 표본 부족 — 아래 지수는 회귀 기준({reg_label})=100 대비 값입니다."
        )
        for cell in cells:
            code = code_by_label.get(cell["label"])
            if code == display_code:
                cell["index"] = None
                cell["is_reference"] = False
            else:
                cell["is_reference"] = code == regression_ref
        return cells, extra_warnings, reg_label

    scale = 100.0 / float(base["index"])
    for cell in cells:
        code = code_by_label.get(cell["label"])
        if code == display_code:
            cell["index"] = 100.0
            cell["index_lo"] = None
            cell["index_hi"] = None
            cell["gamma"] = None
            cell["p_value"] = None
            cell["is_reference"] = True
        elif cell["index"] is not None:
            cell["index"] = round(float(cell["index"]) * scale, 1)
            if cell.get("index_lo") is not None:
                cell["index_lo"] = round(float(cell["index_lo"]) * scale, 1)
            if cell.get("index_hi") is not None:
                cell["index_hi"] = round(float(cell["index_hi"]) * scale, 1)
            cell["is_reference"] = False
        else:
            cell["is_reference"] = False

    if regression_ref != display_code:
        extra_warnings.append(f"회귀 기준: {reg_label}(표본 최다) → 화면 지수는 {display_label}=100")

    return cells, extra_warnings, display_label


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


def _add_floor_control_dummies(reg: pd.DataFrame, parts: list[pd.DataFrame], controls: list[str]) -> None:
    """층 구간을 통제변수로 (1층 기준)."""
    if "floor_index_code" not in reg.columns:
        return
    ref = REFERENCE_FLOOR_CODE
    added = False
    for _, code, _ in RESIDENTIAL_FLOOR_GROUPS:
        if code == ref:
            continue
        col = f"ctrl_{code}"
        reg[col] = (reg["floor_index_code"] == code).astype(float)
        if reg[col].sum() >= MIN_GROUP_FOR_DUMMY:
            parts.append(reg[[col]])
            added = True
    if added:
        controls.append("relative_floor")


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
    effective_dim = dimension
    effective_floor_mode = floor_mode if floor_mode in FLOOR_INDEX_MODES else "relative"
    if dimension == "floor" and floor_mode == "linear":
        warnings.append("층 선형은 효용지수 탭에서 지원하지 않습니다. 상대·개별·구간 중 선택하세요.")
        effective_floor_mode = "relative"

    work = df.dropna(subset=["unit_price"]).copy()
    work = work[work["unit_price"].astype(float) > 0]
    n_total = len(work)
    if n_total == 0:
        return _empty_result(dimension, warnings=["유효 거래가 없습니다."])

    _ensure_building_age(work)
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
        for _, row in work.iterrows():
            ea = row.get("exclusive_area")
            if ea is None or (isinstance(ea, float) and pd.isna(ea)) or float(ea) <= 0:
                code, lbl, sort_v = "area_missing", "—", None
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

    group_counts: dict[str, int] = defaultdict(int)
    group_prices: dict[str, list[float]] = defaultdict(list)
    for _, row in work.iterrows():
        code = row["index_group_code"]
        group_counts[code] += 1
        group_prices[code].append(float(row["unit_price"]))

    if effective_dim == "floor":
        picked = _pick_regression_reference(group_counts, group_specs)
        if picked is None:
            best_label, best_code = max(
                group_specs,
                key=lambda x: group_counts.get(x[1], 0),
            )[:2]
            best_count = group_counts.get(best_code, 0)
            warnings.append(
                f"회귀 기준({best_label}) 거래 {best_count}건 — "
                f"최소 {MIN_GROUP_FOR_DUMMY}건 필요, 회귀 지수 미산출"
            )
            display_code, display_label = _display_reference_for_mode(effective_floor_mode)
            return _result_with_cells(
                effective_dim,
                display_label,
                controls,
                n_total,
                0,
                None,
                baseline,
                _cells_fallback(
                    group_specs,
                    group_counts,
                    group_prices,
                    display_code,
                    baseline,
                    effective_dim,
                ),
                warnings,
                floor_mode=effective_floor_mode,
            )
        reference_code, reference_label = picked

    ref_count = group_counts.get(reference_code, 0)
    if ref_count < MIN_GROUP_FOR_DUMMY:
        warnings.append(
            f"기준({reference_label}) 거래 {ref_count}건 — "
            f"최소 {MIN_GROUP_FOR_DUMMY}건 필요, 회귀 지수 미산출"
        )
        display_ref, display_label = (
            _display_reference_for_mode(effective_floor_mode)
            if effective_dim == "floor"
            else (reference_code, reference_label)
        )
        return _result_with_cells(
            effective_dim,
            display_label,
            controls,
            n_total,
            0,
            None,
            baseline,
            _cells_fallback(group_specs, group_counts, group_prices, display_ref, baseline, effective_dim),
            warnings,
            floor_mode=effective_floor_mode if effective_dim == "floor" else None,
        )

    reg = work.copy()
    reg = reg[reg["exclusive_area"].astype(float) > 0]
    if reg.empty:
        warnings.append("전용면적 유효 거래 없음")
        fb_ref, fb_label = (
            _display_reference_for_mode(effective_floor_mode)
            if effective_dim == "floor"
            else (reference_code, reference_label)
        )
        return _result_with_cells(
            effective_dim,
            fb_label,
            controls,
            n_total,
            0,
            None,
            baseline,
            _cells_fallback(group_specs, group_counts, group_prices, fb_ref, baseline, effective_dim),
            warnings,
            floor_mode=effective_floor_mode if effective_dim == "floor" else None,
        )

    reg["ln_unit_price"] = np.log(reg["unit_price"].astype(float))
    parts: list[pd.DataFrame] = []

    # 면적 차원에서는 연속 ln(면적)과 면적 버킷 더미가 면적 효과를 이중으로 잡으므로
    # ln(면적) 통제를 빼고 버킷 더미만 둔다. 그 외 차원은 규모 프리미엄을 통제한다.
    if effective_dim != "area":
        reg["ln_exclusive_area"] = np.log(reg["exclusive_area"].astype(float))
        parts.append(reg[["ln_exclusive_area"]])
        controls.append("ln_exclusive_area")

    if reg["building_age"].notna().any():
        parts.append(reg[["building_age"]].astype(float))
        controls.append("building_age")

    _add_time_dummies(reg, parts, controls)

    if effective_dim != "floor":
        _add_floor_control_dummies(reg, parts, controls)

    ref_bk = ""
    if "building_key" in reg.columns and reg["building_key"].nunique() > 1:
        ref_bk = str(reg["building_key"].value_counts().idxmax())
        _add_building_fe(reg, parts, controls, reference_key=ref_bk)

    dummy_codes = [
        code
        for _, code, _ in group_specs
        if code != reference_code and group_counts.get(code, 0) >= MIN_GROUP_FOR_DUMMY
    ]
    for label, code, _ in group_specs:
        if code != reference_code and 0 < group_counts.get(code, 0) < MIN_GROUP_FOR_DUMMY:
            warnings.append(f"{label} n={group_counts[code]} — 구간 표본 부족, 지수 미산출")

    for code in dummy_codes:
        col = f"idx_{code}"
        reg[col] = (reg["index_group_code"] == code).astype(float)
        parts.append(reg[[col]])

    if not dummy_codes:
        warnings.append("회귀에 포함할 구간(기준 제외)이 없습니다.")
        fb_ref, fb_label = (
            _display_reference_for_mode(effective_floor_mode)
            if effective_dim == "floor"
            else (reference_code, reference_label)
        )
        return _result_with_cells(
            effective_dim,
            fb_label,
            controls,
            n_total,
            0,
            None,
            baseline,
            _cells_fallback(group_specs, group_counts, group_prices, fb_ref, baseline, effective_dim),
            warnings,
            floor_mode=effective_floor_mode if effective_dim == "floor" else None,
        )

    X = pd.concat(parts, axis=1).astype(float)
    y = reg["ln_unit_price"]
    valid = X.notna().all(axis=1) & y.notna()
    X = X.loc[valid]
    y = y.loc[valid]

    if len(y) < 30:
        warnings.append(f"회귀 표본 n={len(y)} — 참고용 (권장 n≥30)")

    X = sm.add_constant(X, has_constant="add")
    try:
        # HC3 강건표준오차 — 부동산 단가의 이분산성 대응 (계수는 OLS와 동일, SE만 보정)
        model = sm.OLS(y, X, missing="drop").fit(cov_type="HC3")
    except Exception as exc:
        warnings.append(f"회귀 실패: {exc}")
        fb_ref, fb_label = (
            _display_reference_for_mode(effective_floor_mode)
            if effective_dim == "floor"
            else (reference_code, reference_label)
        )
        return _result_with_cells(
            effective_dim,
            fb_label,
            controls,
            n_total,
            0,
            None,
            baseline,
            _cells_fallback(group_specs, group_counts, group_prices, fb_ref, baseline, effective_dim),
            warnings,
            floor_mode=effective_floor_mode if effective_dim == "floor" else None,
        )

    diagnostics, diag_warnings = _collinearity_diagnostics(X)
    warnings.extend(diag_warnings)

    coef_map: dict[str, dict] = {}
    for code in dummy_codes:
        col = f"idx_{code}"
        if col not in model.params.index:
            continue
        gamma = float(model.params[col])
        se = float(model.bse[col]) if col in model.bse.index else None
        p = float(model.pvalues[col]) if col in model.pvalues.index else None
        idx_pct = round(float(np.exp(gamma)) * 100, 1)
        idx_lo = round(float(np.exp(gamma - 1.96 * se)) * 100, 1) if se is not None else None
        idx_hi = round(float(np.exp(gamma + 1.96 * se)) * 100, 1) if se is not None else None
        coef_map[code] = {
            "gamma": round(gamma, 4),
            "p_value": round(p, 4) if p is not None else None,
            "index": idx_pct,
            "index_lo": idx_lo,
            "index_hi": idx_hi,
        }

    cells = _cells_from_regression(
        group_specs,
        group_counts,
        group_prices,
        reference_code,
        coef_map,
        effective_dim,
    )

    result_warnings = list(warnings)
    regression_reference_floor: str | None = None
    reference_floor_label = reference_label
    if effective_dim == "floor":
        display_code, display_label = _display_reference_for_mode(effective_floor_mode)
        cells, norm_warnings, reference_floor_label = _apply_floor_display_reference(
            cells,
            regression_ref=reference_code,
            coef_map=coef_map,
            group_specs=group_specs,
            group_counts=group_counts,
            display_code=display_code,
            display_label=display_label,
        )
        result_warnings.extend(norm_warnings)
        if reference_code != display_code:
            regression_reference_floor = reference_label

    return _result_with_cells(
        effective_dim,
        reference_floor_label,
        controls,
        n_total,
        int(model.nobs),
        round(float(model.rsquared), 4) if model.rsquared is not None else None,
        baseline,
        cells,
        result_warnings,
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
        "method": "regression_semilog",
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
) -> list[dict]:
    cells = []
    for label, code, sort_key in group_specs:
        count = group_counts.get(code, 0)
        prices = group_prices.get(code, [])
        mean_p = float(np.mean(prices)) if prices else None
        is_ref = code == reference_code
        coef = coef_map.get(code)
        if is_ref:
            index_val = 100.0
            gamma = p_value = index_lo = index_hi = None
        elif coef:
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


def _cells_fallback(
    group_specs: list[tuple[str, str, float | None]],
    group_counts: dict[str, int],
    group_prices: dict[str, list[float]],
    reference_code: str,
    baseline: float,
    dimension: str,
) -> list[dict]:
    cells = []
    for label, code, sort_key in group_specs:
        count = group_counts.get(code, 0)
        prices = group_prices.get(code, [])
        mean_p = float(np.mean(prices)) if prices else None
        is_ref = code == reference_code
        cells.append(
            {
                "label": label,
                "floor": sort_key if dimension == "floor" else None,
                "dong": label if dimension == "dong" and label != "—" else None,
                "area": sort_key if dimension == "area" else None,
                "count": count,
                "mean_unit_price": _rnd_price(mean_p) if mean_p is not None else None,
                "index": 100.0 if (is_ref and count > 0) else None,
                "is_reliable": count >= MIN_RELIABLE_BUILDING_STATS,
                "is_reference": is_ref and count > 0,
                "gamma": None,
                "p_value": None,
                "index_lo": None,
                "index_hi": None,
            }
        )
    return cells
