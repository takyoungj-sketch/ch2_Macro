"""신규아파트 실험 API 스키마."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class NewAptExperimentResponse(BaseModel):
    sido_code: Optional[str] = None
    sido_name: Optional[str] = None
    baseline: str = "M2"
    baseline_role: str = ""
    land_join: dict[str, Any] = Field(default_factory=dict)
    land_dispersion: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    m2: dict[str, Any] = Field(default_factory=dict)
    cells: list[dict[str, Any]] = Field(default_factory=list)
    cell_summary: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    error_audit: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class NewAptRegionCompareResponse(BaseModel):
    baseline: str = "M2"
    baseline_status: str = "daejeon_provisional"
    baseline_role: str = ""
    adopt_pooled: bool = False
    samples: dict[str, Any] = Field(default_factory=dict)
    models: list[dict[str, Any]] = Field(default_factory=list)
    transfer: dict[str, Any] = Field(default_factory=dict)
    next_steps: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
