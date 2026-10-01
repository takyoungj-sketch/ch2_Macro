"""AI2 분석 맥락과 도구 봉투. 지역·분석 이름에 묶이지 않는다."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ActionKind = Literal["ask", "call", "offer", "refuse", "report"]
Level = Literal["ok", "impossible", "caution", "fact"]


@dataclass
class AnalysisContext:
    region: str | None = None
    property_type: str | None = None
    analysis_type: str | None = None
    target: str | None = None
    period: str | None = None
    measure: str | None = None
    gross_area: float | None = None
    land_area: float | None = None
    building_age: float | None = None
    road_width_label: str | None = None

    def to_dict(self) -> dict:
        return {
            "region": self.region,
            "property_type": self.property_type,
            "analysis_type": self.analysis_type,
            "target": self.target,
            "period": self.period,
            "measure": self.measure,
            "gross_area": self.gross_area,
            "land_area": self.land_area,
            "building_age": self.building_age,
            "road_width_label": self.road_width_label,
        }


@dataclass
class Alternative:
    id: str
    change: str
    needs_confirm: bool
    args: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "change": self.change,
            "needs_confirm": self.needs_confirm,
            "args": self.args,
        }


@dataclass
class ToolEnvelope:
    tool_id: str
    level: Level
    analysis_possible: bool
    reason_code: str | None = None
    valid_n: int | None = None
    required_n: int | None = None
    excluded_n: int | None = None
    period: str | None = None
    alternative_tools: list[Alternative] = field(default_factory=list)
    comparable: bool | None = None
    facts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tool_id": self.tool_id,
            "level": self.level,
            "analysis_possible": self.analysis_possible,
            "reason_code": self.reason_code,
            "valid_n": self.valid_n,
            "required_n": self.required_n,
            "excluded_n": self.excluded_n,
            "period": self.period,
            "alternative_tools": [a.to_dict() for a in self.alternative_tools],
            "comparable": self.comparable,
            "facts": self.facts,
        }


@dataclass
class Action:
    kind: ActionKind
    message: str
    tool_id: str | None = None
    args: dict = field(default_factory=dict)
    alternatives: list[Alternative] = field(default_factory=list)
    envelope: ToolEnvelope | None = None
    verdict: str | None = None
    comparable: bool | None = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "message": self.message,
            "tool_id": self.tool_id,
            "args": self.args,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "envelope": None if self.envelope is None else self.envelope.to_dict(),
            "verdict": self.verdict,
            "comparable": self.comparable,
        }
