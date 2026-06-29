"""복합 모형 추천·비교 — AI 내러티브 (Facts First, No Recalculation)."""

from __future__ import annotations

from typing import Any, Optional

from app.ai.built_narrative import NarrativeResult, _dedupe

BLOCK_ALIASES: dict[str, tuple[str, ...]] = {
    "gross_area": ("연면적", "gross", "면적"),
    "land_area": ("대지", "land", "대지면적"),
    "building_age": ("연식", "age", "노후", "경과"),
    "road_width": ("도로", "road", "도로조건"),
    "zone_type": ("용도지역", "zone", "용도"),
    "building_use": ("건축물용도", "주택유형", "building_use", "용도"),
    "asset_type": ("유형", "asset", "상가", "공장", "단독"),
    "region_leaf": ("지역", "읍", "면", "동", "region", "loc"),
}


def _match_excluded(message: str, excluded: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    lower = message.lower()
    for ex in excluded:
        if not isinstance(ex, dict):
            continue
        bid = str(ex.get("block_id") or "")
        label = str(ex.get("label") or bid)
        aliases = BLOCK_ALIASES.get(bid, ()) + (bid, label)
        if any(a in message or a.lower() in lower for a in aliases if a):
            return ex
    return None


def _reason_lines(ex: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for r in ex.get("reasons") or []:
        if isinstance(r, dict) and r.get("message"):
            out.append(str(r["message"]))
    return out


def _top_candidate_summary(cands: list[Any], metric: str) -> str:
    if not cands or not isinstance(cands[0], dict):
        return f"{metric} 상위 후보 없음"
    c = cands[0]
    blocks = c.get("blocks") or []
    scale = c.get("response_scale") or "?"
    mape = (c.get("metrics") or {}).get("mape") if isinstance(c.get("metrics"), dict) else c.get("mape")
    blk = ", ".join(str(b) for b in blocks) if blocks else "(절편만)"
    mape_s = f", MAPE={float(mape):.1f}%" if mape is not None else ""
    return f"{metric} 1위: {blk} ({scale}{mape_s})"


def interpret_built_model_selection(
    *,
    diagnostics: dict[str, Any],
    scope_label: str,
    message: str,
) -> NarrativeResult:
    """Group Forward / Best Subset Facts → 설명 (최적·적정가 금지)."""
    mode = str(diagnostics.get("selection_mode") or "suggest")
    n = diagnostics.get("n")
    excluded = diagnostics.get("excluded") or []
    lower = message.lower()

    if any(k in message or k in lower for k in ("추천", "후보", "pareto", "설명형", "예측형", "균형")):
        arch = diagnostics.get("archetype_candidates") or []
        lines = []
        for c in arch[:3]:
            if not isinstance(c, dict):
                continue
            label = c.get("archetype_label") or c.get("archetype")
            conf = c.get("confidence_label") or "?"
            m = c.get("metrics") or {}
            adj = m.get("adj_r_squared")
            mape = m.get("mape")
            adj_s = f"Adj R²={adj:.2f}" if adj is not None else "Adj R²=?"
            mape_s = f"MAPE={mape:.0f}%" if mape is not None else "MAPE=?"
            lines.append(f"· **{label}** ({conf}): {adj_s}, {mape_s}")
        arch_txt = "\n".join(lines) if lines else "후보 없음"
        answer = (
            f"**{scope_label}** (n={n}) **Pareto 추천 후보**입니다.\n\n"
            f"{arch_txt}\n\n"
            "**정답 1개가 아닙니다.**\n"
            "· **가격 예측** → 예측형(MAPE 우선)\n"
            "· **보고서·요인 설명** → 설명형(Adj R² 우선)\n"
            "· **둘 다** → 균형형\n\n"
            "각 후보 `reasons`에 baseline(현재 변수) 대비 trade-off가 있습니다."
        )
        return NarrativeResult(
            answer=answer,
            followups=["추천 신뢰도는?", "MAPE 300%는 왜?", "과적합인가?"],
        )

    if any(k in message or k in lower for k in ("aic", "bic")) and mode == "compare":
        aic1 = _top_candidate_summary(diagnostics.get("candidates_by_aic") or [], "AIC")
        bic1 = _top_candidate_summary(diagnostics.get("candidates_by_bic") or [], "BIC")
        same = aic1.split(": ", 1)[-1] == bic1.split(": ", 1)[-1]
        answer = (
            f"**{scope_label}** (n={n}) 모형 비교입니다.\n\n"
            "**AIC**는 적합 + 변수 수(2×k) 페널티 — **표본 내 설명력·간결함** 균형.\n"
            "**BIC**는 k에 더 큰 페널티 — **더 단순한 모형**을 선호합니다.\n\n"
            f"· {aic1}\n· {bic1}\n"
        )
        if not same:
            answer += (
                "\n⚠ AIC·BIC 1위가 **다를 수 있습니다** — 「정답」이 아니라 **기준 선택**입니다. "
                "해석 목적(예측 MAPE vs 변수 수)에 맞는 탭을 고르세요."
            )
        return NarrativeResult(
            answer=answer,
            followups=_dedupe([
                "MAPE 기준은 어떻게 보나요?",
                "추천과 모형 비교 차이는?",
                "linear vs log는?",
            ]),
            trust_level="high",
            trust_sources=["excluded reasons", "candidate rankings"],
        )

    if any(k in message for k in ("추천", "forward", "Forward", "포워드")):
        steps = diagnostics.get("forward_steps") or []
        rec = diagnostics.get("recommended_blocks") or []
        answer = (
            f"**추천 모델 찾기**(Group Forward)는 빈 모형에서 **블록 단위**로 AIC가 줄어드는 변수만 "
            f"순차 추가합니다. **하나의 정답이 아니라** 1안 + 제외 사유입니다.\n\n"
            f"scope **{scope_label}**, n={n}, 포함: {', '.join(rec) if rec else '(절편만)'}."
        )
        if steps:
            last = steps[-1]
            aic = last.get("aic_after", "?") if isinstance(last, dict) else "?"
            answer += f"\n\nForward {len(steps)}단계 — 마지막 AIC {aic}."
        return NarrativeResult(
            answer=answer,
            followups=["왜 제외된 블록이 있나요?", "AIC와 BIC 차이는?", "이 모형을 채택하면?"],
        )

    if any(k in message for k in ("비교", "best subset", "Best", "서브셋", "subset")):
        answer = (
            "**모형 비교**(Group Best Subset)는 후보 블록의 **부분집합(≤128)** 을 평가해 "
            "AIC·BIC·MAPE 탭별 **상위 3~5개**를 나란히 보여줍니다. "
            "사용자가 **「이 모형으로 분석」** 으로 채택합니다 — CH2가 최적이라고 주장하지 않습니다."
        )
        if mode == "compare":
            answer += (
                f"\n\n{_top_candidate_summary(diagnostics.get('candidates_by_aic') or [], 'AIC')}\n"
                f"{_top_candidate_summary(diagnostics.get('candidates_by_mape') or [], 'MAPE')}"
            )
        return NarrativeResult(
            answer=answer,
            followups=["AIC와 BIC 차이는?", "왜 도로조건이 빠졌나?", "linear vs log는?"],
        )

    if any(k in message for k in ("로그", "linear", "선형", "log", "scale")):
        cmp = diagnostics.get("model_comparison")
        rec = None
        if isinstance(cmp, dict):
            rec = cmp.get("recommended")
        scale = diagnostics.get("response_scale") or rec or "?"
        answer = (
            f"동일 블록 집합에 **linear(금액)** vs **log(금액) semi-log** 를 표본 내 MAPE 등으로 비교합니다. "
            f"현재 선택/권장 scale: **{scale}**. "
            "금액 분포가 오른쪽 꼬리면 log가 잔차를 안정화할 **수 있으나** 해석은 β·단위에 주의하세요."
        )
        return NarrativeResult(
            answer=answer,
            followups=["MAPE 기준은?", "추천 모형과 다른 scale을 쓰면?"],
        )

    ex = _match_excluded(message, excluded if isinstance(excluded, list) else [])
    if ex:
        label = ex.get("label") or ex.get("block_id")
        lines = _reason_lines(ex)
        body = "\n".join(f"· {ln}" for ln in lines) if lines else "· Facts에 상세 사유 없음"
        answer = (
            f"**{label}** 블록은 추천 모형에 **포함되지 않았습니다** (scope {scope_label}).\n\n"
            f"{body}\n\n"
            "Forward는 **AIC 개선이 있는 블록만** 추가합니다. 다른 블록이 같은 단계에서 더 큰 개선을 주면 "
            "이 블록은 제외될 수 있습니다."
        )
        return NarrativeResult(
            answer=answer,
            followups=_dedupe([f"{label}을 넣으면 어떻게 되나?", "다른 제외 블록은?", "직접 수동 분석은?"]),
            focus_var=str(ex.get("block_id")),
        )

    rec = diagnostics.get("recommended_blocks") or []
    answer = (
        f"**{scope_label}** scope 모형 선택 Facts (n={n}).\n"
        f"모드: {'추천(Forward)' if mode == 'suggest' else '모형 비교(Best Subset)'}. "
    )
    if mode == "suggest":
        answer += f"추천 포함 블록: {', '.join(rec) if rec else '(절편만)'}."
        if excluded:
            answer += f" 제외 {len(excluded)}개 — 블록 이름을 질문하면 사유를 설명합니다."
    else:
        answer += (
            f"\n{_top_candidate_summary(diagnostics.get('candidates_by_aic') or [], 'AIC')}\n"
            "탭을 바꿔 기준별 후보를 비교한 뒤 채택하세요."
        )
    answer += "\n\n※ 통계적 모형 선택 참고이며 **적정가·최적 가격이 아닙니다.**"

    return NarrativeResult(
        answer=answer,
        followups=suggested_model_selection_followups(mode),
        trust_level="high" if n and int(n) >= 30 else "medium",
        trust_sources=["forward steps", "excluded reasons", "candidate metrics"],
    )


def suggested_model_selection_followups(mode: str) -> list[str]:
    base = [
        "왜 이 변수 블록이 제외됐나요?",
        "AIC와 BIC 차이는?",
        "linear vs log는 어떻게 고르나요?",
    ]
    if mode == "suggest":
        base.insert(0, "Forward가 멈춘 이유는?")
    else:
        base.insert(0, "추천과 모형 비교 차이는?")
    return _dedupe(base)
