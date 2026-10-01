"""분석 종류별 도구 연결. 플래너는 이 표만 보고 다음 행동을 고른다."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisSpec:
    analysis_type: str
    property_types: frozenset[str]
    needs_target: bool
    ask: str
    discovery_tool: str | None
    direct_tool: str
    follow_tool: str | None = None
    needs_measure: bool = False


_SPECS: dict[str, AnalysisSpec] = {}


def register(spec: AnalysisSpec) -> None:
    _SPECS[spec.analysis_type] = spec


def get_spec(analysis_type: str | None) -> AnalysisSpec | None:
    if not analysis_type:
        return None
    return _SPECS.get(analysis_type)


def list_specs() -> list[AnalysisSpec]:
    return list(_SPECS.values())


def reset_specs(specs: dict[str, AnalysisSpec] | None = None) -> None:
    _SPECS.clear()
    for spec in (specs or {}).values():
        register(spec)
