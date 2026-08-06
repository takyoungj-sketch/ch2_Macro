"""R0 — analysis_scope SSOT (built)."""

from __future__ import annotations

from app.built.schemas import RegressionRunRequest, RegressionVariableSpec
from app.recommendation.models import AnalysisRegionUnitHint
from app.recommendation.scope import (
    _region_units_from_hints,
    resolve_anchor_unit,
    scope_from_built_request,
)

def test_region_units_from_hints_dedupes_codes():
    hints = [
        AnalysisRegionUnitHint(
            code="4311210100",
            level="eupmyeondong",
            name="봉명동",
            addr1="충청북도",
            addr2="청주시 흥덕구",
        ),
        AnalysisRegionUnitHint(
            code="4311210100",
            level="eupmyeondong",
            name="봉명동",
            addr1="충청북도",
            addr2="청주시 흥덕구",
        ),
    ]
    units = _region_units_from_hints(hints)
    assert len(units) == 1
    assert units[0].name == "봉명동"
    assert units[0].code == "4311210100"


def test_resolve_anchor_skips_cross_parent():
    from app.recommendation.models import RegionUnitRef

    units = [
        RegionUnitRef(
            code="1100000000",
            level="eupmyeondong",
            name="타지역",
            cross_parent=True,
        ),
        RegionUnitRef(
            code="4311210100",
            level="eupmyeondong",
            name="봉명동",
        ),
    ]
    anchor = resolve_anchor_unit(units)
    assert anchor is not None
    assert anchor.name == "봉명동"


def test_resolve_anchor_explicit_code():
    from app.recommendation.models import RegionUnitRef

    units = [
        RegionUnitRef(code="4311210200", level="eupmyeondong", name="운천동"),
        RegionUnitRef(code="4311210100", level="eupmyeondong", name="봉명동"),
    ]
    anchor = resolve_anchor_unit(units, anchor_region_code="4311210100")
    assert anchor is not None
    assert anchor.name == "봉명동"


def test_scope_from_built_request_carries_filters_and_codes():
    req = RegressionRunRequest(
        asset_type="commercial",
        region_codes=["4311210100", "4311210200"],
        region_code_level="eupmyeondong",
        region_addrs=["충청북도|청주시 흥덕구|봉명동", "충청북도|청주시 흥덕구|운천동"],
        anchor_region_code="4311210100",
        region_unit_hints=[
            AnalysisRegionUnitHint(
                code="4311210100",
                level="eupmyeondong",
                name="봉명동",
                addr1="충청북도",
                addr2="청주시 흥덕구",
            ),
            AnalysisRegionUnitHint(
                code="4311210200",
                level="eupmyeondong",
                name="운천동",
                addr1="충청북도",
                addr2="청주시 흥덕구",
                cross_parent=True,
            ),
        ],
        zone_types=["일반상업"],
        variables=RegressionVariableSpec(),
    )
    scope = scope_from_built_request(req)
    assert scope.domain == "built"
    assert scope.asset_slice == "commercial"
    assert len(scope.region_units) == 2
    assert scope.anchor_unit is not None
    assert scope.anchor_unit.name == "봉명동"
    assert scope.sample_filters.zone_types == ["일반상업"]
    assert scope.region_codes == ["4311210100", "4311210200"]
