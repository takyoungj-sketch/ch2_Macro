"""복합 회귀 — 2세대+ 내러티브 해석 (변수 중심 Reasoning Bundle slice)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

VAR_ALIASES: dict[str, tuple[str, ...]] = {
    "building_age": ("연식", "building_age", "age", "경과", "노후"),
    "gross_area": ("연면적", "gross_area", "연면"),
    "land_area": ("대지", "land_area", "대지면적"),
    "road_code": ("도로", "road_code", "road_width", "도로조건"),
}

CONT_LABELS = {
    "gross_area": "연면적",
    "land_area": "대지면적",
    "building_age": "연식",
    "road_code": "도로",
    "road_width_label": "도로조건",
}

CONTINUOUS_KEYS = frozenset(VAR_ALIASES.keys())


@dataclass
class NarrativeResult:
    answer: str
    followups: list[str]
    focus_var: Optional[str] = None
    trust_level: Literal["high", "medium", "low"] = "high"
    trust_sources: list[str] = field(default_factory=list)


def _human_name(raw: str) -> str:
    key = raw.strip()
    if key in CONT_LABELS:
        return CONT_LABELS[key]
    if key.startswith("road_") or "m" in key.lower():
        return key.replace("road_", "도로 ").replace("_", " ")
    if key.startswith("zone_") or "zone" in key:
        return key.replace("zone_", "용도 ").replace("_", " ")
    if key.startswith("use_") or "building_use" in key:
        return key.replace("building_use_", "용도 ").replace("_", " ")
    return key


def _is_categorical(name: str) -> bool:
    n = name.lower()
    return not any(k == name or k in n for k in CONTINUOUS_KEYS) and (
        n.startswith("zone_")
        or n.startswith("use_")
        or n.startswith("road_")
        or "주거" in name
        or "용도" in _human_name(name)
    )


def _match_var_key(text: str, coeff_names: list[str]) -> Optional[str]:
    lower = text.lower()
    for key, aliases in VAR_ALIASES.items():
        if any(a in text or a in lower for a in aliases):
            return key
    for name in coeff_names:
        hn = _human_name(name)
        if hn in text or name in text:
            return name
    return None


def _find_coeff(coeffs: list[dict], focus: str) -> Optional[dict]:
    aliases = VAR_ALIASES.get(focus, (focus,))
    for c in coeffs:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "")
        if name == focus or any(a in name or a in _human_name(name) for a in aliases):
            return c
    for c in coeffs:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "")
        if any(a in name for a in aliases if focus in VAR_ALIASES):
            return c
    return None


def _find_corr(correlations: list[dict], focus: str) -> Optional[dict]:
    aliases = VAR_ALIASES.get(focus, (focus,))
    for s in correlations:
        if not isinstance(s, dict):
            continue
        var = str(s.get("variable") or "")
        label = str(s.get("label") or "")
        if var == focus or any(a in label or a in var for a in aliases):
            return s
    return None


def _find_vif(vif_list: list[dict], focus: str) -> Optional[float]:
    aliases = VAR_ALIASES.get(focus, (focus,))
    for v in vif_list:
        if not isinstance(v, dict):
            continue
        n = str(v.get("name") or "")
        if n == focus or any(a in n for a in aliases):
            val = v.get("vif")
            return float(val) if val is not None else None
    return None


def _max_vif(vif_list: list[dict]) -> float:
    vals = [float(v.get("vif") or 0) for v in vif_list if isinstance(v, dict)]
    return max(vals) if vals else 0.0


def _dedupe(items: list[str], limit: int = 4) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
        if len(out) >= limit:
            break
    return out


def _section(title: str, body: str) -> str:
    return f"### {title}\n\n{body.strip()}\n"


def _evidence_section(*, has_regression: bool, has_vif: bool, has_corr: bool) -> str:
    items: list[str] = []
    if has_regression:
        items.append("✓ 회귀분석 결과")
    if has_vif:
        items.append("✓ 다중공선성(VIF)")
    if has_corr:
        items.append("✓ 변수간 상관관계")
    if not items:
        items.append("✓ CH2 분석 데이터")
    return _section("사용한 데이터", "\n".join(items))


def _sig_label(p: Optional[float]) -> str:
    if p is None:
        return "불명"
    if p < 0.001:
        return "매우 높음"
    if p < 0.01:
        return "높음"
    if p < 0.05:
        return "있음"
    return "낮음"


def _direction_label(estimate: Optional[float]) -> str:
    if estimate is None:
        return "—"
    e = float(estimate)
    if e > 0:
        return "▲"
    if e < 0:
        return "▼"
    return "—"


def _rank_magnitudes(coeffs: list[dict]) -> dict[str, str]:
    sig: list[tuple[str, float]] = []
    for c in coeffs:
        if not isinstance(c, dict):
            continue
        p, est = c.get("p_value"), c.get("estimate")
        if p is None or est is None or float(p) >= 0.05:
            continue
        sig.append((str(c.get("name") or ""), abs(float(est))))
    if not sig:
        return {}
    sig.sort(key=lambda x: x[1], reverse=True)
    labels: dict[str, str] = {}
    n = len(sig)
    for i, (name, ae) in enumerate(sig):
        if n == 1:
            labels[name] = "큼"
        elif i == 0 or ae >= sig[0][1] * 0.85:
            labels[name] = "큼"
        elif i <= max(1, n // 2) or ae >= sig[0][1] * 0.35:
            labels[name] = "중간"
        elif ae >= sig[-1][1] * 0.5:
            labels[name] = "작음"
        else:
            labels[name] = "미세"
    return labels


def _magnitude_for(name: str, estimate: Optional[float], ranks: dict[str, str]) -> str:
    if name in ranks:
        return ranks[name]
    if estimate is None:
        return "—"
    ae = abs(float(estimate))
    if ae >= 500:
        return "큼"
    if ae >= 50:
        return "중간"
    if ae >= 5:
        return "작음"
    return "미세"


def _adj_narrative(adj: Optional[float]) -> str:
    if adj is None:
        return "설명력 지표가 제공되지 않았습니다."
    a = float(adj)
    if a >= 0.8:
        return "설명력이 **높은** 회귀모형입니다."
    if a >= 0.5:
        return "설명력이 **중간** 수준입니다."
    return "설명력이 **낮은** 편으로, 가격 변동 중 상당 부분이 모형 변수로 설명되지 않을 수 있습니다."


def _n_narrative_short(n: Optional[int]) -> str:
    if n is None:
        return ""
    if n >= 1000:
        return "표본수가 **충분**하여 통계적 신뢰성이 높은 편입니다."
    if n >= 200:
        return "표본수가 **무난**한 수준입니다."
    if n >= 50:
        return "표본수가 **다소 적**어 세부 계수 해석에 주의가 필요합니다."
    return "표본수가 **적**어 결과가 불안정할 수 있습니다."


def _n_narrative_detailed(n: Optional[int]) -> str:
    if n is None:
        return "표본 정보가 제공되지 않았습니다."
    ni = int(n)
    if ni >= 1000:
        return (
            f"표본수는 **{ni:,}건**으로 회귀분석에 **충분**합니다. "
            "개별 계수의 방향·크기 모두 비교적 안정적으로 해석할 수 있는 편입니다."
        )
    if ni >= 200:
        return (
            f"표본수는 **{ni:,}건**으로 회귀분석은 **가능**합니다. "
            "주요 변수의 방향성은 참고할 수 있으나, 세부 더미·희귀 범주 계수는 다소 불안정할 수 있습니다."
        )
    if ni >= 50:
        return (
            f"표본수는 **{ni:,}건**으로 회귀분석은 **가능**하지만, "
            "개별 계수 해석에는 **다소 주의**가 필요합니다. "
            "변수의 **방향성**은 참고할 수 있으나, 계수 **크기**를 일반화하기에는 표본이 충분히 크다고 보기 어렵습니다."
        )
    return (
        f"표본수는 **{ni:,}건**으로 **적은** 편입니다. "
        "회귀 자체는 실행되었을 수 있으나, 계수 부호·유의성·크기가 표본 몇 건에 크게 좌우될 수 있습니다. "
        "방향만 참고하고, 크기·인과 해석은 매우 신중히 다루세요."
    )


def _corr_narrative(r: Optional[float]) -> str:
    if r is None:
        return "단순 상관 정보가 없습니다."
    rf = float(r)
    strength = "강한" if abs(rf) >= 0.5 else "중간" if abs(rf) >= 0.3 else "약한"
    direction = "양의" if rf > 0 else "음의"
    return f"단순 상관은 **{strength} {direction}** 관계입니다 (r={rf:.3f})."


def _vif_narrative(vif: Optional[float]) -> str:
    if vif is None:
        return "VIF 정보가 없거나 범주형 더미 변수입니다."
    if vif >= 10:
        return (
            f"다중공선성 지표(VIF={vif:.1f})가 **높아**, "
            "다른 설명변수와 겹친 상태일 수 있습니다. 이 변수 계수만 단독으로 해석하지 마세요."
        )
    if vif >= 5:
        return f"다중공선성(VIF={vif:.1f})은 **참고** 수준이며, 다른 변수와 어느 정도 겹칠 수 있습니다."
    return f"다중공선성(VIF={vif:.1f})은 **낮은** 편으로, 다른 변수와 심하게 겹치지 않은 상태입니다."


def _categorical_note(name: str, estimate: Optional[float]) -> Optional[str]:
    if estimate is None or not _is_categorical(name):
        return None
    label = _human_name(name)
    e = float(estimate)
    if e < 0:
        return f"**{label}**은(는) 기준 범주 대비 거래금액이 **낮아지는 방향**으로 나타났습니다."
    if e > 0:
        return f"**{label}**은(는) 기준 범주 대비 거래금액이 **높아지는 방향**으로 나타났습니다."
    return None


def _sig_coeffs(coeffs: list[dict]) -> list[dict]:
    out = []
    for c in coeffs:
        if not isinstance(c, dict):
            continue
        p = c.get("p_value")
        if p is not None and float(p) < 0.05:
            out.append(c)
    return out


def _build_ai_insight(
    *,
    coeffs: list[dict],
    scope_label: str,
    n: Optional[int],
    adj: Optional[float],
) -> str:
    sig = _sig_coeffs(coeffs)
    if not sig:
        return (
            f"**{scope_label}** scope에서 유의한 변수가 많지 않습니다. "
            "표본·필터·모형 설정을 함께 확인하는 것이 좋습니다."
        )

    ranks = _rank_magnitudes(coeffs)
    lines: list[str] = [f"**{scope_label}** 이번 회귀에서는"]

    def _line_for(keys: tuple[str, ...], label: str) -> Optional[str]:
        for c in sig:
            raw = str(c.get("name") or "")
            if raw in keys or any(k in raw for k in keys):
                est = c.get("estimate")
                if est is None:
                    continue
                d = _direction_label(float(est))
                mag = _magnitude_for(raw, float(est), ranks)
                return f"- **{label}**의 영향력이 {mag}하며, 방향은 **{d}** 입니다."
        return None

    area = _line_for(("gross_area",), "연면적")
    land = _line_for(("land_area",), "대지면적")
    age = _line_for(("building_age", "연식"), "연식")
    road = _line_for(("road_", "road_code", "road_width"), "도로조건")

    for part in (area, land, age):
        if part:
            lines.append(part)

    area_mag = ranks.get("gross_area", "") + ranks.get("land_area", "")
    road_present = any("road" in str(c.get("name") or "").lower() for c in sig)
    if ("큼" in area_mag or "중간" in area_mag) and road_present:
        lines.append("- **건물 규모(연면·대지)** 변수가 **도로조건**보다 영향이 더 크게 나타난 편입니다.")

    if adj is not None and float(adj) < 0.5:
        lines.append("- 설명력(Adj R²)이 낮아, **모형에 담기지 않은 요인**이 가격 변동에 크게 작용할 수 있습니다.")

    if n is not None and int(n) < 100:
        lines.append("- 표본이 많지 않아, 위 패턴은 **방향 참고** 수준으로 보는 것이 안전합니다.")

    if len(lines) <= 1:
        top = sorted(
            sig,
            key=lambda c: abs(float(c.get("estimate") or 0)),
            reverse=True,
        )[:2]
        for c in top:
            nm = _human_name(str(c.get("name") or "?"))
            d = _direction_label(float(c.get("estimate") or 0))
            lines.append(f"- **{nm}**이(가) 두드러진 {d} 방향 패턴을 보입니다.")

    return "\n\n".join(lines)


def _dynamic_followups(
    diagnostics: dict[str, Any],
    *,
    focus_var: Optional[str] = None,
    focus_label: Optional[str] = None,
) -> list[str]:
    n = diagnostics.get("n")
    adj = diagnostics.get("adj_r_squared")
    vif_list = diagnostics.get("vif") or []
    coeffs = diagnostics.get("coefficients") or []
    max_vif = _max_vif(vif_list)
    questions: list[str] = []

    if max_vif >= 7:
        questions.append("왜 다중공선성이 발생했나요?")
    elif max_vif >= 5:
        questions.append("VIF가 높은 변수가 해석에 미치는 영향은?")

    if n is not None and int(n) < 100:
        questions.append("표본수가 적으면 어떤 문제가 생기나요?")

    if adj is not None and float(adj) < 0.5:
        questions.append("설명력이 낮은 이유는?")

    for c in coeffs:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "")
        p, est = c.get("p_value"), c.get("estimate")
        if p is None or est is None or float(p) >= 0.05:
            continue
        if ("연식" in name or "building_age" in name) and float(est) < 0:
            questions.append("왜 연식 계수가 음수인가요?")
            break

    if focus_var and focus_label:
        questions.append(f"{focus_label} 영향은 얼마나 큰가요?")
        questions.append(f"{focus_label} VIF는 괜찮은가요?")

    if not questions:
        questions.extend(
            [
                "왜 연식 계수가 음수인가요?",
                "신뢰구간이 넓은 이유는?",
                "다른 변수와 비교해 주세요.",
            ]
        )

    return _dedupe(questions)


def _trust_for(diagnostics: dict[str, Any]) -> tuple[Literal["high", "medium", "low"], list[str]]:
    sources: list[str] = ["회귀분석 결과"]
    n = diagnostics.get("n")
    if diagnostics.get("vif"):
        sources.append("다중공선성(VIF)")
    if diagnostics.get("correlations") or diagnostics.get("correlation_count"):
        sources.append("변수간 상관관계")

    level: Literal["high", "medium", "low"] = "high"
    if n is not None and int(n) < 50:
        level = "low"
    elif n is not None and int(n) < 200:
        level = "medium"
    adj = diagnostics.get("adj_r_squared")
    if adj is not None and float(adj) < 0.4:
        level = "low" if level == "high" else level
    return level, sources


def _deep_negative_reason(
    *,
    label: str,
    focus: str,
    r: Optional[float],
    p: Optional[float],
    coeffs: list[dict],
    scope_label: str,
) -> Optional[str]:
    if p is None or float(p) >= 0.05:
        return None
    parts = [
        f"이번 회귀에서는 **{label}**의 단순 상관은 크지 않지만, "
        "연면적·대지면적 등 **다른 변수를 통제한 후에도 음의 효과가 유지**되었습니다."
    ]
    if r is not None and abs(float(r)) < 0.3:
        parts.append(
            "이는 단순 scatter만 보면 드러나지 않던 효과가 **다변량 OLS에서 분리**된 결과일 수 있습니다."
        )
    if focus in ("building_age",) or "연식" in label:
        parts.append(
            f"**{scope_label}** scope 특성상 노후 건물 비중, 규모·용도와의 결합 효과 등이 "
            "함께 작용했을 **가능성**이 있습니다."
        )
    parts.append("다만 회귀계수는 **인과관계**를 의미하지 않습니다.")
    return " ".join(parts)


def narrative_for_variable(
    *,
    focus: str,
    diagnostics: dict[str, Any],
    correlations: list[dict],
    scope_label: str,
    message: str,
) -> NarrativeResult:
    coeffs = diagnostics.get("coefficients") or []
    coeff = _find_coeff(coeffs, focus)
    corr = _find_corr(correlations, focus)
    vif_val = _find_vif(diagnostics.get("vif") or [], focus)
    label = _human_name(focus if coeff is None else str(coeff.get("name") or focus))

    est = coeff.get("estimate") if coeff else None
    p = coeff.get("p_value") if coeff else None
    r = corr.get("pearson_r") if corr else None
    n = diagnostics.get("n")

    if est is not None and float(est) < 0:
        summary = (
            f"**{label}**이 증가할수록 다른 조건이 같을 때 거래금액이 **낮아지는 경향**이 나타났습니다."
        )
    elif est is not None and float(est) > 0:
        summary = (
            f"**{label}**이 증가할수록 다른 조건이 같을 때 거래금액이 **높아지는 경향**이 나타났습니다."
        )
    else:
        summary = f"**{label}** 변수에 대한 회귀 결과를 scope 기준으로 해석했습니다."

    insight = ""
    if est is not None and float(est) < 0 and any(k in message for k in ("음수", "왜", "마이너스")):
        deep = _deep_negative_reason(
            label=label,
            focus=focus,
            r=float(r) if r is not None else None,
            p=float(p) if p is not None else None,
            coeffs=coeffs,
            scope_label=scope_label,
        )
        if deep:
            insight = deep

    reasons: list[str] = []
    if p is not None:
        pl = float(p)
        if pl < 0.001:
            reasons.append(f"{label} 계수는 **p<0.001**로 통계적으로 **매우 유의**합니다.")
        elif pl < 0.05:
            reasons.append(f"{label} 계수는 **유의**합니다 (p={pl:.4f}).")
        else:
            reasons.append(
                f"{label} 계수는 **유의하지 않**습니다 (p={pl:.4f}). 부호만으로 해석하지 마세요."
            )

    reasons.append(_corr_narrative(float(r) if r is not None else None))
    if not insight and r is not None and p is not None and abs(float(r)) < 0.3 and float(p) < 0.05:
        reasons.append(
            "단순 상관은 약하지만 **연면적·대지 등 다른 변수를 통제**하면 "
            f"{label} 효과가 분리되어 유의하게 나타날 수 있습니다."
        )
    if insight:
        reasons.insert(0, insight)
    reasons.append(_vif_narrative(vif_val))
    reasons.append(_n_narrative_detailed(n))

    cat_note = _categorical_note(str(coeff.get("name") or focus) if coeff else focus, est)
    if cat_note:
        reasons.append(cat_note)

    caveat = (
        f"이 해석은 **{scope_label}** · 현재 화면 필터·기간 scope에 한정됩니다. "
        "다른 지역·기간에서는 달라질 수 있습니다."
    )

    followups = _dynamic_followups(
        diagnostics,
        focus_var=focus,
        focus_label=label,
    )
    trust_level, trust_sources = _trust_for(diagnostics)

    sections = [_section("요약", summary)]
    if insight and insight not in summary:
        sections.append(_section("💡 AI Insight", insight))
    sections.extend(
        [
            _section("이유", "\n\n".join(f"- {x}" for x in reasons)),
            _evidence_section(
                has_regression=coeff is not None,
                has_vif=vif_val is not None,
                has_corr=r is not None,
            ),
            _section("주의", caveat),
        ]
    )
    return NarrativeResult(
        answer="\n".join(sections),
        followups=followups,
        focus_var=focus,
        trust_level=trust_level,
        trust_sources=trust_sources,
    )


def narrative_overview(
    *,
    diagnostics: dict[str, Any],
    correlations: list[dict],
    scope_label: str,
) -> NarrativeResult:
    n = diagnostics.get("n")
    adj = diagnostics.get("adj_r_squared")
    coeffs = [c for c in (diagnostics.get("coefficients") or []) if isinstance(c, dict)]
    ranks = _rank_magnitudes(coeffs)

    summary = " ".join(filter(None, [_adj_narrative(adj), _n_narrative_short(n)]))
    insight = _build_ai_insight(coeffs=coeffs, scope_label=scope_label, n=n, adj=adj)

    rows: list[tuple[str, str, str, str]] = []
    cat_notes: list[str] = []
    for c in coeffs:
        p = c.get("p_value")
        if p is None or float(p) >= 0.05:
            continue
        raw = str(c.get("name") or "?")
        name = _human_name(raw)
        est = c.get("estimate")
        fe = float(est) if est is not None else None
        rows.append(
            (
                name,
                _direction_label(fe),
                _magnitude_for(raw, fe, ranks),
                _sig_label(float(p)),
            )
        )
        note = _categorical_note(raw, fe)
        if note:
            cat_notes.append(note)
        if len(rows) >= 8:
            break

    table = ""
    if rows:
        table = "| 변수 | 영향 | 크기 | 유의성 |\n| --- | --- | --- | --- |\n"
        table += "\n".join(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows)
        if cat_notes:
            table += "\n\n" + "\n\n".join(f"- {n}" for n in cat_notes[:4])
    else:
        table = "p<0.05 유의 변수가 적거나, 더미·기준 카테고리 위주일 수 있습니다."

    reasons = [
        f"**{scope_label}** scope 기준 **OLS 회귀**입니다.",
        _n_narrative_detailed(n),
        "아래 표는 **다른 변수를 동시에 통제**한 상태에서 유의한 변수만 요약한 것입니다.",
    ]
    if correlations:
        top = sorted(
            [s for s in correlations if isinstance(s, dict) and s.get("pearson_r") is not None],
            key=lambda s: abs(float(s["pearson_r"])),
            reverse=True,
        )[:2]
        for s in top:
            lbl = s.get("label") or s.get("variable")
            reasons.append(f"**{lbl}**: {_corr_narrative(float(s['pearson_r']))}")

    caveat = f"**{scope_label}** scope·선택 필터 내 패턴이며, 인과·적정가·투자 판단이 아닙니다."

    has_vif = bool(diagnostics.get("vif"))
    has_corr = bool(correlations)

    answer = "\n".join(
        [
            _section("요약", summary),
            _section("💡 AI Insight", insight),
            _section("주요 변수", table),
            _section("이유", "\n\n".join(f"- {x}" for x in reasons)),
            _evidence_section(has_regression=True, has_vif=has_vif, has_corr=has_corr),
            _section("주의", caveat),
        ]
    )
    followups = _dynamic_followups(diagnostics)
    trust_level, trust_sources = _trust_for(diagnostics)
    return NarrativeResult(
        answer=answer,
        followups=followups,
        trust_level=trust_level,
        trust_sources=trust_sources,
    )


def build_built_narrative(
    *,
    diagnostics: dict[str, Any],
    scope_label: str,
    message: str,
    correlations: list[dict] | None = None,
) -> NarrativeResult:
    corrs = correlations or diagnostics.get("correlations") or []
    if not isinstance(corrs, list):
        corrs = []
    coeff_names = [str(c.get("name") or "") for c in (diagnostics.get("coefficients") or []) if isinstance(c, dict)]

    focus = _match_var_key(message, coeff_names)
    is_var_q = focus and any(
        k in message for k in ("왜", "음수", "양수", "계수", "영향", "유의", "vif", "상관")
    )

    if focus and is_var_q:
        return narrative_for_variable(
            focus=focus,
            diagnostics=diagnostics,
            correlations=corrs,
            scope_label=scope_label,
            message=message,
        )

    if focus and not is_var_q:
        return narrative_for_variable(
            focus=focus,
            diagnostics=diagnostics,
            correlations=corrs,
            scope_label=scope_label,
            message=message,
        )

    return narrative_overview(
        diagnostics=diagnostics,
        correlations=corrs,
        scope_label=scope_label,
    )
