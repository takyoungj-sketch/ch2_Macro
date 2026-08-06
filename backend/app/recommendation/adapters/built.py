"""Built domain recommend adapter (R1/R2)."""

from __future__ import annotations

from app.built.schemas import RegressionRecommendResponse, RegressionSelectionRequest
from app.recommendation.stages import run_recommendation


def recommend_built_regression(conn, req: RegressionSelectionRequest) -> RegressionRecommendResponse:
    return run_recommendation(conn, req)
