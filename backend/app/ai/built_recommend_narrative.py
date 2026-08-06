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
        fitness = conclusion.get("cv_fitness") if isinstance(conclusion.get("cv_fitness"), dict) else {}
        flabel = fitness.get("label_ko") or "—"
        lines.append(f"· CV-MAPE **{float(cv):.1f}%** ({flabel})")

    if stage2.get("ran"):
        local_cv = stage2.get("local_cv_mape")
        pools = stage2.get("pools") or []
        best_twin = None
        if isinstance(pools, list) and pools:
            cvs = [
                float(p["cv_mape"])
                for p in pools
                if isinstance(p, dict) and p.get("cv_mape") is not None
            ]
            best_twin = min(cvs) if cvs else None
        if local_cv is not None and best_twin is not None:
            if best_twin > float(local_cv) + 0.5:
                lines.append(
                    f"· Twin pool 최저 CV-MAPE **{best_twin:.1f}%** — Local({float(local_cv):.1f}%)보다 "
                    "개선되지 않았습니다."
                )
                lines.append(
                    "· **표본 부족**보다 **독립변수 설명력 부족** 가능성이 큽니다."
                )
            elif best_twin < float(local_cv) - 0.5:
                lines.append(
                    f"· Twin pool이 Local 대비 CV-MAPE {float(local_cv) - best_twin:.1f}%p 개선했습니다."
                )
            else:
                lines.append("· Twin pool 추가 후에도 예측력 개선 폭이 제한적입니다.")

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
            "Twin을 써도 안 되면 어떻게 하나요?",
            "주요 계수를 설명해 주세요.",
            "다음에 무엇을 하면 좋나요?",
        ]
    )
    return NarrativeResult(answer=answer, followups=followups)
