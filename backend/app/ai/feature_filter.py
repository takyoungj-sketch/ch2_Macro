"""AI 쪽 비공개 기능 처리 (D-085).

세 군데에서 같은 기준(현재 요청자의 기능 상태)을 쓴다.

1. **입구** — `/api/ai/chat` · `/explain` · `/history` 가 처리기에 넘기기 전에 요청의 화면 컨텍스트
   (`context`, `facts.base_screen` 포함)를 고친다(`filter_ai_body`).
   - `rent_regression` 꺼짐: 임대 상세 회귀 탭(`detail_tab == "regression"`) facts 를 비운다.
   - `land_regression` 꺼짐: 토지 회귀·예측 패널(`LandRegressionTab`, `LandPredict`) facts 를 비운다.
   - `land_ledger_link` 꺼짐: facts 어디에 있든 대장 연결 값을 지운다.
2. **세션 재생** — 세션에 남는 것(대화 턴·분석 History·화면 스냅샷·이전 근거 `dialogue_evidence`)에
   그 요청이 실제로 쓴 비공개 기능 이름을 붙여 둔다(`current_used`). 다음 요청에서 세션을 꺼낼 때
   현재 요청자에게 꺼진 기능이 붙은 항목은 지운다(`sessions.purge_hidden`). 안내 문구는 만들지 않는다.
3. **제품 지식·저장 결과** — 제품 지식 문구에서 꺼진 기능 설명을 빼고(`product_view`),
   저장된 AI 결과 조회는 꺼진 기능 화면의 결과를 돌려주지 않는다(`stored_result_visible`).

기능 상태는 요청마다 `ai_feature_scope(request, context)` 로 묶는다. 묶이지 않은 호출(내부·테스트)은
공개(`public`) 기능만 켜진 것으로 본다.

ai2(랩, 관리자 전용)는 이 경로를 쓰지 않는다.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterable

from fastapi import Request

from app.feature_gates import (
    FEATURES,
    LAND_LEDGER_LINK,
    LAND_REGRESSION,
    RENT_REGRESSION,
    enabled_features,
    feature_mode,
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

ALL = frozenset(FEATURES)

_enabled: ContextVar[frozenset | None] = ContextVar("ch2_ai_features_enabled", default=None)
_used: ContextVar[frozenset] = ContextVar("ch2_ai_features_used", default=frozenset())
_admin: ContextVar[bool] = ContextVar("ch2_ai_features_admin", default=False)
_unknown: ContextVar[bool] = ContextVar("ch2_ai_features_unknown", default=False)


# ── facts 고치기 ───────────────────────────────────────────────

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


def _hidden_panel(app: str, panel: str, facts: dict, enabled: frozenset) -> bool:
    if app == "rent" and facts.get("detail_tab") == "regression":
        return RENT_REGRESSION not in enabled
    if app == "land" and panel in LAND_REGRESSION_PANELS:
        return LAND_REGRESSION not in enabled
    return False


def clean_facts(app: str, panel: str, facts: dict, enabled: frozenset) -> tuple[dict, bool]:
    hidden = False
    if _hidden_panel(app, panel, facts, enabled):
        facts = {"detail_tab": facts["detail_tab"]} if "detail_tab" in facts else {}
        hidden = True
    base = facts.get("base_screen")
    if isinstance(base, dict) and isinstance(base.get("facts"), dict):
        b_facts, b_hidden = clean_facts(
            str(base.get("app") or app), str(base.get("panel") or ""), base["facts"], enabled
        )
        facts = {**facts, "base_screen": {**base, "facts": b_facts}}
        hidden = hidden or b_hidden
    if LAND_LEDGER_LINK not in enabled:
        facts = strip_ledger(facts)
    return facts, hidden


def features_used(context) -> frozenset:
    """이 컨텍스트가 실제로 담고 있는 비공개 기능 값(그 기능을 끄면 facts 가 달라지는 것)."""
    app, panel, facts = str(context.app), str(context.panel), dict(context.facts or {})
    full, _ = clean_facts(app, panel, facts, ALL)
    used = set()
    for name in FEATURES:
        without, _ = clean_facts(app, panel, facts, ALL - {name})
        if without != full:
            used.add(name)
    return frozenset(used)


def filter_context_for(context, enabled: frozenset):
    facts, hidden = clean_facts(str(context.app), str(context.panel), dict(context.facts or {}), enabled)
    update: dict[str, Any] = {"facts": facts}
    if hidden:
        # 화면 설명(explain)도 비공개 기능 설명일 수 있으므로 넘기지 않는다.
        update["explain"] = None
    return context.model_copy(update=update)


def filter_ai_context(context, request: Request):
    """AiContext 를 고친 사본을 돌려준다(원본 불변)."""
    return filter_context_for(context, frozenset(enabled_features(request)))


def filter_ai_body(body, request: Request):
    """context 를 가진 요청 본문(AiChatRequest·AiExplainRequest·AiHistoryRecordRequest)."""
    if getattr(body, "context", None) is None:
        return body
    return body.model_copy(update={"context": filter_ai_context(body.context, request)})


# ── 요청 단위 기능 상태 ─────────────────────────────────────────

def _public_only() -> frozenset:
    return frozenset(name for name in FEATURES if feature_mode(name) == "public")


def current_enabled() -> frozenset:
    bound = _enabled.get()
    return bound if bound is not None else _public_only()


def scope_bound() -> bool:
    return _enabled.get() is not None


def current_used() -> frozenset:
    return _used.get()


def add_used(tag: Any) -> None:
    """이 요청의 답이 이전 근거를 쓸 수 있게 되면, 그 근거의 표지를 이 요청 표지에 합친다
    (답 표지 = 현재 요청에서 쓴 것 ∪ 이전 근거에서 쓴 것)."""
    used = tag_used(tag)
    if used is None or tag_unknown(tag):
        # 표지 없는 근거(출처 불명)를 썼다 — 이후 재저장·재질문을 거쳐도 이 표시는 유지된다.
        _unknown.set(True)
    if used:
        _used.set(_used.get() | used)


def current_unknown() -> bool:
    return bool(_unknown.get())


def is_admin_now() -> bool:
    return bool(_admin.get())


# ── 기능 표지와 재생 허용(허용 목록 방식) ─────────────────────────────

TAG_VERSION = 1


def make_tag(used: Iterable[str] | None = None, *, unknown: bool | None = None) -> dict:
    """저장·세션 항목에 붙이는 표지. 쓴 비공개 기능이 없어도 표지는 항상 남긴다.
    인자를 생략하면 이 요청의 표지(현재 요청 ∪ 이전 근거, 출처 불명 포함)를 쓴다."""
    tag: dict = {"v": TAG_VERSION, "used": sorted(set(current_used() if used is None else used))}
    if (current_unknown() if unknown is None else unknown):
        tag["unknown"] = True
    return tag


def tag_unknown(tag: Any) -> bool:
    """출처 불명 표시가 붙은 표지인가(표지 자체가 없는 경우는 tag_used 가 None 으로 따로 본다)."""
    return isinstance(tag, dict) and bool(tag.get("unknown"))


def tag_used(tag: Any) -> frozenset | None:
    """표지에서 쓴 기능 집합. 표지가 아니면(없음·비어 있음·옛 형식) None."""
    if isinstance(tag, dict) and tag.get("v") == TAG_VERSION and isinstance(tag.get("used"), list):
        return frozenset(str(x) for x in tag["used"])
    return None


def replay_allowed(tag: Any, *, has_evidence: bool = True) -> bool:
    """저장된 AI 답·근거를 지금 요청자에게 재생해도 되는가 — 모든 재생 경로의 단일 관문.

    대상: 재시도 `ticket.replay`, 결과 조회 `/api/ai/requests/{id}`, 세션 History·스냅샷·대화 턴,
    previous 근거(`dialogue_evidence`).
    - 관리자: 그대로 허용.
    - 비관리자: 표지가 있고, 표지의 기능 중 지금 꺼진 것이 하나도 없을 때만 허용.
      표지가 없거나 비어 있는데(옛 형식 포함) 근거가 있으면 거절.
      출처 불명(`unknown`) 표지는 거절 — 표지 없는 근거를 거쳐 만든 답이다.
    """
    if is_admin_now():
        return True
    if not has_evidence:
        return True
    used = tag_used(tag)
    if used is None or tag_unknown(tag):
        return False
    return used <= current_enabled()


@contextmanager
def ai_feature_scope(request: Request, context=None):
    """요청자 기능 상태와, 이 요청(필터 뒤)이 쓴 비공개 기능을 묶는다."""
    from app.feature_gates import is_admin

    enabled = frozenset(enabled_features(request))
    used = features_used(context) & enabled if context is not None else frozenset()
    t1 = _enabled.set(enabled)
    t2 = _used.set(used)
    t3 = _admin.set(is_admin(request))
    t4 = _unknown.set(False)
    try:
        yield enabled
    finally:
        _unknown.reset(t4)
        _admin.reset(t3)
        _used.reset(t2)
        _enabled.reset(t1)


# ── 제품 지식 ─────────────────────────────────────────────────

_LAND_APP_LINE = "- land(토지): 용도지역×지목 매트릭스·장기추세·유료 필지 회귀"
_LAND_APP_LINE_HIDDEN = "- land(토지): 용도지역×지목 매트릭스·장기추세·단가 분포·거래목록"
_LAND_PACK_LINE = (
    "land: 용도지역×지목 매트릭스 셀 회귀·장기추세·유료 필지 분석. "
    "셀별 n·Adj R²·모델(log/선형)은 Bundle facts만 인용."
)
_LAND_PACK_LINE_HIDDEN = (
    "land: 용도지역×지목 매트릭스·장기추세·단가 분포·거래목록. "
    "셀별 n·단가는 Bundle facts만 인용. 토지 화면의 회귀식·계수·예측은 설명하거나 안내하지 않는다."
)
_RENT_ANCHOR = "- 바람직: 주거 전월세 단가·전환은 임대 목록, 상업 임대료·공실은 상권 모달."
RENT_HIDDEN_GUIDE = (
    "- 임대 화면은 층·면적·연식에 따른 가격 차이(효용지수·회귀분석)를 제공하지 않는다. "
    "그런 질문은 집합부동산(매매)의 단지 분석(층·면적 효용지수·단지 회귀)으로 안내한다. "
    "전월세 화면은 전세가율·전환율·롤링 추이를 제공한다."
)


def product_view(text: str, enabled: frozenset | None = None) -> str:
    """제품 지식 문구를 기능 상태에 맞춘다(여러 번 적용해도 같다)."""
    if not isinstance(text, str) or not text:
        return text
    enabled = current_enabled() if enabled is None else enabled
    if LAND_REGRESSION not in enabled:
        text = text.replace(_LAND_APP_LINE, _LAND_APP_LINE_HIDDEN)
        text = text.replace(_LAND_PACK_LINE, _LAND_PACK_LINE_HIDDEN)
    if RENT_REGRESSION not in enabled and _RENT_ANCHOR in text and RENT_HIDDEN_GUIDE not in text:
        text = text.replace(_RENT_ANCHOR, _RENT_ANCHOR + "\n" + RENT_HIDDEN_GUIDE)
    return text


# ── 저장된 AI 결과 ───────────────────────────────────────────────

def stored_result_visible(payload: Any) -> bool:
    """저장된 AiChatResponse(JSON)를 지금 요청자에게 돌려줘도 되는지(재시도·결과 조회).
    표지 판정은 replay_allowed 하나로 한다. 화면 위치 검사는 그 위의 이중 방어다."""
    if payload is None:
        return True
    if is_admin_now():
        return True
    enabled = current_enabled()
    if not isinstance(payload, dict):
        return False
    ctx = payload.get("answer_context") or {}
    if not isinstance(ctx, dict):
        ctx = {}
    app, panel = str(ctx.get("app") or ""), str(ctx.get("panel") or "")
    if app == "land" and panel in LAND_REGRESSION_PANELS and LAND_REGRESSION not in enabled:
        return False
    if app == "rent" and (ctx.get("화면") == "regression" or ctx.get("detail_tab") == "regression") \
            and RENT_REGRESSION not in enabled:
        return False
    return replay_allowed(payload.get("feature_tags"), has_evidence=True)
