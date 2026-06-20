"""Commercial Analysis Cohort — 다중 도로 cluster 효용지수·회귀."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.analysis_explain import (
    build_commercial_floor_index_explain,
    build_commercial_regression_explain,
)
from app.collective.analysis_gates import count_recent_transactions, evaluate_analysis_gates
from app.collective.db import get_collective_db
from app.collective.filters import apply_period_filters
from app.collective.schemas import AnalysisExplain, AnalysisFeatures, FloorIndexCell, FloorIndexDiagnostics
from app.collective_commercial.floor_index_regression import (
    compute_commercial_area_index_regression,
    compute_shop_floor_index_regression,
)
from app.collective_commercial.regression.engine import predict_commercial_regression, run_commercial_regression
from app.collective_commercial.schemas import (
    CommercialCohortClusterSummary,
    CommercialCohortFloorIndexResponse,
    CommercialCohortHistogramResponse,
    CommercialCohortRegressionPredictRequest,
    CommercialCohortRegressionResponse,
    CommercialCohortRequest,
    CommercialCohortTransactionsRequest,
    CommercialCohortTransactionsResponse,
    CommercialHistogramBin,
    CommercialRegressionPredictResponse,
    CommercialTransactionRow,
)
from app.collective_commercial.transaction_export import commercial_transactions_csv_bytes
from app.collective.transaction_export import MAX_COLLECTIVE_TX_EXPORT, csv_attachment_response, export_filename

router = APIRouter(prefix="/analysis/cohort", tags=["집합상가·공장-코호트"])

_TX_SELECT = """
    SELECT cluster_key, asset_type, unit_price, floor, gross_area, land_area,
           price, building_age, building_year, contract_year, contract_month,
           zone_type, building_use, road_width_label, road_code, addr4, road_name
    FROM collective_commercial_transactions
"""


def _cohort_keys(body: CommercialCohortRequest) -> list[str]:
    keys = list(dict.fromkeys(body.cluster_keys))
    if not keys:
        raise HTTPException(400, "cluster_keys가 비어 있습니다.")
    if len(keys) > 10:
        raise HTTPException(400, "코호트는 최대 10개 도로 cluster까지 가능합니다.")
    return keys


def _fetch_cohort_transactions(
    db: Session,
    cluster_keys: list[str],
    *,
    contract_year_from: Optional[int],
    contract_year_to: Optional[int],
    contract_date_from=None,
    contract_date_to=None,
) -> tuple[pd.DataFrame, list[CommercialCohortClusterSummary]]:
    keys = list(dict.fromkeys(cluster_keys))
    clauses = ["cluster_key = ANY(:keys)"]
    params: dict = {"keys": keys}
    apply_period_filters(
        clauses,
        params,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    where = " AND ".join(clauses)
    rows = db.execute(text(f"{_TX_SELECT} WHERE {where}"), params).mappings().all()
    if not rows:
        raise HTTPException(404, "코호트 거래 없음")

    meta_rows = db.execute(
        text(
            """
            SELECT t.cluster_key,
                   COALESCE(MAX(c.display_label), MAX(t.road_name), t.cluster_key) AS display_label,
                   MAX(t.road_name) AS road_name,
                   COUNT(*)::int AS cnt
            FROM collective_commercial_transactions t
            LEFT JOIN commercial_clusters c ON c.cluster_key = t.cluster_key
            WHERE t.cluster_key = ANY(:keys)
            GROUP BY t.cluster_key
            """
        ),
        {"keys": keys},
    ).mappings().all()
    summaries = [
        CommercialCohortClusterSummary(
            cluster_key=r["cluster_key"],
            display_label=r["display_label"] or r["cluster_key"],
            road_name=r.get("road_name"),
            count=int(r["cnt"] or 0),
        )
        for r in meta_rows
    ]
    return pd.DataFrame(rows), summaries


def _cohort_display_label(summaries: list[CommercialCohortClusterSummary], keys: list[str]) -> str:
    if len(keys) == 1 and summaries:
        hit = next((s for s in summaries if s.cluster_key == keys[0]), None)
        return hit.display_label if hit else keys[0]
    labels = []
    for k in keys[:3]:
        hit = next((s for s in summaries if s.cluster_key == k), None)
        labels.append(hit.display_label if hit else k[:8])
    suffix = f" 외 {len(keys) - 3}개" if len(keys) > 3 else ""
    return " · ".join(labels) + suffix


@router.post("/floor-index", response_model=CommercialCohortFloorIndexResponse)
def cohort_floor_index(body: CommercialCohortRequest, db: Session = Depends(get_collective_db)):
    keys = _cohort_keys(body)
    df, summaries = _fetch_cohort_transactions(
        db,
        keys,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
        contract_date_from=body.contract_date_from,
        contract_date_to=body.contract_date_to,
    )
    years = [int(y) for y in df["contract_year"].dropna().tolist()]
    cnt_recent = count_recent_transactions(
        years,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    gates = evaluate_analysis_gates(len(df), cnt_recent)
    if not gates.floor_index_eligible and not body.experiment:
        raise HTTPException(
            403,
            detail=gates.messages[0] if gates.messages else "코호트 효용지수 최소 표본 미달",
        )

    asset_type = body.asset_type or str(df["asset_type"].mode().iloc[0]) if not df.empty else "collective_shop"
    cohort_mode = len(keys) > 1

    if body.dimension == "floor" and asset_type in ("collective_shop", "collective_factory"):
        raw = compute_shop_floor_index_regression(df, cohort_mode=cohort_mode)
    elif body.dimension == "area":
        raw = compute_commercial_area_index_regression(df, asset_type=asset_type, cohort_mode=cohort_mode)
    else:
        raise HTTPException(400, f"지원하지 않는 dimension: {body.dimension}")

    method = raw.get("method", "regression_semilog")
    explain = AnalysisExplain(
        **build_commercial_floor_index_explain(
            method=method,
            dimension=raw["dimension"],
            asset_type=asset_type,
            raw=raw,
        )
    )
    diag_raw = raw.get("diagnostics")
    diagnostics = FloorIndexDiagnostics(**diag_raw) if diag_raw else None

    return CommercialCohortFloorIndexResponse(
        cluster_keys=keys,
        cohort_clusters=summaries,
        asset_type=asset_type,
        dimension=raw["dimension"],
        method=method,
        reference_floor=raw.get("reference_floor"),
        controls=raw.get("controls") or [],
        n_total=raw["n_total"],
        n_regression=raw.get("n_regression"),
        r_squared=raw.get("r_squared"),
        baseline_median=raw.get("baseline_median"),
        cells=[FloorIndexCell(**c) for c in raw["cells"]],
        warnings=raw.get("warnings") or [],
        explain=explain,
        analysis=AnalysisFeatures(
            floor_index=gates.floor_index_eligible,
            regression=gates.regression_eligible,
            count_total=gates.count_total,
            count_recent=gates.count_recent,
            messages=gates.messages,
        ),
        diagnostics=diagnostics,
    )


@router.post("/regression/run", response_model=CommercialCohortRegressionResponse)
def cohort_regression_run(body: CommercialCohortRequest, db: Session = Depends(get_collective_db)):
    keys = _cohort_keys(body)
    df, summaries = _fetch_cohort_transactions(
        db,
        keys,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
        contract_date_from=body.contract_date_from,
        contract_date_to=body.contract_date_to,
    )
    years = [int(y) for y in df["contract_year"].dropna().tolist()]
    cnt_recent = count_recent_transactions(
        years,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    gates = evaluate_analysis_gates(len(df), cnt_recent)
    if not gates.regression_eligible and not body.experiment:
        raise HTTPException(
            403,
            detail=gates.messages[0] if gates.messages else "코호트 회귀 최소 표본 미달",
        )

    asset_type = body.asset_type or str(df["asset_type"].mode().iloc[0]) if not df.empty else "collective_shop"
    is_shop = asset_type == "collective_shop"
    display_label = _cohort_display_label(summaries, keys)
    cluster_names = {s.cluster_key: s.display_label for s in summaries}

    result = run_commercial_regression(
        df,
        keys[0],
        display_label,
        body,
        is_shop=is_shop,
        cohort_mode=len(keys) > 1,
        cluster_display_names=cluster_names,
    )
    explain = AnalysisExplain(
        **build_commercial_regression_explain(result, body, asset_type=asset_type, is_shop=is_shop)
    )
    return CommercialCohortRegressionResponse(
        **result.model_dump(),
        cluster_keys=keys,
        cohort_clusters=summaries,
        explain=explain,
    )


@router.post("/regression/predict", response_model=CommercialRegressionPredictResponse)
def cohort_regression_predict(body: CommercialCohortRegressionPredictRequest, db: Session = Depends(get_collective_db)):
    keys = _cohort_keys(body)
    df, summaries = _fetch_cohort_transactions(
        db,
        keys,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
        contract_date_from=body.contract_date_from,
        contract_date_to=body.contract_date_to,
    )
    years = [int(y) for y in df["contract_year"].dropna().tolist()]
    cnt_recent = count_recent_transactions(
        years,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    gates = evaluate_analysis_gates(len(df), cnt_recent)
    if not gates.regression_eligible and not body.experiment:
        raise HTTPException(
            403,
            detail=gates.messages[0] if gates.messages else "코호트 회귀 예측 최소 표본 미달",
        )

    asset_type = body.asset_type or str(df["asset_type"].mode().iloc[0]) if not df.empty else "collective_shop"
    is_shop = asset_type == "collective_shop"
    cluster_names = {s.cluster_key: s.display_label for s in summaries}
    try:
        raw = predict_commercial_regression(
            df,
            body,
            body.inputs,
            is_shop=is_shop,
            cohort_mode=len(keys) > 1,
            cluster_display_names=cluster_names,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return CommercialRegressionPredictResponse(**raw)


@router.post("/histogram", response_model=CommercialCohortHistogramResponse)
def cohort_histogram(
    body: CommercialCohortRequest,
    db: Session = Depends(get_collective_db),
    bins: int = Query(12, ge=4, le=40),
    contract_year: Optional[int] = Query(None),
):
    keys = _cohort_keys(body)
    clauses = ["cluster_key = ANY(:keys)", "unit_price IS NOT NULL"]
    params: dict = {"keys": keys}
    apply_period_filters(
        clauses,
        params,
        contract_date_from=body.contract_date_from,
        contract_date_to=body.contract_date_to,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    if contract_year is not None:
        clauses.append("contract_year = :cy")
        params["cy"] = contract_year
    where = " AND ".join(clauses)
    rows = db.execute(
        text(f"SELECT unit_price FROM collective_commercial_transactions WHERE {where}"),
        params,
    ).fetchall()
    prices = [float(r[0]) for r in rows if r[0] is not None]
    if not prices:
        return CommercialCohortHistogramResponse(cluster_keys=keys, bins=[], n=0, contract_year=contract_year)
    lo, hi = min(prices), max(prices)
    if lo == hi:
        return CommercialCohortHistogramResponse(
            cluster_keys=keys,
            bins=[CommercialHistogramBin(lo=lo, hi=hi, count=len(prices))],
            n=len(prices),
            contract_year=contract_year,
        )
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(prices, bins=edges)
    out = [
        CommercialHistogramBin(
            lo=round(float(edges[i]), 1),
            hi=round(float(edges[i + 1]), 1),
            count=int(counts[i]),
        )
        for i in range(len(counts))
        if counts[i] > 0
    ]
    return CommercialCohortHistogramResponse(
        cluster_keys=keys,
        bins=out,
        n=len(prices),
        contract_year=contract_year,
    )


@router.post("/transactions", response_model=CommercialCohortTransactionsResponse)
def cohort_transactions(body: CommercialCohortTransactionsRequest, db: Session = Depends(get_collective_db)):
    keys = _cohort_keys(body)
    clauses = ["cluster_key = ANY(:keys)"]
    params: dict = {"keys": keys}
    apply_period_filters(
        clauses,
        params,
        contract_date_from=body.contract_date_from,
        contract_date_to=body.contract_date_to,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    if body.contract_year is not None:
        clauses.append("contract_year = :cy")
        params["cy"] = body.contract_year
    where = " AND ".join(clauses)
    total = int(db.execute(text(f"SELECT COUNT(*) FROM collective_commercial_transactions WHERE {where}"), params).scalar() or 0)
    params.update({"limit": body.page_size, "offset": (body.page - 1) * body.page_size})
    rows = db.execute(
        text(
            f"""
            SELECT id, asset_type, cluster_key, addr3, addr4, lot_number,
                   contract_year, contract_month, contract_date,
                   price, gross_area, land_area, unit_price, floor, building_year, building_age,
                   zone_type, building_use, area_bucket_label, road_name,
                   road_code, road_width_label, buyer_type, seller_type, deal_type
            FROM collective_commercial_transactions
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST,
                     contract_month DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [CommercialTransactionRow(**dict(r)) for r in rows]
    return CommercialCohortTransactionsResponse(cluster_keys=keys, total=total, items=items)


@router.post("/transactions/export")
def cohort_transactions_export(body: CommercialCohortRequest, db: Session = Depends(get_collective_db)):
    keys = _cohort_keys(body)
    clauses = ["cluster_key = ANY(:keys)"]
    params: dict = {"keys": keys}
    apply_period_filters(
        clauses,
        params,
        contract_date_from=body.contract_date_from,
        contract_date_to=body.contract_date_to,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    where = " AND ".join(clauses)
    total = int(db.execute(text(f"SELECT COUNT(*) FROM collective_commercial_transactions WHERE {where}"), params).scalar() or 0)
    if total > MAX_COLLECTIVE_TX_EXPORT:
        raise HTTPException(
            413,
            detail=f"내보내기 상한({MAX_COLLECTIVE_TX_EXPORT:,}건)을 초과했습니다. cluster·기간 범위를 줄여 주세요.",
        )
    rows = db.execute(
        text(
            f"""
            SELECT id, asset_type, cluster_key, addr3, addr4, lot_number,
                   contract_year, contract_month, contract_date,
                   price, gross_area, land_area, unit_price, floor, building_year, building_age,
                   zone_type, building_use, area_bucket_label, road_name,
                   road_code, road_width_label, buyer_type, seller_type, deal_type
            FROM collective_commercial_transactions
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST,
                     contract_month DESC NULLS LAST, id DESC
            """
        ),
        params,
    ).mappings().all()
    payload = commercial_transactions_csv_bytes([dict(r) for r in rows])
    filename = export_filename(display_name="", fallback_key=f"cohort_{len(keys)}", prefix="cohort_transactions")
    return csv_attachment_response(payload, filename)
