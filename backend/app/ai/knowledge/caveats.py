"""Caveat catalog — 조건 → 판단 → 다음 행동. 숫자를 invent하지 않음.

Gate(엔진)가 실행 가능 여부를 정한다. Caveat는 실행된 결과의 신뢰와 다음 경로만 담당한다.
D-056 · docs/CH2_AI_ASSISTANT_EXPANSION_PLAN.md
"""

from __future__ import annotations

from typing import Any

from app.collective.analysis_gates import MIN_COUNT_REGRESSION

# 카탈로그: id → 행동 규칙. 한 단지 실측 n·계수는 넣지 않는다.
CAVEAT_CATALOG: dict[str, dict[str, str]] = {
    "small_sample": {
        "id": "small_sample",
        "condition": "회귀는 실행됐으나 n이 권장(엔진 참고용 경고 또는 권장 n≥30)에 못 미침",
        "judgment": "결과의 안정성에 주의가 필요합니다.",
        "next_action": "인접지역 확대 또는 코호트(통합)로 표본을 늘린 분석을 추가로 비교하는 것이 좋습니다.",
    },
    "type_imbalance": {
        "id": "type_imbalance",
        "condition": "한 유형의 표본이 다른 유형보다 뚜렷이 적음 (Bundle n_by_type)",
        "judgment": "유형 효과 추정이 한쪽에 치우칠 수 있습니다.",
        "next_action": "표본이 적은 유형을 코호트에 더 넣거나, 인접지역을 포함한 통합회귀를 검토하세요.",
    },
    "floor_type_split": {
        "id": "floor_type_split",
        "condition": "엔진 경고: 유형이 층으로 갈림 (같은 층에 두 유형이 없음)",
        "judgment": "유형 더미가 층 구간 차이를 흡수하므로 순수 유형 효과로 읽지 마세요.",
        "next_action": "층 구간을 나눈 해석을 하거나, 유형 효과를 주장하지 말고 한계를 먼저 적으세요.",
    },
    "attrs_instead_of_fe": {
        "id": "attrs_instead_of_fe",
        "condition": "엔진 경고: 단지 속성 투입으로 단지 FE 생략",
        "judgment": "단지 간 차이는 속성으로 설명되며 단지 고정효과와 동시에 읽을 수 없습니다.",
        "next_action": "속성 해석과 FE 해석을 섞지 마세요. 둘 중 하나의 spec만 비교하세요.",
    },
    "kapt_same_pnu": {
        "id": "kapt_same_pnu",
        "condition": "K-apt가 같은 지번 공유(kapt_same_pnu) — 세대수·주차는 단지 전체",
        "judgment": "해당 유형의 재고(세대수·주차)로 쓰면 안 됩니다.",
        "next_action": "세대수·주차 계수를 이 유형 전용 규모로 해석하지 마세요.",
    },
    "high_vif": {
        "id": "high_vif",
        "condition": "VIF 경고가 Bundle에 있음",
        "judgment": "계수가 변수 중복의 영향을 받을 수 있습니다.",
        "next_action": "해당 변수 해석을 제한하고, 변수를 줄인 spec과 비교하세요.",
    },
    "low_adj_r2": {
        "id": "low_adj_r2",
        "condition": "Adj R²가 Bundle에 있고 낮음 (인용만, 임계는 엔진/설명이 우선)",
        "judgment": "선택 변수로 가격 분산을 잘 설명하지 못합니다.",
        "next_action": "변수·층 형식·공간 단위를 바꾼 경로를 검토하세요. 설명력을 숫자로 지어내지 마세요.",
    },
    "below_engine_min": {
        "id": "below_engine_min",
        "condition": "Gate 미달 — 엔진이 회귀를 실행하지 않음",
        "judgment": "이번 조건으로는 회귀를 계산할 수 없습니다.",
        "next_action": "기간·코호트·인접지역을 넓히거나 게이트 안내를 따르세요. History 슬롯은 만들지 않습니다.",
    },
}


def _warn_blob(warnings: list[Any]) -> str:
    return " ".join(str(w) for w in warnings if w is not None)


def _cite_n(n: Any) -> str:
    if n is None:
        return ""
    try:
        return f" (Bundle n={int(n)})"
    except (TypeError, ValueError):
        return f" (Bundle n={n})"


def _as_fired(cid: str, *, extra: str = "") -> dict[str, str]:
    row = dict(CAVEAT_CATALOG[cid])
    if extra:
        row["judgment"] = row["judgment"] + extra
    return row


def fire_caveats(
    *,
    n: Any = None,
    warnings: list[Any] | None = None,
    n_by_type: dict[str, Any] | None = None,
    adj_r_squared: Any = None,
    vif_warning: Any = None,
) -> list[dict[str, str]]:
    """엔진/Bundle 신호만으로 caveat_ids를 켠다. % 증가 같은 숫자는 만들지 않는다."""
    fired: list[dict[str, str]] = []
    seen: set[str] = set()
    blob = _warn_blob(list(warnings or []))
    if vif_warning:
        blob = f"{blob} {vif_warning}"

    def _add(cid: str, extra: str = "") -> None:
        if cid in seen or cid not in CAVEAT_CATALOG:
            return
        seen.add(cid)
        fired.append(_as_fired(cid, extra=extra))

    if "유형이 층으로 갈립니다" in blob:
        _add("floor_type_split")
    if "단지 FE 생략" in blob:
        _add("attrs_instead_of_fe")
    if "kapt_same_pnu" in blob or ("같은 지번" in blob and "K-apt" in blob):
        _add("kapt_same_pnu")
    if "참고용" in blob:
        _add("small_sample", extra=_cite_n(n))
    elif n is not None:
        try:
            ni = int(n)
        except (TypeError, ValueError):
            ni = None
        if ni is not None and ni < MIN_COUNT_REGRESSION:
            _add("small_sample", extra=_cite_n(ni))

    if n_by_type and isinstance(n_by_type, dict):
        counts: list[int] = []
        for v in n_by_type.values():
            try:
                counts.append(int(v))
            except (TypeError, ValueError):
                continue
        if counts and min(counts) == 0:
            _add("type_imbalance", extra=" (한 유형 n=0, Bundle)")
        elif len(counts) >= 2 and min(counts) > 0 and min(counts) * 4 <= max(counts):
            _add("type_imbalance")

    if vif_warning or "VIF" in blob or "다중공선" in blob:
        _add("high_vif")

    if adj_r_squared is not None:
        try:
            if float(adj_r_squared) < 0.2:
                _add("low_adj_r2", extra=f" (Bundle Adj R²={float(adj_r_squared):.3f})")
        except (TypeError, ValueError):
            pass

    return fired


def format_caveats_for_prompt(fired: list[dict[str, str]]) -> str:
    if not fired:
        return ""
    lines = ["[Caveats — 조건→판단→다음 행동. 새 숫자를 만들지 말 것]"]
    for c in fired:
        lines.append(
            f"- {c['id']}: {c['judgment']} 다음: {c['next_action']}"
        )
    lines.append("금지: 신뢰도 N% 증가, 없는 계수, 적정가.")
    return "\n".join(lines)


def caveat_ids(fired: list[dict[str, str]]) -> list[str]:
    return [c["id"] for c in fired if c.get("id")]
