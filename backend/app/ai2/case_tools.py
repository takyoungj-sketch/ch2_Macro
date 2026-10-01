"""토지 쌍둥이·복합 예측 픽스처. 숫자는 프로토콜용이고 원장을 읽지 않는다."""

from __future__ import annotations

from dataclasses import dataclass

from app.ai2.catalog import AnalysisSpec, register
from app.ai2.types import AnalysisContext, ToolEnvelope

# built/regression/engine.py 예측: n < 10 이면 예측 불가.
BUILT_PREDICT_MIN_N = 10

TWIN_SPEC = AnalysisSpec(
    analysis_type="twin_region",
    property_types=frozenset({"land"}),
    needs_target=False,
    ask="",
    discovery_tool=None,
    direct_tool="twin_status",
)

BUILT_VALUE_SPEC = AnalysisSpec(
    analysis_type="built_value",
    property_types=frozenset({"built"}),
    needs_target=False,
    ask="총액인가요, ㎡당인가요?",
    discovery_tool=None,
    direct_tool="built_predict",
    needs_measure=True,
)

SHOP_AREA_SPEC = AnalysisSpec(
    analysis_type="shop_area",
    property_types=frozenset({"collective_shop"}),
    needs_target=True,
    ask="특정 도로인가요, 이 지역 전체인가요?",
    discovery_tool="sample_status",
    direct_tool="floor_index",
)

SHOP_FLOOR_SPEC = AnalysisSpec(
    analysis_type="shop_floor",
    property_types=frozenset({"collective_shop"}),
    needs_target=True,
    ask="특정 도로인가요, 이 지역 전체인가요?",
    discovery_tool="sample_status",
    direct_tool="floor_index",
)

FACTORY_FLOOR_SPEC = AnalysisSpec(
    analysis_type="factory_floor",
    property_types=frozenset({"collective_shop", "collective_factory"}),
    needs_target=True,
    ask="특정 도로인가요, 이 지역 전체인가요?",
    discovery_tool="sample_status",
    direct_tool="floor_index",
)

FACTORY_AREA_SPEC = AnalysisSpec(
    analysis_type="factory_area",
    property_types=frozenset({"collective_shop", "collective_factory"}),
    needs_target=True,
    ask="특정 도로인가요, 이 지역 전체인가요?",
    discovery_tool="sample_status",
    direct_tool="floor_index",
)

RENT_RATE_SPEC = AnalysisSpec(
    analysis_type="rent_conversion",
    property_types=frozenset({"rent"}),
    needs_target=False,
    ask="",
    discovery_tool=None,
    direct_tool="rent_rate",
)

PROFILE_TWIN_SPEC = AnalysisSpec(
    analysis_type="profile_twin",
    property_types=frozenset({"profile"}),
    needs_target=False,
    ask="",
    discovery_tool=None,
    direct_tool="profile_twin_status",
)

BUILT_SPEC = AnalysisSpec(
    analysis_type="built_predict",
    property_types=frozenset({"built"}),
    needs_target=False,
    ask="",
    discovery_tool=None,
    direct_tool="built_predict",
)

UNAVAILABLE_ANALYSIS = {
    "land_regression": "토지 회귀는 현재 제공하지 않습니다.",
}


@dataclass(frozen=True)
class CaseWorld:
    kind: str
    period: str = "2021-09~2026-08"
    valid_n: int = 0
    twin_adopted: bool = False
    twin_region: str | None = None
    local_cv_mape: float | None = None
    twin_cv_mape: float | None = None
    y_hat: float | None = None
    pi_lower: float | None = None
    pi_upper: float | None = None
    y_hat_suppressed: bool = False
    reference_inputs: tuple[str, ...] = ()
    price_base_year: int | None = None


CASES: dict[str, CaseWorld] = {
    "twin_worse": CaseWorld(
        kind="twin",
        twin_adopted=False,
        twin_region="오창읍",
        local_cv_mape=12.0,
        twin_cv_mape=14.5,
        valid_n=40,
    ),
    "twin_better": CaseWorld(
        kind="twin",
        twin_adopted=True,
        twin_region="오창읍",
        local_cv_mape=14.0,
        twin_cv_mape=11.0,
        valid_n=40,
    ),
    "built_ok": CaseWorld(
        kind="built",
        valid_n=40,
        y_hat=1520.0,
        pi_lower=980.0,
        pi_upper=2100.0,
        price_base_year=2025,
    ),
    "built_partial": CaseWorld(
        kind="built",
        valid_n=40,
        y_hat=1520.0,
        pi_lower=980.0,
        pi_upper=2100.0,
        price_base_year=2025,
        reference_inputs=("building_age", "road_width"),
    ),
    "built_short": CaseWorld(kind="built", valid_n=8),
    "built_extrap": CaseWorld(
        kind="built",
        valid_n=40,
        y_hat=1520.0,
        pi_lower=400.0,
        pi_upper=9000.0,
        y_hat_suppressed=True,
        price_base_year=2025,
    ),
}


def install_case_specs() -> None:
    register(TWIN_SPEC)
    register(BUILT_SPEC)
    register(BUILT_VALUE_SPEC)
    register(SHOP_FLOOR_SPEC)
    register(SHOP_AREA_SPEC)
    register(FACTORY_FLOOR_SPEC)
    register(FACTORY_AREA_SPEC)
    register(RENT_RATE_SPEC)
    register(PROFILE_TWIN_SPEC)


def run_case_tool(tool_id: str, ctx: AnalysisContext, world: CaseWorld) -> ToolEnvelope:
    period = ctx.period or world.period
    if tool_id == "twin_status":
        adopted = world.twin_adopted
        return ToolEnvelope(
            tool_id=tool_id,
            level="ok" if adopted else "caution",
            analysis_possible=True,
            reason_code=None if adopted else "TWIN_NOT_ADOPTED",
            valid_n=world.valid_n,
            period=period,
            facts={
                "twin_adopted": adopted,
                "twin_region": world.twin_region,
                "local_cv_mape": world.local_cv_mape,
                "twin_cv_mape": world.twin_cv_mape,
            },
        )
    if tool_id == "built_predict":
        if world.valid_n < BUILT_PREDICT_MIN_N:
            return ToolEnvelope(
                tool_id=tool_id,
                level="impossible",
                analysis_possible=False,
                reason_code="INSUFFICIENT_SAMPLE",
                valid_n=world.valid_n,
                required_n=BUILT_PREDICT_MIN_N,
                period=period,
            )
        return ToolEnvelope(
            tool_id=tool_id,
            level="caution" if world.y_hat_suppressed else "ok",
            analysis_possible=True,
            reason_code="EXTRAPOLATION" if world.y_hat_suppressed else None,
            valid_n=world.valid_n,
            required_n=BUILT_PREDICT_MIN_N,
            period=period,
            facts={
                "y_hat": world.y_hat,
                "pi_lower": world.pi_lower,
                "pi_upper": world.pi_upper,
                "y_hat_suppressed": world.y_hat_suppressed,
                "reference_inputs": list(world.reference_inputs),
                "price_base_year": world.price_base_year,
            },
        )
    return ToolEnvelope(
        tool_id=tool_id,
        level="impossible",
        analysis_possible=False,
        reason_code="UNSUPPORTED",
        period=period,
    )
