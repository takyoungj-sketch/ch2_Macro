"""MatrixYearlyRequest 가 PaidFilters 공통 필터(deal_types 등)를 상속하는지 검증."""

from app.schemas import MatrixYearlyRequest, PaidAnalysisRequest, PaidFilters


def test_paid_filters_exposes_deal_types():
    assert "deal_types" in PaidFilters.model_fields


def test_matrix_yearly_request_inherits_deal_types():
    assert "deal_types" in MatrixYearlyRequest.model_fields
    req = MatrixYearlyRequest(
        zone_type="자녹",
        land_category="답",
        deal_types=["중개거래"],
    )
    assert req.deal_types == ["중개거래"]


def test_paid_analysis_request_still_has_deal_types():
    assert "deal_types" in PaidAnalysisRequest.model_fields
