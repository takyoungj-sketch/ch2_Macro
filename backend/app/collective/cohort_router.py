"""Analysis Cohort — 다중 building_key 효용지수·회귀."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.analysis_explain import (
    build_residential_floor_index_explain,
    build_residential_regression_explain,
)
from app.collective.analysis_gates import count_recent_transactions, evaluate_analysis_gates
from app.collective.db import get_collective_db
from app.collective.filters import apply_period_filters, apply_year_filters
from app.collective.floor_index_regression import compute_residential_floor_index_regression
from app.collective.regression.engine import predict_regression, run_cohort_regression
from app.collective.transaction_export import (
    MAX_COLLECTIVE_TX_EXPORT,
    TX_SELECT,
    export_filename,
    transactions_csv_bytes,
    csv_attachment_response,
)
from app.collective.schemas import (
    AnalysisExplain,
    AnalysisFeatures,
    CohortAnalysisRequest,
    CohortBuildingSummary,
    CohortFloorIndexResponse,
    CohortHistogramResponse,
    CohortRegressionPredictRequest,
    CohortRegressionResponse,
    CohortTransactionsRequest,
    CohortTransactionsResponse,
    CohortYearlyStatsResponse,
    CollectiveRegressionPredictResponse,
    CollectiveRegressionRequest,
    CollectiveTransactionRow,
    FloorIndexCell,
    HistogramBin,
    YearlyStatPoint,
    YearlyStatsResponse,
)

router = APIRouter(prefix="/analysis/cohort", tags=["집합부동산-코호트"])


def _fetch_cohort_transactions(
    db: Session,
    building_keys: list[str],
    *,
    contract_year_from: Optional[int],
    contract_year_to: Optional[int],
    contract_date_from=None,
    contract_date_to=None,
) -> tuple[pd.DataFrame, list[CohortBuildingSummary]]:
    keys = list(dict.fromkeys(building_keys))
    clauses = ["building_key = ANY(:keys)", "is_valid = true"]
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
            SELECT building_key, display_name, asset_type,
                   unit_price, floor, dong, housing_subtype, exclusive_area,
                   price, building_age, building_year, contract_year, contract_month
            FROM collective_transactions
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
            SELECT building_key, MAX(display_name) AS display_name, COUNT(*)::int AS cnt
            FROM collective_transactions
            WHERE building_key = ANY(:keys) AND is_valid = true
            GROUP BY building_key
            """
        ),
        {"keys": keys},
    ).mappings().all()
    summaries = [
        CohortBuildingSummary(
            building_key=r["building_key"],
            display_name=r["display_name"] or "",
            count=int(r["cnt"] or 0),
        )
        for r in meta_rows
    ]
    return pd.DataFrame(rows), summaries


def _cohort_keys(body: CohortAnalysisRequest) -> list[str]:
    keys = list(dict.fromkeys(body.building_keys))
    if not keys:
        raise HTTPException(400, "building_keys가 비어 있습니다.")
    if len(keys) > 10:
        raise HTTPException(400, "코호트는 최대 10개 단지까지 가능합니다.")
    return keys


@router.post("/stats/by-year", response_model=CohortYearlyStatsResponse)
def cohort_stats_by_year(body: CohortAnalysisRequest, db: Session = Depends(get_collective_db)):
    keys = _cohort_keys(body)
    series: list[YearlyStatsResponse] = []
    for bk in keys:
        clauses = ["building_key = :bk", "is_valid = true", "contract_year IS NOT NULL"]
        params: dict = {"bk": bk}
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
            text("SELECT MAX(display_name) AS dn FROM collective_transactions WHERE building_key = :bk"),
            {"bk": bk},
        ).mappings().first()
        rows = db.execute(
            text(
                f"""
                SELECT contract_year AS year, COUNT(*)::int AS count, AVG(unit_price)::float AS mean
                FROM collective_transactions
                WHERE {where}
                GROUP BY contract_year
                ORDER BY contract_year
                """
            ),
            params,
        ).mappings().all()
        points = [
            YearlyStatPoint(
                year=int(r["year"]),
                count=int(r["count"]),
                mean=round(float(r["mean"]), 1) if r["mean"] is not None else None,
            )
            for r in rows
        ]
        series.append(
            YearlyStatsResponse(
                building_key=bk,
                display_name=(meta["dn"] if meta else None) or bk,
                points=points,
                data_source="live",
            )
        )
    if not any(s.points for s in series):
        raise HTTPException(404, "코호트 연도별 거래 없음")
    return CohortYearlyStatsResponse(building_keys=keys, series=series)


@router.post("/histogram", response_model=CohortHistogramResponse)
def cohort_histogram(
    body: CohortAnalysisRequest,
    db: Session = Depends(get_collective_db),
    bins: int = Query(12, ge=4, le=40),
    contract_year: Optional[int] = Query(None),
):
    keys = _cohort_keys(body)
    clauses = ["building_key = ANY(:keys)", "is_valid = true", "unit_price IS NOT NULL"]
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
        text(f"SELECT unit_price FROM collective_transactions WHERE {where}"),
        params,
    ).fetchall()
    prices = [float(r[0]) for r in rows if r[0] is not None]
    if not prices:
        return CohortHistogramResponse(building_keys=keys, bins=[], n=0, contract_year=contract_year)
    lo, hi = min(prices), max(prices)
    if lo == hi:
        return CohortHistogramResponse(
            building_keys=keys,
            bins=[HistogramBin(lo=lo, hi=hi, count=len(prices))],
            n=len(prices),
            contract_year=contract_year,
        )
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(prices, bins=edges)
    out = [
        HistogramBin(lo=round(float(edges[i]), 1), hi=round(float(edges[i + 1]), 1), count=int(counts[i]))
        for i in range(len(counts))
        if counts[i] > 0
    ]
    return CohortHistogramResponse(
        building_keys=keys,
        bins=out,
        n=len(prices),
        contract_year=contract_year,
    )


@router.post("/transactions", response_model=CohortTransactionsResponse)
def cohort_transactions(body: CohortTransactionsRequest, db: Session = Depends(get_collective_db)):
    keys = _cohort_keys(body)
    clauses = ["building_key = ANY(:keys)", "is_valid = true"]
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
    total = db.execute(text(f"SELECT COUNT(*) FROM collective_transactions WHERE {where}"), params).scalar()
    params.update({"limit": body.page_size, "offset": (body.page - 1) * body.page_size})
    rows = db.execute(
        text(
            f"""
            SELECT id, asset_type, building_key, display_name,
                   addr1, addr2, addr3, contract_year, contract_month, contract_date,
                   exclusive_area, land_area, price, unit_price, floor, dong, housing_subtype, building_age,
                   buyer_type, seller_type, deal_type, road_name
            FROM collective_transactions
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST, display_name, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [CollectiveTransactionRow(**_tx_row_dict(r)) for r in rows]
    return CohortTransactionsResponse(building_keys=keys, total=int(total or 0), items=items)


@router.post("/transactions/export")
def cohort_transactions_export(body: CohortAnalysisRequest, db: Session = Depends(get_collective_db)):
    """코호트 거래목록 — 목록 API와 동일 필터, 전체 CSV."""
    keys = _cohort_keys(body)
    clauses = ["building_key = ANY(:keys)", "is_valid = true"]
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
    total = int(db.execute(text(f"SELECT COUNT(*) FROM collective_transactions WHERE {where}"), params).scalar() or 0)
    if total > MAX_COLLECTIVE_TX_EXPORT:
        raise HTTPException(
            413,
            detail=(
                f"내보내기 상한({MAX_COLLECTIVE_TX_EXPORT:,}건)을 초과했습니다. "
                "단지·기간 범위를 줄여 주세요."
            ),
        )
    rows = db.execute(
        text(
            f"""
            {TX_SELECT}
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST, display_name, id DESC
            """
        ),
        params,
    ).mappings().all()
    asset = body.asset_type or (str(rows[0]["asset_type"]) if rows else "apartment")
    payload = transactions_csv_bytes([dict(r) for r in rows], asset_type=asset, include_building=True)
    filename = export_filename(display_name="", fallback_key=f"cohort_{len(keys)}", prefix="cohort_transactions")
    return csv_attachment_response(payload, filename)


@router.post("/floor-index", response_model=CohortFloorIndexResponse)
def cohort_floor_index(body: CohortAnalysisRequest, db: Session = Depends(get_collective_db)):
    df, summaries = _fetch_cohort_transactions(
        db,
        body.building_keys,
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

    raw = compute_residential_floor_index_regression(
        df,
        asset_type=body.asset_type or str(df["asset_type"].mode().iloc[0]) if not df.empty else "apartment",
        dimension=body.dimension,
        floor_mode=body.variables.floor_mode,
    )
    asset = body.asset_type or str(df["asset_type"].mode().iloc[0]) if not df.empty else "apartment"
    explain = AnalysisExplain(**build_residential_floor_index_explain(raw=raw, asset_type=str(asset)))
    return CohortFloorIndexResponse(
        building_keys=body.building_keys,
        cohort_buildings=summaries,
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


@router.post("/regression/run", response_model=CohortRegressionResponse)
def cohort_regression(body: CohortAnalysisRequest, db: Session = Depends(get_collective_db)):
    df, summaries = _fetch_cohort_transactions(
        db,
        body.building_keys,
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

    label = summaries[0].display_name if len(summaries) == 1 else f"코호트 {len(summaries)}개 단지"
    dominant = str(df["asset_type"].mode().iloc[0]) if not df.empty else "apartment"
    reg_req = CollectiveRegressionRequest(
        asset_type=body.asset_type or dominant,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
        variables=body.variables,
        exclude_outliers_iqr=body.exclude_outliers_iqr,
        outlier_iqr_multiplier=body.outlier_iqr_multiplier,
        experiment=body.experiment,
    )
    result = run_cohort_regression(
        df,
        body.building_keys,
        label,
        reg_req,
        building_display_names={s.building_key: s.display_name for s in summaries},
    )
    return CohortRegressionResponse(
        **result.model_dump(),
        building_keys=body.building_keys,
        cohort_buildings=summaries,
        explain=AnalysisExplain(
            **build_residential_regression_explain(
                result,
                reg_req,
                asset_type=reg_req.asset_type,
                cohort=True,
            ),
        ),
    )


@router.post("/regression/predict", response_model=CollectiveRegressionPredictResponse)
def cohort_regression_predict(body: CohortRegressionPredictRequest, db: Session = Depends(get_collective_db)):
    df, summaries = _fetch_cohort_transactions(
        db,
        body.building_keys,
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

    dominant = str(df["asset_type"].mode().iloc[0]) if not df.empty else "apartment"
    try:
        raw = predict_regression(
            df,
            body,
            body.inputs,
            cohort_mode=len(body.building_keys) > 1,
            building_display_names={s.building_key: s.display_name for s in summaries},
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return CollectiveRegressionPredictResponse(**raw)
