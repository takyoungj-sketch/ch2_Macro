"""회귀 예측값 — 내러티브 해석 (PI · CI · 표본)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from app.ai.built_narrative import NarrativeResult, _dedupe, _section


def _fmt_won(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"{float(v):,.0f}"


def build_prediction_narrative(
    *,
    diagnostics: dict[str, Any],
    scope_label: str,
    message: str = "",
) -> NarrativeResult:
    n = diagnostics.get("n") or diagnostics.get("regression_n")
    y_hat = diagnostics.get("y_hat")
    pi_lo = diagnostics.get("pi_lower")
    pi_hi = diagnostics.get("pi_upper")
    ci_lo = diagnostics.get("ci_lower")
    ci_hi = diagnostics.get("ci_upper")
    warnings = diagnostics.get("warnings") or []
    adj = diagnostics.get("adj_r_squared")

    if y_hat is None:
        summary = "예측값이 아직 없습니다. 입력 조건을 채운 뒤 **예측**을 실행해 주세요."
        return NarrativeResult(
            answer=_section("요약", summary),
            followups=["예측구간(PI)과 신뢰구간(CI) 차이는?"],
            trust_level="low",
            trust_sources=[],
        )

    pi_width = float(pi_hi) - float(pi_lo) if pi_hi is not None and pi_lo is not None else None
    rel_width = (pi_width / float(y_hat) * 100) if pi_width and y_hat else None

    summary = (
        f"입력 조건 기준 **예상 거래금액은 약 {_fmt_won(float(y_hat))}만원**입니다 "
        f"({scope_label} · 동일 scope 회귀모형)."
    )

    insight: list[str] = []
    if rel_width is not None:
        if rel_width >= 80:
            insight.append(
                f"- **95% 예측구간(PI)** 폭이 넓습니다(약 ±{rel_width/2:.0f}%). "
                "표본·변수 불확실성이 크거나 입력값이 scope 밖일 수 있습니다."
            )
        elif rel_width >= 40:
            insight.append(
                f"- 예측구간 폭이 **중간** 수준입니다. 개별 거래 변동을 일부 반영합니다."
            )
        else:
            insight.append("- 예측구간이 **상대적으로 좁은** 편입니다(모형·표본 기준).")

    insight.append(
        "- **PI(예측구간)** 는 '이 조건의 **개별 거래 1건**' 범위, "
        "**CI(평균 신뢰구간)** 는 '평균 예측값'의 불확실성입니다."
    )

    if n is not None:
        ni = int(n)
        if ni < 50:
            insight.append(
                f"- 회귀 표본 **{ni}건**으로, PI·계수 불안정성에 **주의**가 필요합니다."
            )
        elif ni >= 200:
            insight.append(f"- 회귀 표본 **{ni}건**으로 예측의 **통계적 기반**은 무난한 편입니다.")

    if adj is not None:
        a = float(adj)
        if a >= 0.7:
            insight.append("- 회귀 **설명력이 높은** 편이나, 예측 ≠ 적정가입니다.")
        elif a < 0.4:
            insight.append("- 회귀 **설명력이 낮아**, 예측구간이 넓어질 수 있습니다.")

    reasons = [
        f"scope **{scope_label}** · OLS 적합 후 입력값으로 산출한 **통계적 예측**입니다.",
        f"예상 금액 **{_fmt_won(float(y_hat))}만원**, "
        f"PI **{_fmt_won(float(pi_lo) if pi_lo else None)}~{_fmt_won(float(pi_hi) if pi_hi else None)}만원**.",
        f"평균 CI **{_fmt_won(float(ci_lo) if ci_lo else None)}~{_fmt_won(float(ci_hi) if ci_hi else None)}만원**.",
    ]
    for w in warnings[:3]:
        reasons.append(f"⚠ {w}")

    if "신뢰" in message or "pi" in message.lower() or "구간" in message:
        reasons.insert(
            1,
            "PI가 넓으면 '비슷한 조건 거래도 금액 편차가 크다'는 뜻일 수 있으며, "
            "n이 작거나 모형 설명력이 낮을 때 흔합니다.",
        )

    caveat = (
        "**개별 물건의 적정가·매매가격이 아닙니다.** "
        "현장 조건·권리·실거래 특수성은 반영되지 않습니다."
    )

    followups = _dedupe(
        [
            "신뢰구간(PI)이 넓은 이유는?",
            "예측구간과 평균 신뢰구간 차이는?",
            "표본수가 적으면 어떤 문제가 생기나요?" if n and int(n) < 100 else "회귀 변수는 무엇을 썼나요?",
            "이 결과를 어떻게 해석하나요?",
        ]
    )

    trust: Literal["high", "medium", "low"] = "medium"
    if n is not None and int(n) >= 200:
        trust = "high"
    elif n is not None and int(n) < 50:
        trust = "low"

    answer = "\n".join(
        [
            _section("요약", summary),
            _section("💡 AI Insight", "\n\n".join(insight)),
            _section("이유", "\n\n".join(f"- {x}" for x in reasons)),
            _section(
                "사용한 데이터",
                "✓ CH2 회귀모형\n✓ 예측·PI/CI 산출",
            ),
            _section("주의", caveat),
        ]
    )
    return NarrativeResult(
        answer=answer,
        followups=followups,
        trust_level=trust,
        trust_sources=["회귀모형", "예측구간(PI/CI)"],
    )


def prediction_diagnostics_from_facts(facts: dict[str, Any], *, scope_label: str) -> dict[str, Any]:
    return {
        "n": facts.get("n"),
        "regression_n": facts.get("regression_n"),
        "adj_r_squared": facts.get("adj_r_squared"),
        "y_hat": facts.get("y_hat"),
        "pi_lower": facts.get("pi_lower"),
        "pi_upper": facts.get("pi_upper"),
        "ci_lower": facts.get("ci_lower"),
        "ci_upper": facts.get("ci_upper"),
        "warnings": facts.get("warnings") or [],
        "scope_label": scope_label,
        "admin_level": facts.get("admin_level"),
    }
