"""AI 입구에서 비공개 기능 데이터 걷어내기 (D-085).

`/api/ai/chat` · `/api/ai/explain` · `/api/ai/history` 가 처리기(orchestrator)에 넘기기 전에
요청의 화면 컨텍스트(`context`, 그 안의 `facts.base_screen` 포함)를 고친다.
비관리자(또는 기능이 꺼진 경우)에게서 온 비공개 기능 값은 AI 가 읽지도, 세션 기록에 남기지도 않는다.

- `rent_regression` 꺼짐: 임대 상세의 회귀 탭(`detail_tab == "regression"`) 컨텍스트는 facts 를 비운다.
- `land_regression` 꺼짐: 토지 회귀·예측 패널(`LandRegressionTab`, `LandPredict`) 컨텍스트는 facts 를 비운다.
- `land_ledger_link` 꺼짐: facts 어디에 있든 대장 연결 값(공시지가·연결상태·연결 건수·`log_assessed_land_price`)을 지운다.

ai2(랩, 관리자 전용)는 이 경로를 쓰지 않는다.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request

from app.feature_gates import (
    LAND_LEDGER_LINK,
    LAND_REGRESSION,
    RENT_REGRESSION,
    feature_enabled,
)

LAND_REGRESSION_PANELS = frozenset({"LandRegressionTab", "LandPredict"})

# land_trait_link.TRAIT_ITEM_KEYS + 회귀 응답의 연결 건수·공시지가 기준연도
LEDGER_KEYS = frozenset(
    {
        "trait_link_status",
        "trait_link_label",
        "trait_price_status",
        "official_price_won",
        "official_price_year",
        "trait_asof",
        "trait_unverified",
        "recovered_lot",
        "trait_enrich_applied",
        "linked_n",
        "unlinked_n",
        "structural_excluded_n",
        "assessed_years",
        "log_assessed_land_price",
    }
)
LEDGER_TERMS = frozenset({"log_assessed_land_price"})
_TERM_FIELDS = ("name", "term", "variable", "key", "id")


def _is_ledger_term(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    return any(str(item.get(f) or "") in LEDGER_TERMS for f in _TERM_FIELDS)


def strip_ledger(value: Any) -> Any:
    """dict·list 를 따라가며 대장 연결 키와 공시지가 계수 항목을 지운다."""
    if isinstance(value, dict):
        return {k: strip_ledger(v) for k, v in value.items() if k not in LEDGER_KEYS}
    if isinstance(value, list):
        return [strip_ledger(v) for v in value if not _is_ledger_term(v)]
    return value


def _hidden_panel(app: str, panel: str, facts: dict, request: Request) -> bool:
    if app == "rent" and facts.get("detail_tab") == "regression":
        return not feature_enabled(request, RENT_REGRESSION)
    if app == "land" and panel in LAND_REGRESSION_PANELS:
        return not feature_enabled(request, LAND_REGRESSION)
    return False


def _clean_facts(app: str, panel: str, facts: dict, request: Request) -> tuple[dict, bool]:
    hidden = False
    if _hidden_panel(app, panel, facts, request):
        facts = {"detail_tab": facts["detail_tab"]} if "detail_tab" in facts else {}
        hidden = True
    base = facts.get("base_screen")
    if isinstance(base, dict) and isinstance(base.get("facts"), dict):
        b_facts, b_hidden = _clean_facts(
            str(base.get("app") or app), str(base.get("panel") or ""), base["facts"], request
        )
        facts = {**facts, "base_screen": {**base, "facts": b_facts}}
        hidden = hidden or b_hidden
    if not feature_enabled(request, LAND_LEDGER_LINK):
        facts = strip_ledger(facts)
    return facts, hidden


def filter_ai_context(context, request: Request):
    """AiContext 를 고친 사본을 돌려준다(원본 불변)."""
    facts, hidden = _clean_facts(str(context.app), str(context.panel), dict(context.facts or {}), request)
    update: dict[str, Any] = {"facts": facts}
    if hidden:
        # 화면 설명(explain)도 비공개 기능 설명일 수 있으므로 넘기지 않는다.
        update["explain"] = None
    return context.model_copy(update=update)


def filter_ai_body(body, request: Request):
    """context 를 가진 요청 본문(AiChatRequest·AiExplainRequest·AiHistoryRecordRequest)."""
    if getattr(body, "context", None) is None:
        return body
    return body.model_copy(update={"context": filter_ai_context(body.context, request)})
