"""CH2 AI — Pydantic 스키마 (AiContext, Evidence, Chat)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

AiApp = Literal["land", "built", "collective"]
AiPurpose = Literal["statistics", "prediction", "market_analysis", "methodology"]
AiRoute = Literal["refusal", "ch2", "explain", "statistics", "opinion", "web"]
EvidenceType = Literal[
    "ch2_regression",
    "ch2_sample",
    "ch2_correlation",
    "ch2_vif",
    "ch2_explain",
    "ch2_trend",
    "ch2_matrix",
    "stats_knowledge",
    "ai_opinion",
    "web",
    "refusal_policy",
]
EvidenceConfidence = Literal["high", "medium", "low"]


class AnalysisExplainPreset(BaseModel):
    id: str
    question: str
    answer: str


class AnalysisExplain(BaseModel):
    """집합 analysis_explain 와 동형 — AI Explain Router 입력."""

    spec_id: str
    spec_version: str = "1"
    title: str
    summary: str
    formula: Optional[str] = None
    index_rule: Optional[str] = None
    reference: Optional[str] = None
    floor_groups: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    interpretation: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    interpretation_hints: list[str] = Field(default_factory=list)
    presets: list[AnalysisExplainPreset] = Field(default_factory=list)


class AiScope(BaseModel):
    region_label: Optional[str] = None
    region_codes: list[str] = Field(default_factory=list)
    asset_type: Optional[str] = None
    filters: dict[str, Any] = Field(default_factory=dict)


class AiContext(BaseModel):
    """프론트 → AI: 현재 화면 컨텍스트 (Screen-bound)."""

    app: AiApp = "built"
    panel: str = "RegressionCard"
    purpose: AiPurpose = "statistics"
    scope: AiScope = Field(default_factory=AiScope)
    facts: dict[str, Any] = Field(default_factory=dict)
    explain: Optional[AnalysisExplain] = None


class EvidenceItem(BaseModel):
    type: EvidenceType
    label: str
    ref: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None
    confidence: EvidenceConfidence = "medium"


class AiChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=4000)
    context: AiContext = Field(default_factory=AiContext)


class AiExplainRequest(BaseModel):
    message: Optional[str] = None
    context: AiContext = Field(default_factory=AiContext)


class SuggestedQuestionsQuery(BaseModel):
    app: AiApp = "built"
    panel: str = "RegressionCard"
    purpose: AiPurpose = "statistics"


class AiChatResponse(BaseModel):
    session_id: str
    route: AiRoute
    answer: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    bundle_id: Optional[str] = None
    suggested_followups: list[str] = Field(default_factory=list)
    disclaimer: Optional[str] = None
    llm_used: bool = False
    trust_level: Optional[Literal["high", "medium", "low"]] = None
    trust_sources: list[str] = Field(default_factory=list)
    ai_interpretation: Optional[str] = None


class AiDiagnosticPack(BaseModel):
    """Reasoning Bundle — LLM/템플릿 공통 입력."""

    bundle_id: str
    panel: str
    app: AiApp
    summary_lines: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class AiHealthResponse(BaseModel):
    status: str = "ok"
    llm_configured: bool = False
    polish_enabled: bool = False
    web_search_configured: bool = False
    model: Optional[str] = None
    constitution_version: str = "1"
