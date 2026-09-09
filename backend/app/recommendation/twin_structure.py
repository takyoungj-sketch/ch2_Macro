"""복합 Stage2 Twin — 지역 구조 순위 · 탐색/확인 CV · 계수 안정.

가격(거래금액·㎡당 단가)은 후보 선정에 쓰지 않는다. 구조 점수는 순서를
고정할 뿐, 유용함의 증명이 아니다. 증명은 탐색 CV 다음의 확인 CV와 안정이다.
"""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.recommendation.cv_fitness import CLEAR_IMPROVE_PP

KEY_COEFF_PREFIXES = ("gross_area", "land_area", "building_age")
STRUCTURE_TOP_K = 5
PRACTICAL_ABS_PP = 0.5
PRACTICAL_REL = 0.02

# land_profile 저장 점수는 단가 유사 40%가 섞여 있어 Jaccard만 파싱한다.
_JACCARD_RE = re.compile(r"Top3 Jaccard\s+([0-9.]+)", re.I)

StabilityStatus = Literal["ok", "warn", "fail"]
SearchBand = Literal["improved", "tie", "worse"]


class TwinExperimentStep(BaseModel):
    """접두 실험 한 줄 — AI·화면 로그 SSOT."""

    step_id: str
    label: str
    prefix_k: int
    region_codes: list[str] = Field(default_factory=list)
    n: int
    search_cv_mape: Optional[float] = None
    confirm_cv_mape: Optional[float] = None
    search_cv_delta: Optional[float] = None
    key_coefficients: dict[str, float] = Field(default_factory=dict)
    coeff_notes: list[str] = Field(default_factory=list)
    stability: StabilityStatus = "ok"
    selected: bool = False
    search_picked: bool = False
    verdict_ko: str = ""


class TwinPrefixDecision(BaseModel):
    decision: str = "local"
    decision_reason: str = ""
    adopt_recommended: bool = False
    search_band: SearchBand = "tie"
    practical_band_pp: float = PRACTICAL_ABS_PP
    selected_step_id: Optional[str] = None
    search_winner_step_id: Optional[str] = None
    confirm_skipped_reason: Optional[str] = None
    region_effect: Optional[str] = None
    steps: list[TwinExperimentStep] = Field(default_factory=list)


def practical_band_pp(local_search_cv: float | None) -> float:
    """실질적 개선 띠 — 채택 문턱이 아니라 무시할 흔들림."""
    if local_search_cv is None:
        return PRACTICAL_ABS_PP
    return round(max(PRACTICAL_ABS_PP, abs(float(local_search_cv)) * PRACTICAL_REL), 2)


def classify_search_delta(delta: float | None, band: float) -> SearchBand:
    if delta is None:
        return "tie"
    if delta >= band:
        return "improved"
    if delta <= -band:
        return "worse"
    return "tie"


def improvement_label(delta: float | None, band: float) -> str:
    """채택 문턱이 아니라 Twin 결과 설명용."""
    kind = classify_search_delta(delta, band)
    if kind == "tie":
        return "사실상 동등"
    if kind == "worse":
        return "악화"
    if delta is not None and delta >= CLEAR_IMPROVE_PP:
        return "뚜렷한 개선"
    return "소폭 개선"


def _jaccard_from_note(note: object) -> float | None:
    if not isinstance(note, str):
        return None
    m = _JACCARD_RE.search(note)
    if not m:
        return None
    try:
        return float(m.group(1))
    except (TypeError, ValueError):
        return None


def structure_score_from_detail(detail: object, fallback: float | None = None) -> float:
    """인구·8대 구성 + 토지 Top3 Jaccard. 아파트·유형 P50·토지 단가는 제외."""
    if not isinstance(detail, dict):
        return float(fallback or 0.0)

    blocks = detail.get("block_scores") if isinstance(detail.get("block_scores"), dict) else {}
    features = detail.get("features") if isinstance(detail.get("features"), dict) else {}

    parts: list[tuple[float, float]] = []
    pop = blocks.get("population")
    if isinstance(pop, (int, float)):
        parts.append((float(pop), 0.25))
    mix = blocks.get("market_mix")
    if isinstance(mix, (int, float)):
        parts.append((float(mix), 0.55))

    land_feat = features.get("land_profile") if isinstance(features.get("land_profile"), dict) else {}
    jaccard = _jaccard_from_note(land_feat.get("note"))
    if jaccard is not None:
        parts.append((jaccard, 0.20))

    if not parts:
        return float(fallback or 0.0)

    wsum = sum(w for _, w in parts)
    score = sum(s * w for s, w in parts) / wsum if wsum else 0.0
    adj = detail.get("represent_market_adjustment")
    if isinstance(adj, (int, float)):
        score += float(adj)
    return float(max(0.0, min(1.0, score)))


def rank_neighbors_by_structure(
    neighbors: list[dict[str, Any]],
    *,
    top_k: int = STRUCTURE_TOP_K,
) -> list[dict[str, Any]]:
    """구조 점수로 재순위. 동점이면 원래 순서 유지. 상위 top_k."""
    scored: list[tuple[int, float, dict[str, Any]]] = []
    for i, row in enumerate(neighbors):
        if not isinstance(row, dict):
            continue
        code = str(row.get("region_code") or row.get("twin_region_code") or "").strip()
        if not code:
            continue
        fallback = row.get("similarity_score")
        fb = float(fallback) if isinstance(fallback, (int, float)) else 0.0
        struct = structure_score_from_detail(row.get("detail_scores"), fallback=fb)
        copy = dict(row)
        copy["region_code"] = code
        copy["structure_score"] = round(struct, 6)
        scored.append((i, struct, copy))
    scored.sort(key=lambda t: (-t[1], t[0]))
    out: list[dict[str, Any]] = []
    for rank, (_, struct, row) in enumerate(scored[: max(0, top_k)], start=1):
        row["structure_rank"] = rank
        out.append(row)
    return out


def key_coefficients_from_fit(fit: object) -> dict[str, float]:
    model = getattr(fit, "model", None)
    if model is None or not hasattr(model, "params"):
        return {}
    out: dict[str, float] = {}
    try:
        index = list(model.params.index)
    except (AttributeError, TypeError):
        return {}
    for name in index:
        key = str(name)
        if key == "const":
            continue
        for prefix in KEY_COEFF_PREFIXES:
            if key == prefix or key.startswith(prefix):
                try:
                    out[key] = round(float(model.params[name]), 4)
                except (TypeError, ValueError):
                    pass
                break
    return out


def coeff_stability(
    local_coeffs: dict[str, float],
    twin_coeffs: dict[str, float],
) -> tuple[StabilityStatus, list[str]]:
    notes: list[str] = []
    flips: list[str] = []
    shared = set(local_coeffs) & set(twin_coeffs)
    for name in sorted(shared):
        a = local_coeffs[name]
        b = twin_coeffs[name]
        if a == 0 and b == 0:
            continue
        if a * b < 0:
            flips.append(f"{name} 부호 반전 ({a:+.3g} → {b:+.3g})")
            continue
        if a != 0 and (abs(b / a) >= 2.0 or abs(b / a) <= 0.5):
            notes.append(f"{name} 크기 변화 ({a:+.3g} → {b:+.3g})")
    if flips:
        return "fail", flips + notes
    if notes:
        return "warn", notes
    if not shared:
        return "ok", ["비교할 공통 핵심 계수 없음"]
    return "ok", []


def region_effect_note(blocks: list[str] | None) -> str:
    if blocks and "region_leaf" in blocks:
        return "지역 효과: 읍면동/리 더미 포함 (Twin을 붙이면 지역마다 절편이 달라질 수 있음)"
    return "지역 효과: 읍면동/리 더미 없음 (공통 기울기)"


def decide_twin_prefix(
    *,
    local_n: int,
    local_search_cv: float | None,
    local_confirm_cv: float | None,
    local_coeffs: dict[str, float],
    local_blocks: list[str],
    prefixes: list[dict[str, Any]],
    confirm_skipped_reason: str | None = None,
) -> TwinPrefixDecision:
    """접두 실험 종합. 탐색 CV로 후보를 고르고, 확인 CV는 채택 권고에만 쓴다."""
    band = practical_band_pp(local_search_cv)
    local_step = TwinExperimentStep(
        step_id="local",
        label="Local",
        prefix_k=0,
        region_codes=[],
        n=local_n,
        search_cv_mape=local_search_cv,
        confirm_cv_mape=local_confirm_cv,
        search_cv_delta=0.0,
        key_coefficients=local_coeffs,
        stability="ok",
        selected=False,
        verdict_ko="기준 (지금 지역만)",
    )
    steps = [local_step]
    eligible: list[TwinExperimentStep] = []

    for row in prefixes:
        search = row.get("search_cv_mape")
        search_f = float(search) if isinstance(search, (int, float)) else None
        delta = None
        if local_search_cv is not None and search_f is not None:
            delta = round(float(local_search_cv) - search_f, 2)
        coeffs = row.get("key_coefficients") if isinstance(row.get("key_coefficients"), dict) else {}
        stab, notes = coeff_stability(local_coeffs, {str(k): float(v) for k, v in coeffs.items() if isinstance(v, (int, float))})
        n = int(row.get("n") or 0)
        if n <= local_n:
            notes = [*notes, "적합 n이 Local보다 늘지 않음"]
            if stab == "ok":
                stab = "warn"
        band_kind = classify_search_delta(delta, band)
        verdict = {
            "improved": "탐색 CV 개선",
            "tie": "탐색 CV 동등(실질적 개선 띠 안)",
            "worse": "탐색 CV 악화",
        }[band_kind]
        if stab == "fail":
            verdict = "계수 불안정 — 채택 제외"
        step = TwinExperimentStep(
            step_id=str(row.get("candidate_id") or f"prefix_{row.get('prefix_k')}"),
            label=str(row.get("label") or ""),
            prefix_k=int(row.get("prefix_k") or 0),
            region_codes=list(row.get("region_codes") or []),
            n=n,
            search_cv_mape=search_f,
            confirm_cv_mape=float(row["confirm_cv_mape"]) if isinstance(row.get("confirm_cv_mape"), (int, float)) else None,
            search_cv_delta=delta,
            key_coefficients={str(k): float(v) for k, v in coeffs.items() if isinstance(v, (int, float))},
            coeff_notes=notes,
            stability=stab,
            selected=False,
            verdict_ko=verdict,
        )
        steps.append(step)
        if stab != "fail" and band_kind == "improved" and n > local_n:
            eligible.append(step)

    decision = TwinPrefixDecision(
        practical_band_pp=band,
        confirm_skipped_reason=confirm_skipped_reason,
        region_effect=region_effect_note(local_blocks),
        steps=steps,
    )

    if not eligible:
        decision.decision = "local"
        decision.decision_reason = (
            "Local 식을 Twin 표본에 다시 적합했으나, 탐색 CV의 실질적 개선과 계수 안정을 "
            "함께 만족하는 접두가 없어 Local을 유지합니다. 표본이 늘었다는 것만으로 "
            "채택하지 않습니다."
        )
        decision.search_band = "tie"
        steps[0].selected = True
        return decision

    winner = min(
        eligible,
        key=lambda s: (s.search_cv_mape is None, s.search_cv_mape if s.search_cv_mape is not None else 1e9),
    )
    for s in steps:
        s.search_picked = s.step_id == winner.step_id
        s.selected = s.step_id == winner.step_id
    decision.search_winner_step_id = winner.step_id
    decision.selected_step_id = winner.step_id
    decision.decision = winner.step_id
    decision.search_band = "improved"
    win_blocks = next((p.get("blocks") for p in prefixes if p.get("candidate_id") == winner.step_id), None)
    if isinstance(win_blocks, list):
        decision.region_effect = region_effect_note(win_blocks)

    confirm_ok = True
    confirm_note = ""
    if confirm_skipped_reason:
        confirm_ok = False
        confirm_note = confirm_skipped_reason
    elif local_confirm_cv is None or winner.confirm_cv_mape is None:
        confirm_ok = False
        confirm_note = "확인 CV를 산출할 연도가 부족합니다."
        decision.confirm_skipped_reason = confirm_note
    else:
        cdelta = round(float(local_confirm_cv) - float(winner.confirm_cv_mape), 2)
        cband = classify_search_delta(cdelta, band)
        if cband == "worse":
            confirm_ok = False
            confirm_note = (
                f"확인 CV는 Local {local_confirm_cv:.2f}% → Twin {winner.confirm_cv_mape:.2f}% "
                f"(Δ {cdelta:+.2f}%p)로 실질적 개선이 아닙니다."
            )
        elif cband == "tie":
            confirm_ok = False
            confirm_note = (
                f"확인 CV 차이가 실질적 개선 띠({band}%p) 안입니다 "
                f"(Local {local_confirm_cv:.2f}% → {winner.confirm_cv_mape:.2f}%)."
            )
        else:
            confirm_note = (
                f"확인 CV Local {local_confirm_cv:.2f}% → Twin {winner.confirm_cv_mape:.2f}% "
                f"(Δ {cdelta:+.2f}%p)."
            )

    if winner.stability == "warn":
        confirm_ok = False
        confirm_note = (confirm_note + " " if confirm_note else "") + "핵심 계수 크기 변화가 커 주의입니다."

    decision.adopt_recommended = confirm_ok
    improve = improvement_label(winner.search_cv_delta, band)
    search_txt = (
        f"탐색 CV Local {local_search_cv:.2f}% → {winner.label} {winner.search_cv_mape:.2f}%"
        f" (Δ {winner.search_cv_delta:+.1f}%p, {improve})"
        if local_search_cv is not None
        and winner.search_cv_mape is not None
        and winner.search_cv_delta is not None
        else (
            f"탐색 CV Local {local_search_cv:.2f}% → {winner.label} {winner.search_cv_mape:.2f}%"
            if local_search_cv is not None and winner.search_cv_mape is not None
            else winner.label
        )
    )
    if confirm_ok:
        decision.decision_reason = (
            f"{search_txt}. {confirm_note} 핵심 계수 방향이 유지되어 "
            "같은 식을 Twin 표본에 재적합한 결과를 권고합니다. "
            "변수 구성은 Local과 같고 계수만 다시 추정합니다. 기본 통계 식은 바꾸지 않습니다."
        )
    else:
        decision.decision = "local"
        decision.adopt_recommended = False
        # 탐색 승자(search_picked)는 유지. selected만 Local로 — 같은 CV를 최종 성능으로 쓰지 않음.
        decision.decision_reason = (
            f"{search_txt} 이나, {confirm_note} Local 유지를 권고합니다. "
            "탐색 CV로 고른 숫자를 최종 성능으로 보지 않습니다."
        )
        for s in steps:
            s.selected = s.step_id == "local"
        decision.selected_step_id = "local"
        for s in steps:
            if s.step_id == winner.step_id:
                s.verdict_ko = (s.verdict_ko + " · 확인 미통과").strip(" ·")
    return decision
