"""회귀 엔진의 표시 메타데이터. 모형·검증 산식은 각 엔진이 소유한다."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field


class RegressionValidationContext(BaseModel):
    status: Literal["available", "partial", "unavailable", "not_run"] = "unavailable"
    method: str = "random_kfold"
    observation_unit: Literal["transaction", "complex"] = "transaction"
    requested_folds: int = 5
    attempted_folds: int = 0
    completed_folds: int = 0
    eligible_n: int = 0
    evaluated_n: int = 0
    excluded_n: int = 0
    reason_code: str | None = None
    reason: str | None = None
    failures: list[dict[str, Any]] = Field(default_factory=list)


class RegressionMetricContext(BaseModel):
    key: str
    role: Literal["training", "selection_validation", "independent_confirmation"]
    scale: str
    value: float | None = None
    n: int | None = None
    method: str | None = None
    status: Literal["available", "unavailable"] = "available"
    reason: str | None = None
    evaluation_signature: str | None = None
    validation: RegressionValidationContext | None = None


class RegressionVariableState(BaseModel):
    name: str
    state: Literal["included", "not_in_model", "constant", "no_data", "missing_after_filter", "not_identifiable"]
    columns: list[str] = Field(default_factory=list)


class RegressionComparisonContext(BaseModel):
    basis: Literal["common_complete_case"] = "common_complete_case"
    observation_unit: Literal["transaction", "complex"] = "transaction"
    sample_n: int
    fit_n: int
    evaluation_n: int | None = None
    method: str
    role: Literal["training", "selection_validation"]
    sample_signature: str | None = None
    evaluation_signature: str | None = None


def comparison_context(rows, *, observation_unit="transaction", fit_n, evaluation_n,
        method, role, split=None):
    identity = observation_signature(rows, observation_unit=observation_unit)
    sample_sig = signature(dict(identity=identity,
        data=sorted(signature(row) for row in rows.to_dict("records")))) if identity else None
    return RegressionComparisonContext(observation_unit=observation_unit, sample_n=len(rows), fit_n=fit_n, evaluation_n=evaluation_n,
        method=method, role=role, sample_signature=sample_sig,
        evaluation_signature=signature(dict(sample=sample_sig, split=split, method=method))
            if sample_sig and role == "selection_validation" else None)


class RegressionAnalysisContext(BaseModel):
    version: str = "1"
    observation_unit: Literal["transaction", "complex"]
    target: str
    target_unit: str
    response_scale: str
    fit_n: int
    coefficient_n: int
    design_rank: int | None = None
    source_n: int | None = None
    model_signature: str
    data_signature: str
    fit_sample_signature: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    feature_names: list[str] = Field(default_factory=list)
    variables: list[RegressionVariableState] = Field(default_factory=list)
    metrics: list[RegressionMetricContext] = Field(default_factory=list)
    reference_categories: dict[str, str] = Field(default_factory=dict)
    sample_steps: list[dict[str, Any]] = Field(default_factory=list)
    fit_years: list[int] = Field(default_factory=list)
    assessed_years: list[int] = Field(default_factory=list)
    provision: dict[str, Any] | None = None
    sample_groups: list[dict[str, Any]] = Field(default_factory=list)


def grouped_sample_details(source, fitted, *, key, labels=None, reference=None, effects=(), attributes=()):
    """이미 조회한 행만 사용한다. 확인값은 적합 거래에서 유일한 값일 때만 제공한다."""
    if key not in source.columns or key not in fitted.columns:
        return []
    import pandas as pd
    labels = labels or {}
    result = []
    source_keys = source[key].fillna("미확인").astype(str)
    fit_keys = fitted[key].fillna("미확인").astype(str)
    for value in sorted(source_keys.unique()):
        raw = source.loc[source_keys == value]
        used = fitted.loc[fit_keys == value]
        confirmed = {}
        for col in attributes:
            if col not in used.columns or used.empty:
                continue
            vals = pd.to_numeric(used[col], errors="coerce")
            # 일부 행만 값이 있거나 연도별 값이 다르면 대표값을 만들지 않는다.
            if vals.notna().all() and np.isfinite(vals).all() and vals.nunique() == 1:
                confirmed[col] = float(vals.iloc[0])
        address = []
        if not raw.empty:
            for col in ("addr1", "addr2", "addr3", "addr4"):
                if col in raw.columns:
                    vals = raw[col].dropna().astype(str).str.strip()
                    vals = vals.loc[vals != ""].unique()
                    if len(vals) == 1:
                        address.append(vals[0])
        result.append(dict(key=value, label=str(labels.get(value, value)), address=" ".join(address),
            source_n=len(raw), fit_n=len(used),
            fe_state="no_fit" if used.empty else "reference" if value == reference
                else "estimated" if value in effects else "not_in_model",
            confirmed_attributes=confirmed))
    return result


def _plain(value):
    if hasattr(value, "model_dump"):
        return _plain(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        result = [_plain(v) for v in value]
        return sorted(result, key=str) if isinstance(value, set) else result
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return _plain(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def signature(value) -> str:
    return hashlib.sha256(json.dumps(_plain(value), sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()


def fitted_model_signature(*, data_signature, coefficients, response_scale, target, target_unit):
    params = []
    for c in coefficients:
        value = _plain(c)
        estimate = value.get("estimate", value.get("coef"))
        # DB 반환 순서 차이로 생기는 기계 정밀도 수준의 OLS 차이는 무시한다.
        params.append((value["name"], float(f"{estimate:.12g}") if estimate is not None else None))
    return signature(dict(data=data_signature, params=sorted(params), response_scale=response_scale,
        target=target, target_unit=target_unit))


def require_model_signature(expected, actual):
    if expected is not None and expected != actual:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="분석 자료 또는 실제 모형이 변경되었습니다. 회귀를 다시 실행한 뒤 추정값을 계산하세요.")


def observation_signature(frame, *, observation_unit="transaction") -> str | None:
    """식별자 없는 행 번호는 관측 ID로 취급하지 않는다."""
    if "transaction_id" in frame.columns:
        if frame["transaction_id"].isna().any():
            return None
        keys = frame["transaction_id"].astype(str).tolist()
    elif "id" in frame.columns:
        if frame["id"].isna().any():
            return None
        keys = frame["id"].astype(str).tolist()
    elif observation_unit == "complex" and {"building_key", "asset_type"}.issubset(frame.columns):
        if frame[["building_key", "asset_type"]].isna().any().any():
            return None
        keys = (frame.asset_type.astype(str) + ":" + frame.building_key.astype(str)).tolist()
    else:
        return None
    return signature(sorted(keys))


_ALIASES = {
    "area_sqm": ("area_sqm", "log_area"), "log_area": ("log_area",),
    "assessed_land_price": ("assessed_land_price", "log_assessed_land_price"),
    "parking": ("parking_per_household",), "structure": ("struct_",),
    "builder": ("builder_",), "asset_type_dummy": ("atype_",),
    "floor": ("floor", "floor_", "shop_", "fac_"),
    "dong": ("dong_",), "housing_subtype": ("rights_",),
    "zone_type": ("zone_",), "building_use": ("use_",),
    "road_width": ("roadw_",), "road_condition": ("road_",),
    "deal_type": ("deal_",), "partial_ownership": ("partial_own",),
    "contract_period": ("time_",), "beopjungri_fe": ("beop_",),
    "region_dummy": ("region_",), "region_leaf_dummy": ("loc_",),
    "road_width_dummy": ("road_",), "zone_type_dummy": ("zone_",),
    "building_use_dummy": ("use_",), "structure_dummy": ("struct_",),
}


def build_analysis_context(*, request, rows, coefficients, observation_unit,
        target, target_unit, response_scale, fit_n, exog=None, metrics=(), source_n=None,
        variable_states=None, reference_categories=None, sample_steps=None, source_rows=None, sample_groups=None):
    conditions = _plain(request)
    if not isinstance(conditions, dict):
        conditions = {}
    conditions.pop("inputs", None)
    conditions.pop("expected_model_signature", None)
    features = [str(c.name if hasattr(c, "name") else c["name"]) for c in coefficients]
    variable_flags = dict(conditions.get("variables", {}))
    if conditions.get("region_dummy") is True:
        variable_flags["region_dummy"] = True
    states = []
    for key, enabled in variable_flags.items():
        if enabled is not True:
            continue
        aliases = _ALIASES.get(key, (key,))
        columns = [name for name in features if any(name.startswith(a) if a.endswith("_") else name == a for a in aliases)]
        state = "included" if columns else (variable_states or {}).get(key, "not_in_model")
        if not columns and state == "included":
            state = "not_in_model"
        states.append(RegressionVariableState(name=key, state=state, columns=columns))
    row_records = rows.to_dict("records") if hasattr(rows, "to_dict") else rows
    # 순서만 다른 입력에 같은 내용 서명을 부여하고 중복 관측은 보존한다.
    data_sig = signature(sorted(signature(row) for row in row_records))
    model_sig = fitted_model_signature(data_signature=data_sig, coefficients=coefficients,
        response_scale=response_scale, target=target, target_unit=target_unit)
    verdict = None
    if exog is not None:
        from app.regression_sample_judge import judge_exog
        verdict = judge_exog(exog)
    display_rows = source_rows if source_rows is not None else rows
    def years(columns):
        values = set()
        if hasattr(display_rows, "columns"):
            for column in columns:
                if column not in display_rows.columns:
                    continue
                for value in display_rows[column].dropna():
                    try:
                        number = int(value)
                        if 1900 <= number <= 2200:
                            values.add(number)
                    except (TypeError, ValueError, OverflowError):
                        continue
        return sorted(values)
    return RegressionAnalysisContext(observation_unit=observation_unit, target=target,
        target_unit=target_unit, response_scale=response_scale, fit_n=fit_n,
        coefficient_n=len(features), design_rank=verdict.rank if verdict is not None else None,
        source_n=source_n, model_signature=model_sig, data_signature=data_sig,
        fit_sample_signature=observation_signature(rows, observation_unit=observation_unit) if hasattr(rows, "columns") else None,
        conditions=conditions, feature_names=features, variables=states,
        reference_categories={str(k): str(v) for k, v in (reference_categories or {}).items() if v is not None},
        sample_steps=sample_steps or [], sample_groups=sample_groups or [], fit_years=years(["contract_year"]),
        assessed_years=years(["official_price_year", "assessed_land_price_year"]),
        provision=dict(tier=verdict.tier, identification_limited=verdict.identification,
            residual_df=verdict.n-verdict.rank, reasons=list(verdict.reasons)) if verdict is not None else None,
        metrics=[m if isinstance(m, RegressionMetricContext) else RegressionMetricContext(**{
            **m, **({"status": "unavailable", "reason": m.get("reason") or "계산되지 않았습니다."} if m.get("value") is None else {"reason": None})
        }) for m in metrics])
