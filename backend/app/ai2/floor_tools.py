"""아파트 층별효용 도구. 첫 사례일 뿐이고, 판정 숫자는 집합 게이트를 그대로 쓴다."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.collective.analysis_gates import MIN_COUNT_FLOOR_INDEX
from app.collective.floor_index_regression import MIN_GROUP_FOR_DUMMY

from app.ai2.catalog import AnalysisSpec, register
from app.ai2.types import Alternative, AnalysisContext, ToolEnvelope

FLOOR_SPEC = AnalysisSpec(
    analysis_type="floor_utility",
    property_types=frozenset({"apartment"}),
    needs_target=True,
    ask="특정 단지인가요, 이 지역 전체인가요?",
    discovery_tool="sample_status",
    direct_tool="floor_index",
    follow_tool="insight_compare",
)

FORMULA_SPEC = AnalysisSpec(
    analysis_type="floor_utility_method",
    property_types=frozenset({"apartment"}),
    needs_target=False,
    ask="",
    discovery_tool=None,
    direct_tool="floor_formula",
)


@dataclass
class ComplexRow:
    name: str
    n: int
    thin_floor_group: str | None = None
    thin_n: int | None = None
    local_index: float | None = None


@dataclass
class FloorWorld:
    period: str = "2021-09~2026-08"
    complexes: list[ComplexRow] = field(default_factory=list)
    expand_region: str | None = None
    expand_region_feasible: bool = False
    period_expand_feasible: bool = False
    insight_top_index: float = 108.0
    insight_id: str = "08"
    expanded_complexes: list[ComplexRow] = field(default_factory=list)


WORLDS: dict[str, FloorWorld] = {
    "below_gate": FloorWorld(
        complexes=[
            ComplexRow("A아파트", 27),
            ComplexRow("B아파트", 21),
            ComplexRow("C아파트", 13),
        ],
        expand_region="흥덕구",
        expand_region_feasible=True,
    ),
    "one_eligible": FloorWorld(
        complexes=[
            ComplexRow("A아파트", 62, local_index=120.0),
            ComplexRow("B아파트", 21),
            ComplexRow("C아파트", 13),
        ],
        expand_region="흥덕구",
        expand_region_feasible=True,
    ),
    "named_ok": FloorWorld(
        complexes=[ComplexRow("세원가경골", 80, local_index=112.0)],
    ),
    "period_snap": FloorWorld(
        complexes=[ComplexRow("세원가경골", 80, local_index=112.0)],
        period_expand_feasible=True,
    ),
    "two_alts": FloorWorld(
        complexes=[ComplexRow("세원가경골", 80, local_index=112.0)],
        expand_region="흥덕구",
        expand_region_feasible=True,
        period_expand_feasible=True,
    ),
    "expand_hits": FloorWorld(
        complexes=[
            ComplexRow("A아파트", 27),
            ComplexRow("B아파트", 21),
            ComplexRow("C아파트", 13),
        ],
        expand_region="흥덕구",
        expand_region_feasible=True,
        expanded_complexes=[ComplexRow("넓은단지", 70, local_index=105.0)],
    ),
    "named_short": FloorWorld(
        complexes=[ComplexRow("짧은단지", 8)],
    ),
    "thin_group": FloorWorld(
        complexes=[
            ComplexRow("세원가경골", 80, thin_floor_group="최상층", thin_n=3, local_index=112.0)
        ],
    ),
}


def install_floor_spec() -> None:
    register(FLOOR_SPEC)
    register(FORMULA_SPEC)


def _row(world: FloorWorld, name: str) -> ComplexRow | None:
    rows = [*world.complexes, *world.expanded_complexes]
    return next((c for c in rows if c.name == name), None)


def _eligible(world: FloorWorld) -> list[ComplexRow]:
    return [c for c in world.complexes if c.n >= MIN_COUNT_FLOOR_INDEX]


def _period_block(tool_id: str, ctx: AnalysisContext, world: FloorWorld) -> ToolEnvelope | None:
    if not ctx.period or ctx.period == world.period:
        return None
    alts: list[Alternative] = []
    reason = "PERIOD_UNAVAILABLE"
    if world.period_expand_feasible:
        reason = "PERIOD_OUTSIDE"
        alts.append(Alternative("expand_period", world.period, True, {"period": world.period}))
        if world.expand_region_feasible and world.expand_region:
            alts.append(
                Alternative(
                    "expand_region",
                    world.expand_region,
                    True,
                    {"region": world.expand_region},
                )
            )
    return ToolEnvelope(
        tool_id=tool_id,
        level="impossible",
        analysis_possible=False,
        reason_code=reason,
        period=world.period,
        alternative_tools=alts,
        facts={"requested_period": ctx.period},
    )


def run_floor_tool(tool_id: str, ctx: AnalysisContext, args: dict, world: FloorWorld) -> ToolEnvelope:
    period = ctx.period or world.period
    if tool_id in ("sample_status", "floor_index"):
        blocked = _period_block(tool_id, ctx, world)
        if blocked is not None:
            return blocked
    if tool_id == "floor_formula":
        return ToolEnvelope(
            tool_id=tool_id,
            level="fact",
            analysis_possible=True,
            period="2021-09-01~2026-08-31",
            comparable=False,
            facts={
                "index_rule": "지수_g = exp(γ_g) × 100  (1층 = 100%, 더미 없음)",
                "screen": "아파트는 그 단지 최고층 대비 1층·저층부·중층부·고층부·최상층. 화면 100은 1층.",
                "insight_id": world.insight_id,
                "insight_window": "2021-09-01~2026-08-31",
                "reran": False,
            },
        )
    if tool_id == "sample_status":
        valid_n = sum(c.n for c in world.complexes)
        alts: list[Alternative] = []
        if _eligible(world):
            alts.append(
                Alternative("representative_candidates", "대표 단지 후보", False, {})
            )
        elif world.expand_region_feasible and world.expand_region:
            alts.append(
                Alternative(
                    "expand_region",
                    world.expand_region,
                    True,
                    {"region": world.expand_region},
                )
            )
        return ToolEnvelope(
            tool_id=tool_id,
            level="impossible",
            analysis_possible=False,
            reason_code="NO_REGION_LEVEL_INDEX",
            valid_n=valid_n,
            required_n=MIN_COUNT_FLOOR_INDEX,
            excluded_n=0,
            period=period,
            alternative_tools=alts,
            facts={
                "complexes": [{"name": c.name, "n": c.n} for c in world.complexes],
                "sample_meets_floor_gate": valid_n >= MIN_COUNT_FLOOR_INDEX,
            },
        )
    if tool_id == "representative_candidates":
        eligible = _eligible(world)
        if not eligible:
            return ToolEnvelope(
                tool_id=tool_id,
                level="impossible",
                analysis_possible=False,
                reason_code="INSUFFICIENT_SAMPLE",
                valid_n=max((c.n for c in world.complexes), default=0),
                required_n=MIN_COUNT_FLOOR_INDEX,
                period=period,
                facts={"candidates": [{"name": c.name, "n": c.n} for c in world.complexes]},
            )
        selected = max(eligible, key=lambda c: c.n)
        return ToolEnvelope(
            tool_id=tool_id,
            level="fact",
            analysis_possible=True,
            valid_n=selected.n,
            required_n=MIN_COUNT_FLOOR_INDEX,
            period=period,
            alternative_tools=[
                Alternative(
                    "floor_index",
                    selected.name,
                    True,
                    {"target": selected.name},
                )
            ],
            facts={
                "selected": selected.name,
                "selected_n": selected.n,
                "candidates": [{"name": c.name, "n": c.n} for c in world.complexes],
                "rule": "거래 수가 가장 많고 최소 건수를 넘는 단지",
            },
        )
    if tool_id == "floor_index":
        name = str(args.get("target") or ctx.target or "")
        row = _row(world, name)
        if row is None or row.n < MIN_COUNT_FLOOR_INDEX:
            n = 0 if row is None else row.n
            return ToolEnvelope(
                tool_id=tool_id,
                level="impossible",
                analysis_possible=False,
                reason_code="INSUFFICIENT_SAMPLE",
                valid_n=n,
                required_n=MIN_COUNT_FLOOR_INDEX,
                period=period,
                facts={"target": name},
            )
        excluded = 0
        facts: dict = {"target": row.name, "local_index": row.local_index}
        level: str = "ok"
        reason = None
        if row.thin_floor_group is not None and (row.thin_n or 0) < MIN_GROUP_FOR_DUMMY:
            excluded = row.thin_n or 0
            level = "caution"
            reason = "INSUFFICIENT_FLOOR_GROUP"
            facts["blank_group"] = row.thin_floor_group
            facts["blank_group_n"] = row.thin_n
            facts["floor_group_min"] = MIN_GROUP_FOR_DUMMY
        return ToolEnvelope(
            tool_id=tool_id,
            level=level,  # type: ignore[arg-type]
            analysis_possible=True,
            reason_code=reason,
            valid_n=row.n,
            required_n=MIN_COUNT_FLOOR_INDEX,
            excluded_n=excluded,
            period=period,
            facts=facts,
        )
    if tool_id == "insight_compare":
        local = None
        for env_facts in (args,):
            local = env_facts.get("local_index")
        return ToolEnvelope(
            tool_id=tool_id,
            level="fact",
            analysis_possible=True,
            reason_code="DIFFERENT_POPULATION",
            period=world.period,
            comparable=False,
            facts={
                "insight_id": world.insight_id,
                "top_floor_index": world.insight_top_index,
                "window": world.period,
                "local_index": local,
            },
        )
    if tool_id == "expand_region":
        eligible = [c for c in world.expanded_complexes if c.n >= MIN_COUNT_FLOOR_INDEX]
        if not eligible:
            return ToolEnvelope(
                tool_id=tool_id,
                level="impossible",
                analysis_possible=False,
                reason_code="NO_DATA_FOR_REGION",
                period=period,
                facts={"region": args.get("region")},
            )
        selected = max(eligible, key=lambda c: c.n)
        return ToolEnvelope(
            tool_id=tool_id,
            level="fact",
            analysis_possible=True,
            reason_code="REGION_EXPANDED",
            valid_n=selected.n,
            required_n=MIN_COUNT_FLOOR_INDEX,
            period=period,
            alternative_tools=[
                Alternative("floor_index", selected.name, True, {"target": selected.name})
            ],
            facts={
                "region": args.get("region"),
                "selected": selected.name,
                "selected_n": selected.n,
            },
        )
    if tool_id == "expand_period":
        return ToolEnvelope(
            tool_id=tool_id,
            level="fact",
            analysis_possible=False,
            reason_code="PERIOD_APPLIED",
            period=str(args.get("period") or world.period),
            facts={"period": args.get("period")},
        )
    return ToolEnvelope(
        tool_id=tool_id,
        level="impossible",
        analysis_possible=False,
        reason_code="UNSUPPORTED",
        period=period,
    )
