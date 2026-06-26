"""장기추세·매트릭스 칸 추이 — 내러티브 해석."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from app.ai.built_narrative import NarrativeResult, _dedupe, _section


def _fmt_price(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"{float(v):,.0f}"


def _extract_points(facts: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    rows = facts.get("rows")
    if isinstance(rows, list):
        for r in rows:
            if not isinstance(r, dict):
                continue
            price = r.get("mean_unit_price_per_sqm") or r.get("mean") or r.get("median")
            points.append(
                {
                    "label": r.get("chart_label") or str(r.get("year") or r.get("bucket_index") or "?"),
                    "year": r.get("year"),
                    "count": r.get("count") or 0,
                    "price": float(price) if price is not None else None,
                }
            )
        return points

    series = facts.get("series")
    if isinstance(series, list) and series:
        primary = series[0] if isinstance(series[0], dict) else {}
        for p in primary.get("points") or []:
            if not isinstance(p, dict):
                continue
            price = p.get("median") if p.get("median") is not None else p.get("mean")
            points.append(
                {
                    "label": str(p.get("year") or "?"),
                    "year": p.get("year"),
                    "count": p.get("count") or 0,
                    "price": float(price) if price is not None else None,
                    "reference_only": p.get("reference_only"),
                }
            )
    return points


def _price_trend_summary(points: list[dict[str, Any]]) -> tuple[str, str]:
    """(direction, detail) — 상승/하락/혼재."""
    priced = [p for p in points if p.get("price") is not None and not p.get("reference_only")]
    if len(priced) < 2:
        return "불명", "가격 추세를 판단하기에 구간이 부족합니다."

    first, last = priced[0], priced[-1]
    p0, p1 = float(first["price"]), float(last["price"])
    pct = ((p1 - p0) / p0 * 100) if p0 else 0.0
    label0 = first.get("label") or "초기"
    label1 = last.get("label") or "최근"

    if abs(pct) < 3:
        direction = "보합"
        detail = f"{label0}→{label1} 구간 단가 변화는 **약 {pct:+.1f}%**로 큰 추세는 두드러지지 않습니다."
    elif pct > 0:
        direction = "상승"
        detail = f"{label0}→{label1} 구간 **㎡당 단가가 약 {pct:+.1f}%** 변했습니다 (참고)."
    else:
        direction = "하락"
        detail = f"{label0}→{label1} 구간 **㎡당 단가가 약 {pct:+.1f}%** 변했습니다 (참고)."

    return direction, detail


def _volume_summary(points: list[dict[str, Any]]) -> str:
    counts = [int(p.get("count") or 0) for p in points]
    if not counts:
        return "거래량 정보가 없습니다."
    total = sum(counts)
    recent = counts[-1] if counts else 0
    peak = max(counts)
    if recent < peak * 0.5 and peak >= 5:
        return f"최근 구간 거래 **{recent}건**으로, 과거 peak({peak}건) 대비 **감소**한 편입니다."
    if recent >= peak * 0.9 and peak >= 3:
        return f"최근 구간 거래 **{recent}건**으로 활발한 편입니다."
    return f"구간별 거래 **총 {total}건**이며, 최근 구간 **{recent}건**입니다."


def build_trend_narrative(
    *,
    diagnostics: dict[str, Any],
    scope_label: str,
    message: str = "",
) -> NarrativeResult:
    points = diagnostics.get("points") or []
    zone = diagnostics.get("zone_type") or ""
    land = diagnostics.get("land_category") or ""
    cell = f" ({zone} × {land})" if zone and land else ""
    is_long = diagnostics.get("kind") == "long_term"

    direction, trend_detail = _price_trend_summary(points)
    vol = _volume_summary(points)

    summary = (
        f"**{scope_label}**{cell}에서 "
        f"{'장기' if is_long else '선택 기간'} **{direction}** 패턴이 관찰됩니다."
    )

    insight_lines = [
        f"- {trend_detail}",
        f"- {vol}",
    ]
    if is_long:
        insight_lines.append("- 장기추세는 행정구역·용도지역 개편·표본 누락에 민감합니다.")
    else:
        insight_lines.append("- 필터·이상치 정책은 거래목록·회귀 탭과 동일 scope입니다.")

    reasons = [
        f"CH2 **{'장기추세' if is_long else '매트릭스 칸 추이'}** API 집계입니다.",
        trend_detail,
        vol,
        "단가는 **만원/㎡** 기준이며, 개별 필지 가격이 아닙니다.",
    ]

    if "거래량" in message or "volume" in message.lower():
        reasons.insert(1, f"**거래량:** {vol}")

    caveat = (
        f"**{scope_label}** · 선택 필터 내 **통계 패턴**이며, "
        "미래 가격·투자·적정가 판단이 아닙니다."
    )

    followups = _dedupe(
        [
            "거래량 감소 패턴이 보이나요?",
            "변곡점은 언제인가요?" if len(points) >= 4 else "최근 구간만 해석해 주세요.",
            "장기추세와 회귀 결과는 어떻게 다른가요?" if is_long else "연도별 추이를 요약해 주세요.",
            "신뢰구간이 넓은 이유는?",
        ]
    )

    trust: Literal["high", "medium", "low"] = "medium"
    total_n = sum(int(p.get("count") or 0) for p in points)
    if total_n >= 200:
        trust = "high"
    elif total_n < 30:
        trust = "low"

    answer = "\n".join(
        [
            _section("요약", summary),
            _section("💡 AI Insight", "\n\n".join(insight_lines)),
            _section("이유", "\n\n".join(f"- {x}" for x in reasons)),
            _section("사용한 데이터", "✓ CH2 추이 집계\n✓ 구간별 단가·거래량"),
            _section("주의", caveat),
        ]
    )
    return NarrativeResult(
        answer=answer,
        followups=followups,
        trust_level=trust,
        trust_sources=["추이 집계", "구간별 거래량"],
    )


def trend_diagnostics_from_facts(facts: dict[str, Any], *, scope_label: str) -> dict[str, Any]:
    points = _extract_points(facts)
    kind = "long_term" if facts.get("series") else "matrix_yearly"
    return {
        "points": points,
        "point_count": len(points),
        "total_count": sum(int(p.get("count") or 0) for p in points),
        "zone_type": facts.get("zone_type"),
        "land_category": facts.get("land_category"),
        "scope_label": scope_label,
        "kind": kind,
        "year_from": facts.get("year_from"),
        "year_to": facts.get("year_to"),
    }
