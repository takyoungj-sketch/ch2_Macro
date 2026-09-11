"""복합 모형추천 Twin 벤치 — 랩 전용. 제품 Stage2 기본 경로를 바꾸지 않는다.

실험 Twin1/Twin2 표본은 구조 1위가 게이트를 통과할 때만 Local+1위.
1위가 떨어지면 Twin 열은 비운다(2위 승격 없음).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.built.regression.engine import predict_regression
from app.built.regression.selection.blocks import spec_from_blocks
from app.built.regression.selection.pooling import (
    _attach_search_confirm_cv,
    _fit_pool_variant,
    _metrics_from_fit,
    _research_pool_variant,
    filter_twins_by_hard_gates,
)
from app.built.schemas import (
    PoolingCandidateMetrics,
    RegressionPredictRequest,
    RegressionSelectionRequest,
)
from app.recommendation.stages import _build_stage1
from app.recommendation.twin_validation import validate_recommend_twin_neighbors

COLUMN_IDS = ("local", "twin1", "twin1_dummy", "twin2", "twin2_dummy")
COLUMN_LABELS = {
    "local": "Local",
    "twin1": "Twin1",
    "twin1_dummy": "Twin1+더미",
    "twin2": "Twin2",
    "twin2_dummy": "Twin2+더미",
}
ROAD_LABEL_CANDIDATES = ("12미터미만", "12m미만", "12m 미만", "12미터 미만")


def pick_rank1_passed(ordered_codes: list[str], gates) -> tuple[str | None, str | None]:
    """구조 1위 코드가 게이트를 통과하면 그 코드, 아니면 이유."""
    if not ordered_codes:
        return None, "Twin 후보가 없습니다."
    rank1 = ordered_codes[0]
    gate = next((g for g in gates if g.region_code == rank1), None)
    if gate is None:
        return None, f"Twin 1위({rank1}) 게이트 결과가 없습니다."
    if not gate.accepted:
        reasons = ", ".join(gate.reasons) if gate.reasons else "게이트 미통과"
        return None, f"Twin 1위({rank1})가 게이트에서 제외됨 — {reasons}"
    return rank1, None


def _empty_column(col_id: str, reason: str) -> dict[str, Any]:
    return {
        "id": col_id,
        "label": COLUMN_LABELS[col_id],
        "skipped_reason": reason,
        "n": None,
        "search_cv_mape": None,
        "confirm_cv_mape": None,
        "blocks": [],
        "response_scale": None,
        "y_hat": None,
        "ci_lower": None,
        "ci_upper": None,
        "pi_lower": None,
        "pi_upper": None,
        "predict_skipped_reason": None,
        "predict_warnings": [],
    }


def _column_from_metrics(
    col_id: str,
    metrics: PoolingCandidateMetrics | None,
    skip: str | None,
) -> dict[str, Any]:
    if metrics is None:
        return _empty_column(col_id, skip or "적합 실패")
    return {
        "id": col_id,
        "label": COLUMN_LABELS[col_id],
        "skipped_reason": None,
        "n": metrics.n,
        "search_cv_mape": metrics.cv_mape,
        "confirm_cv_mape": metrics.confirm_cv_mape,
        "blocks": list(metrics.blocks or []),
        "response_scale": metrics.response_scale,
        "y_hat": None,
        "ci_lower": None,
        "ci_upper": None,
        "pi_lower": None,
        "pi_upper": None,
        "predict_skipped_reason": None,
        "predict_warnings": [],
    }


def _obs_prices(df) -> dict[str, float | int | None]:
    if df is None or "price" not in df.columns or df.empty:
        return {"n": 0, "mean": None, "p50": None}
    s = np.asarray(df["price"], dtype=float)
    s = s[np.isfinite(s) & (s > 0)]
    if s.size == 0:
        return {"n": 0, "mean": None, "p50": None}
    return {
        "n": int(s.size),
        "mean": round(float(np.mean(s)), 1),
        "p50": round(float(np.median(s)), 1),
    }


def _predict_column(
    conn,
    *,
    req: RegressionSelectionRequest,
    col: dict[str, Any],
    region_codes: list[str],
    scenario: dict[str, Any],
    region_leaf: str | None,
) -> dict[str, Any]:
    if col.get("skipped_reason") or not col.get("blocks"):
        return col
    spec = spec_from_blocks(col["blocks"])
    road = scenario.get("road_width_label")
    last_err = None
    road_try: list[str | None] = [road] if road else list(ROAD_LABEL_CANDIDATES)
    if None not in road_try:
        road_try.append(None)
    for rw in road_try:
        body = RegressionPredictRequest(
            asset_type=req.asset_type,
            region_codes=list(region_codes),
            region_code_level="eupmyeondong",
            admin_level="eupmyeondong",
            contract_year_from=req.contract_year_from,
            contract_year_to=req.contract_year_to,
            as_of_month=req.as_of_month,
            window_years=req.window_years,
            include_partial=bool(req.include_partial),
            enrich=bool(req.enrich),
            variables=spec,
            response_scale=col["response_scale"] or "linear",
            gross_area=scenario.get("gross_area"),
            land_area=scenario.get("land_area"),
            building_age=scenario.get("building_age"),
            road_width_label=rw,
            region_leaf=region_leaf,
        )
        try:
            pred = predict_regression(conn, body)
            col["y_hat"] = pred.y_hat
            col["ci_lower"] = pred.ci_lower
            col["ci_upper"] = pred.ci_upper
            col["pi_lower"] = pred.pi_lower
            col["pi_upper"] = pred.pi_upper
            col["predict_warnings"] = list(pred.warnings or [])
            col["predict_skipped_reason"] = None
            return col
        except ValueError as exc:
            last_err = str(exc)
            continue
    col["predict_skipped_reason"] = last_err or "예측 실패"
    return col


def run_recommend_twin_bench(
    conn,
    *,
    req: RegressionSelectionRequest,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    """한 동·한 유형 5열 벤치. Twin은 구조 1위만."""
    analysis_scope, stage1, _primary, _alt, _grade, bundle, _excluded = _build_stage1(conn, req)
    anchor = ""
    if analysis_scope.anchor_unit and analysis_scope.anchor_unit.code:
        anchor = str(analysis_scope.anchor_unit.code)
    if not anchor:
        codes = [c for c in (req.region_codes or []) if str(c).strip()]
        anchor = codes[0] if codes else ""

    local_fit = bundle.primary_raw.fit
    local_blocks = list(bundle.primary_raw.blocks)
    local_metrics = _metrics_from_fit(
        "local",
        "Local",
        local_fit,
        (anchor,) if anchor else tuple(),
        blocks=local_blocks,
        prefix_k=0,
    )
    local_metrics = _attach_search_confirm_cv(
        local_metrics,
        bundle.ctx.df,
        unified=bundle.ctx.unified,
        region_col=bundle.region_col,
    )
    local_col = _column_from_metrics("local", local_metrics, None)

    obs = _obs_prices(bundle.ctx.df)
    twin_skip = None
    rank1 = None
    gates = []
    ordered: list[str] = []

    validated = validate_recommend_twin_neighbors(
        conn,
        req=req,
        admin_level=bundle.ctx.admin_level,
        search_pool=list(bundle.pool),
        anchor_df=bundle.ctx.df,
    )
    for row in validated.neighbors:
        code = str(row.get("region_code") or "").strip()
        if code and code not in ordered and code != anchor:
            ordered.append(code)

    if analysis_scope.admin_level not in {"eupmyeondong", "beopjungri"}:
        twin_skip = "시군구·구 초점에는 Twin을 붙이지 않습니다."
    elif not ordered:
        twin_skip = validated.gate_summary or "Profile Twin 후보가 없습니다."
    else:
        req_for_pool = req.model_copy(update={"profile_twin_neighbors": validated.neighbors})
        gates, _passed = filter_twins_by_hard_gates(
            conn,
            req=req_for_pool,
            anchor_region_codes=(anchor,) if anchor else tuple(),
            twin_region_codes=tuple(ordered),
            admin_level=bundle.ctx.admin_level,
        )
        rank1, twin_skip = pick_rank1_passed(ordered, gates)

    dummy_blocks = list(dict.fromkeys([*local_blocks, "region_leaf"]))
    search_pool = list(bundle.pool)
    dummy_pool = list(dict.fromkeys([*search_pool, "region_leaf"]))
    twin_codes = (rank1,) if rank1 else tuple()
    region_col = bundle.region_col or "eupmyeondong_code"

    def _twin1(blocks, col_id: str):
        if twin_skip:
            return _empty_column(col_id, twin_skip)
        return _column_from_metrics(
            col_id,
            _fit_pool_variant(
                conn,
                local_ctx=bundle.ctx,
                req=req,
                blocks=blocks,
                variant_id=col_id,
                label=COLUMN_LABELS[col_id],
                anchor_region_codes=(anchor,),
                twin_codes=twin_codes,
                admin_level=bundle.ctx.admin_level,
                region_col=region_col if "region_leaf" in blocks else bundle.region_col,
                response_scale=local_fit.response_scale,
                prefix_k=1,
            ),
            None,
        )

    def _twin2(pool, col_id: str):
        if twin_skip:
            return _empty_column(col_id, twin_skip)
        return _column_from_metrics(
            col_id,
            _research_pool_variant(
                conn,
                local_ctx=bundle.ctx,
                req=req,
                search_pool=pool,
                variant_id=col_id,
                label=COLUMN_LABELS[col_id],
                anchor_region_codes=(anchor,),
                twin_codes=twin_codes,
                admin_level=bundle.ctx.admin_level,
                region_col=region_col if "region_leaf" in pool else bundle.region_col,
                prefix_k=1,
            ),
            None,
        )

    cols = [
        local_col,
        _twin1(local_blocks, "twin1"),
        _twin1(dummy_blocks, "twin1_dummy"),
        _twin2(search_pool, "twin2"),
        _twin2(dummy_pool, "twin2_dummy"),
    ]

    local_codes = [anchor] if anchor else list(req.region_codes or [])
    twin_region_codes = [anchor, rank1] if rank1 else local_codes
    for col in cols:
        codes = local_codes if col["id"] == "local" else twin_region_codes
        leaf = anchor if col["id"].endswith("_dummy") else None
        _predict_column(conn, req=req, col=col, region_codes=codes, scenario=scenario, region_leaf=leaf)

    return {
        "asset_type": req.asset_type,
        "admin_level": analysis_scope.admin_level,
        "region_code": anchor,
        "window_years": req.window_years,
        "rank1_region_code": rank1,
        "rank1_skipped_reason": twin_skip,
        "local_obs": obs,
        "scenario": scenario,
        "stage1_blocks": local_blocks,
        "stage1_scale": local_fit.response_scale,
        "columns": cols,
        "twin_gates": [
            {
                "region_code": g.region_code,
                "rank": g.rank,
                "accepted": g.accepted,
                "reasons": list(g.reasons or []),
            }
            for g in gates
        ],
    }
