"""Analysis Cohort — 다중 cluster_key 효용지수·회귀 (집합상가·공장)."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.analysis_explain import (
    build_commercial_regression_explain,
    build_residential_floor_index_explain,
)
from app.collective.analysis_gates import count_recent_transactions, evaluate_analysis_gates
from app.collective.db import get_collective_db
from app.collective.filters import apply_period_filters
from app.collective.floor_index_regression import compute_residential_floor_index_regression
from app.collective.schemas import AnalysisExplain, AnalysisFeatures, FloorIndexCell
from app.collective_commercial.regression.engine import (
    predict_commercial_regression,
    run_cohort_commercial_regression,
)
from app.collective_commercial.tx_rows import commercial_tx_row_dict
from app.collective_commercial.schemas import (
    CommercialCohortAnalysisRequest,
    CommercialCohortClusterSummary,
    CommercialCohortFloorIndexResponse,
    CommercialCohortHistogramResponse,
    CommercialCohortRegressionPredictRequest,
    CommercialCohortRegressionResponse,
    CommercialCohortTransactionsRequest,
    CommercialCohortTransactionsResponse,
    CommercialCohortYearlySeries,
    CommercialCohortYearlyStatsResponse,
    CommercialHistogramBin,
    CommercialRegressionPredictResponse,
    CommercialRegressionRequest,
    CommercialTransactionRow,
    CommercialYearlyStatPoint,
)

router = APIRouter(prefix="/analysis/cohort", tags=["집합상가·공장-코호트"])


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
    clauses = ["cluster_key = ANY(:keys)", "is_valid = true"]
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
    rows = db.execute(
        text(
            f"""
            SELECT cluster_key, asset_type,
                   unit_price, floor, gross_area, land_area,
                   price, building_age, building_year, contract_year, contract_month,
                   zone_type, building_use, road_width_label, road_code, addr4
            FROM collective_commercial_transactions
            WHERE {where}
            """
        ),
        params,
    ).mappings().all()
    if not rows:
        raise HTTPException(404, "코호트 거래 없음")

    meta_rows = db.execute(
        text(
            """
            SELECT t.cluster_key,
                   COALESCE(MAX(c.display_label), MAX(t.road_name), t.cluster_key) AS display_label,
                   COUNT(*)::int AS cnt
            FROM collective_commercial_transactions t
            LEFT JOIN commercial_clusters c ON c.id = t.cluster_id
            WHERE t.cluster_key = ANY(:keys) AND t.is_valid = true
            GROUP BY t.cluster_key
            """
        ),
        {"keys": keys},
    ).mappings().all()
    summaries = [
        CommercialCohortClusterSummary(
            cluster_key=r["cluster_key"],
            display_label=r["display_label"] or "",
            count=int(r["cnt"] or 0),
        )
        for r in meta_rows
    ]
    return pd.DataFrame(rows), summaries


def _cohort_keys(body: CommercialCohortAnalysisRequest) -> list[str]:
    keys = list(dict.fromkeys(body.cluster_keys))
    if not keys:
        raise HTTPException(400, "cluster_keys가 비어 있습니다.")
    if len(keys) > 10:
        raise HTTPException(400, "코호트는 최대 10개 cluster까지 가능합니다.")
    return keys


@router.post("/stats/by-year", response_model=CommercialCohortYearlyStatsResponse)
def cohort_stats_by_year(body: CommercialCohortAnalysisRequest, db: Session = Depends(get_collective_db)):
    keys = _cohort_keys(body)
    series: list[CommercialCohortYearlySeries] = []
    for ck in keys:
        clauses = ["cluster_key = :ck", "is_valid = true", "contract_year IS NOT NULL"]
        params: dict = {"ck": ck}
        apply_period_filters(
            clauses,
            params,
            contract_date_from=body.contract_date_from,
            contract_date_to=body.contract_date_to,
            contract_year_from=body.contract_year_from,
            contract_year_to=body.contract_year_to,
        )
        where = " AND ".join(clauses)
        meta = db.execute(
            text(
                """
                SELECT COALESCE(MAX(c.display_label), MAX(t.road_name), :ck) AS label
                FROM collective_commercial_transactions t
                LEFT JOIN commercial_clusters c ON c.id = t.cluster_id
                WHERE t.cluster_key = :ck
                """
            ),
            {"ck": ck},
        ).mappings().first()
        rows = db.execute(
            text(
                f"""
                SELECT contract_year AS year, COUNT(*)::int AS count,
                       AVG(unit_price)::float AS mean,
                       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price)::float AS median
                FROM collective_commercial_transactions
                WHERE {where}
                GROUP BY contract_year
                ORDER BY contract_year
                """
            ),
            params,
        ).mappings().all()
        points = [
            CommercialYearlyStatPoint(
                year=int(r["year"]),
                count=int(r["count"]),
                mean=round(float(r["mean"]), 1) if r["mean"] is not None else None,
                median=round(float(r["median"]), 1) if r.get("median") is not None else None,
            )
            for r in rows
        ]
        series.append(
            CommercialCohortYearlySeries(
                cluster_key=ck,
                display_label=(meta["label"] if meta else None) or ck,
                points=points,
                data_source="live",
            )
        )
    if not any(s.points for s in series):
        raise HTTPException(404, "코호트 연도별 거래 없음")
    return CommercialCohortYearlyStatsResponse(cluster_keys=keys, series=series)


@router.post("/histogram", response_model=CommercialCohortHistogramResponse)
def cohort_histogram(
    body: CommercialCohortAnalysisRequest,
    db: Session = Depends(get_collective_db),
    bins: int = Query(12, ge=4, le=40),
    contract_year: Optional[int] = Query(None),
):
    keys = _cohort_keys(body)
    clauses = ["cluster_key = ANY(:keys)", "is_valid = true", "unit_price IS NOT NULL"]
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
        CommercialHistogramBin(lo=round(float(edges[i]), 1), hi=round(float(edges[i + 1]), 1), count=int(counts[i]))
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
    clauses = ["cluster_key = ANY(:keys)", "is_valid = true"]
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
    total = db.execute(
        text(f"SELECT COUNT(*) FROM collective_commercial_transactions WHERE {where}"),
        params,
    ).scalar()
    params.update({"limit": body.page_size, "offset": (body.page - 1) * body.page_size})
    rows = db.execute(
        text(
            f"""
            SELECT id, asset_type, cluster_key, addr3, addr4, lot_number,
                   contract_year, contract_month, contract_date, price, gross_area, land_area, unit_price,
                   floor, building_year, building_age, zone_type, building_use,
                   area_bucket_label, road_name, road_code, road_width_label
            FROM collective_commercial_transactions
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [CommercialTransactionRow(**commercial_tx_row_dict(r)) for r in rows]
    return CommercialCohortTransactionsResponse(cluster_keys=keys, total=int(total or 0), items=items)


@router.post("/floor-index", response_model=CommercialCohortFloorIndexResponse)
def cohort_floor_index(body: CommercialCohortAnalysisRequest, db: Session = Depends(get_collective_db)):
    df, summaries = _fetch_cohort_transactions(
        db,
        body.cluster_keys,
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

    work = df.copy()
    work["exclusive_area"] = work["gross_area"]
    asset = body.asset_type or str(work["asset_type"].mode().iloc[0]) if not work.empty else "collective_shop"
    raw = compute_residential_floor_index_regression(
        work,
        asset_type=str(asset),
        dimension=body.dimension,
        floor_mode=body.variables.floor_mode if body.dimension == "floor" else "relative",
    )
    explain = AnalysisExplain(**build_residential_floor_index_explain(raw=raw, asset_type=str(asset)))
    return CommercialCohortFloorIndexResponse(
        cluster_keys=body.cluster_keys,
        cohort_clusters=summaries,
        asset_type=str(asset),
        dimension=raw["dimension"],
        method=raw.get("method"),
        reference_floor=raw.get("reference_floor"),
        controls=raw.get("controls") or [],
        n_total=raw["n_total"],
        n_regression=raw.get("n_regression"),
        r_squared=raw.get("r_squared"),
        baseline_median=raw["baseline_median"],
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
        diagnostics=raw.get("diagnostics"),
    )


@router.post("/regression/run", response_model=CommercialCohortRegressionResponse)
def cohort_regression(body: CommercialCohortAnalysisRequest, db: Session = Depends(get_collective_db)):
    df, summaries = _fetch_cohort_transactions(
        db,
        body.cluster_keys,
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
            detail="; ".join(gates.messages) if gates.messages else "코호트 회귀 최소 표본 미달",
        )

    label = summaries[0].display_label if len(summaries) == 1 else f"코호트 {len(summaries)}개 cluster"
    dominant = str(df["asset_type"].mode().iloc[0]) if not df.empty else "collective_shop"
    is_shop = dominant == "collective_shop"
    reg_req = CommercialRegressionRequest(
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
        variables=body.variables,
        model_type=body.model_type,
        exclude_outliers_iqr=body.exclude_outliers_iqr,
        outlier_iqr_multiplier=body.outlier_iqr_multiplier,
        experiment=body.experiment,
    )
    result = run_cohort_commercial_regression(
        df,
        body.cluster_keys,
        label,
        reg_req,
        is_shop=is_shop,
        cluster_display_labels={s.cluster_key: s.display_label for s in summaries},
    )
    return CommercialCohortRegressionResponse(
        **result.model_dump(exclude={"explain"}),
        cluster_keys=body.cluster_keys,
        cohort_clusters=summaries,
        explain=AnalysisExplain(
            **build_commercial_regression_explain(result, reg_req, is_shop=is_shop),
        ),
    )


@router.post("/regression/predict", response_model=CommercialRegressionPredictResponse)
def cohort_regression_predict(
    body: CommercialCohortRegressionPredictRequest,
    db: Session = Depends(get_collective_db),
):
    df, summaries = _fetch_cohort_transactions(
        db,
        body.cluster_keys,
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
            detail="; ".join(gates.messages) if gates.messages else "코호트 회귀 예측 최소 표본 미달",
        )

    dominant = str(df["asset_type"].mode().iloc[0]) if not df.empty else "collective_shop"
    is_shop = dominant == "collective_shop"
    try:
        raw = predict_commercial_regression(
            df,
            body,
            body.inputs,
            is_shop=is_shop,
            cohort_mode=len(body.cluster_keys) > 1,
            cluster_display_labels={s.cluster_key: s.display_label for s in summaries},
            predict_cluster_key=body.cluster_keys[0] if body.cluster_keys else None,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return CommercialRegressionPredictResponse(**raw)
