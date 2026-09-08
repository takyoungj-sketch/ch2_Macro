"""복합 모형 탐색 — AI 진단 내러티브 (R3.5+)."""

from __future__ import annotations

from typing import Any

from app.ai.built_narrative import NarrativeResult, _dedupe

BLOCK_LABELS: dict[str, str] = {
    "gross_area": "연면적",
    "land_area": "대지면적",
    "building_age": "연식",
    "road_width": "도로조건",
    "zone_type": "용도지역",
    "building_use": "건축물용도",
    "asset_type": "유형",
    "region_leaf": "지역(읍·면·동/법정리)",
}


def _block_names(blocks: list[Any]) -> str:
    if not blocks:
        return "(절편만)"
    return ", ".join(BLOCK_LABELS.get(str(b), str(b)) for b in blocks)


def _action_lines(actions: list[Any]) -> list[str]:
    out: list[str] = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        kind = str(a.get("kind") or "")
        label = str(a.get("label_ko") or "")
        if not label:
            continue
        mark = "✓" if kind == "do" else "✗" if kind == "dont" else "○"
        out.append(f"{mark} {label}")
    return out


_COEFF_KO = {"gross_area": "연면적", "land_area": "대지면적", "building_age": "연식"}
_STAB_KO = {"ok": "양호", "warn": "주의", "fail": "불안정"}


def _fmt_cv(v: Any) -> str:
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _twin_experiment_lines(experiments: list[Any]) -> list[str]:
    """접두 실험 로그 — '왜 이 Twin인가'에 쓸 수 있는 한 줄씩."""
    local = next((e for e in experiments if isinstance(e, dict) and e.get("step_id") == "local"), None)
    local_n = local.get("n") if isinstance(local, dict) else None
    local_cv = local.get("search_cv_mape") if isinstance(local, dict) else None
    local_coeffs = local.get("key_coefficients") if isinstance(local, dict) else {}
    if not isinstance(local_coeffs, dict):
        local_coeffs = {}

    picked = next((e for e in experiments if isinstance(e, dict) and e.get("search_picked")), None)
    lines: list[str] = ["", "**Twin 접두 실험 로그**"]
    for e in experiments:
        if not isinstance(e, dict) or e.get("step_id") == "local":
            continue
        label = e.get("label") or e.get("step_id")
        n = e.get("n")
        search = _fmt_cv(e.get("search_cv_mape"))
        delta = e.get("search_cv_delta")
        delta_s = f"{float(delta):+.1f}%p" if isinstance(delta, (int, float)) else "—"
        stab = _STAB_KO.get(str(e.get("stability") or ""), str(e.get("stability") or "—"))
        verdict = e.get("verdict_ko") or ""
        mark = " ←탐색" if e.get("search_picked") else ""
        rec = " ·권고" if e.get("selected") and e.get("prefix_k") else ""
        lines.append(
            f"· {label}{mark}{rec}: n={n}, 탐색 CV {search} (Δ {delta_s}), 안정 {stab}"
            + (f" — {verdict}" if verdict else "")
        )

    if isinstance(picked, dict) and picked.get("prefix_k"):
        n0 = local_n if local_n is not None else "?"
        n1 = picked.get("n")
        cv0 = _fmt_cv(local_cv)
        cv1 = _fmt_cv(picked.get("search_cv_mape"))
        confirm = _fmt_cv(picked.get("confirm_cv_mape"))
        coeff_bits: list[str] = []
        tw_coeffs = picked.get("key_coefficients") if isinstance(picked.get("key_coefficients"), dict) else {}
        for key, ko in _COEFF_KO.items():
            a = local_coeffs.get(key)
            b = tw_coeffs.get(key)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                coeff_bits.append(f"{ko} {a:+.0f} → {b:+.0f}")
        why = (
            f"· 탐색 승자 **{picked.get('label')}**: 분석표본 {n0}건 → {n1}건, "
            f"탐색 CV {cv0} → {cv1}, 확인 CV {confirm}."
        )
        if coeff_bits:
            why += " 핵심 계수: " + ", ".join(coeff_bits) + "."
        notes = picked.get("coeff_notes") or []
        if isinstance(notes, list) and notes:
            why += " " + " ".join(str(n) for n in notes[:3])
        lines.append(why)
    return lines


def interpret_built_recommend(
    *,
    diagnostics: dict[str, Any],
    scope_label: str,
    message: str,
) -> NarrativeResult:
    """모형 탐색 Facts → AI 진단 (적정가·투자 추천 금지)."""
    stage1 = diagnostics.get("stage1") if isinstance(diagnostics.get("stage1"), dict) else {}
    stage2 = diagnostics.get("stage2") if isinstance(diagnostics.get("stage2"), dict) else {}
    conclusion = diagnostics.get("conclusion") if isinstance(diagnostics.get("conclusion"), dict) else {}
    scope = diagnostics.get("analysis_scope") if isinstance(diagnostics.get("analysis_scope"), dict) else {}

    selection_n = stage1.get("selection_n")
    fit_n = stage1.get("fit_n")
    scope_n = scope.get("scope_n_tx")
    sat = stage1.get("satisfaction") if isinstance(stage1.get("satisfaction"), dict) else {}
    cv = sat.get("cv_mape") or conclusion.get("cv_mape")
    primary = stage1.get("primary") if isinstance(stage1.get("primary"), dict) else {}
    blocks = primary.get("blocks") or []

    lines = [f"**AI 진단** · {scope_label}", ""]

    if scope_n is not None and selection_n is not None:
        lines.append(
            f"· 거래 {scope_n}건 → SSOT 탐색 complete-case {selection_n}건"
            + (f" (적합 {fit_n}건)" if fit_n is not None else "")
        )
    if cv is not None:
        pfit = conclusion.get("predictive_fit") if isinstance(conclusion.get("predictive_fit"), dict) else {}
        flabel = pfit.get("label_ko") or "—"
        lines.append(f"· 예측 오차 **{flabel}** · CV-MAPE **{float(cv):.1f}%**")

    if stage2.get("ran"):
        experiments = stage2.get("twin_experiments") or []
        tv = stage2.get("twin_validation") if isinstance(stage2.get("twin_validation"), dict) else {}
        if tv.get("summary_ko"):
            lines.append(f"· Twin: {tv['summary_ko']}")
        if isinstance(experiments, list) and experiments:
            lines.extend(_twin_experiment_lines(experiments))

    if blocks:
        lines.append(f"· 현재 변수: **{_block_names(blocks)}**")

    for b in conclusion.get("bullets") or []:
        if isinstance(b, dict) and b.get("kind") == "negative" and b.get("text"):
            if "Twin" in str(b["text"]) or "설명" in str(b["text"]):
                lines.append(f"· {b['text']}")

    actions = _action_lines(conclusion.get("recommended_actions") or [])
    if actions:
        lines.extend(["", "**권장 활용**", *actions])
    elif conclusion.get("summary_ko"):
        lines.extend(["", str(conclusion["summary_ko"])])

    checklist = diagnostics.get("diagnostics_checklist") or []
    if isinstance(checklist, list) and checklist:
        marks = {"ok": "✓", "warn": "△", "fail": "✗"}
        lines.extend(["", "**진단 체크리스트**"])
        for item in checklist:
            if not isinstance(item, dict):
                continue
            st = str(item.get("status") or "warn")
            label = item.get("label_ko") or item.get("check_id")
            summary = item.get("summary_ko") or ""
            lines.append(f"{marks.get(st, '·')} **{label}** — {summary}")

    coef_lines = diagnostics.get("coefficient_narratives") or []
    if isinstance(coef_lines, list) and coef_lines:
        lines.extend(["", "**계수 해석 (설명형 참고)**"])
        for cn in coef_lines[:5]:
            if isinstance(cn, dict) and cn.get("text_ko"):
                prefix = "★ " if cn.get("is_top_contributor") else "· "
                lines.append(f"{prefix}{cn['text_ko']}")

    lines.append("")
    lines.append(
        "⚠ 회귀는 선택 scope 내 **통계적 패턴** 설명이며 적정가·매매 추천이 아닙니다."
    )

    answer = "\n".join(lines)
    followups = _dedupe(
        [
            "왜 CV-MAPE가 이렇게 높나요?",
            "왜 이 Twin을 붙였나요?",
            "Twin을 써도 안 되면 어떻게 하나요?",
            "주요 계수를 설명해 주세요.",
        ]
    )
    return NarrativeResult(answer=answer, followups=followups)
