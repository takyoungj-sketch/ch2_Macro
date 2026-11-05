"""AI3 계약. 클라이언트가 실행 상태·승인·엔진 결과를 만들 수 없다."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Context(StrictModel):
    app: Literal["land", "built", "collective", "commercial", "rent", "profile", "insight"] = "land"
    panel: str = Field(default="", max_length=100)
    region_label: str = Field(default="", max_length=120)
    # 화면 스냅샷은 엔진 History와 구별하고 허용된 요약만 전달한다.
    metrics: dict[str, float] = Field(default_factory=dict, max_length=24)


class ChatIn(StrictModel):
    session_id: str | None = Field(default=None, max_length=80)
    message: str = Field(min_length=1, max_length=4000)
    context: Context = Field(default_factory=Context)
    tool_id: str | None = Field(default=None, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ExecuteIn(StrictModel):
    session_id: str = Field(max_length=80)
    plan_id: str = Field(max_length=80)
    # 실행 입력은 받지 않는다. 서버가 저장한 불변 계획만 승인한다.


class Evidence(StrictModel):
    id: str
    label: str
    source: str


class Plan(StrictModel):
    id: str
    tool_id: str
    label: str
    arguments: dict[str, Any]
    created_at: float
    expires_at: float


class Fact(StrictModel):
    id: str
    label: str
    value: str
    source: str


class ChatOut(StrictModel):
    session_id: str
    answer: str
    kind: Literal["answer", "clarify", "plan", "refusal", "unavailable"] = "answer"
    evidence: list[Evidence] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    plan: Plan | None = None
    llm_used: bool = False
    history_ids: list[str] = Field(default_factory=list)


class ExecutionOut(StrictModel):
    id: str
    session_id: str
    plan_id: str
    tool_id: str = ""
    status: Literal["running", "succeeded", "failed", "cancel_requested", "cancelled"]
    created_at: float
    finished_at: float | None = None
    applied_arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    facts: list[Fact] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    error: str | None = None


class LandArgs(StrictModel):
    beopjungri_code: str = Field(pattern=r"^\d{10}$")
    window_years: Literal[3, 5, 7]
    as_of_month: str = Field(pattern=r"^\d{4}-\d{2}-01$")
    matrix_mode: Literal["category", "group"] = "category"


class FloorArgs(StrictModel):
    target_key: str = Field(min_length=1, max_length=300)
    year_from: int = Field(ge=2006, le=2100)
    year_to: int = Field(ge=2006, le=2100)
    dimension: Literal["floor", "area"] = "floor"
    floor_mode: Literal["relative", "rowhouse", "shop", "factory"] = "relative"


class RentArgs(StrictModel):
    addr1: str = Field(min_length=1, max_length=30)
    addr2: str = Field(min_length=1, max_length=60)
    asset_type: Literal["apartment", "officetel", "rowhouse"] = "apartment"
    window_years: Literal[3, 5, 7]
    as_of_month: str = Field(pattern=r"^\d{4}-\d{2}-01$")


class TwinArgs(StrictModel):
    sigungu_code: str = Field(pattern=r"^\d{5}$")
    window_years: Literal[3, 5]
    scope: Literal["adjacent", "region", "national"] = "national"
    twin_profile: Literal["general", "built_commercial"] = "general"
    profile_version: Literal["v2.1-national"] = "v2.1-national"
    top_k: int = Field(default=3, ge=1, le=5)


class RegionSearchArgs(StrictModel):
    name: str = Field(min_length=2, max_length=30)


class TargetSearchArgs(StrictModel):
    addr1: str = Field(min_length=1, max_length=30)
    addr2: str = Field(min_length=1, max_length=60)
    addr4: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=60)
    domain: Literal["residential", "commercial"] = "residential"
