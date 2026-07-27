"""Twin candidate filtering (D-029 Phase B §12.4.2).

동일 행정레벨 · region_scope · 인구 ±50% (population gate는 builder에서 별도 적용).
"""

from __future__ import annotations

from profile_twin.math_utils import pass_population_ratio
from profile_twin.weight import TwinWeights
from region_scope import candidate_scope_sidoes


def twin_candidate_allowed(
    *,
    region_level: str,
    anchor_meta: dict,
    twin_meta: dict,
    scope: str,
) -> bool:
    """행정레벨·scope 기준 후보 허용 여부 (인구 gate 제외)."""
    if region_level == "beopjungri":
        return str(anchor_meta.get("sigungu_code", "")).strip() == str(
            twin_meta.get("sigungu_code", "")
        ).strip()

    if region_level == "sigungu":
        # 시군구 Twin: 전국 후보 (scope 파라미터는 배치 메타·API용)
        return True

    # eupmyeondong
    anchor_sido = str(anchor_meta.get("sido_code", "")).strip()[:2]
    twin_sido = str(twin_meta.get("sido_code", "")).strip()[:2]
    allowed = candidate_scope_sidoes(anchor_sido, scope)
    if allowed is None:
        return True
    return twin_sido in allowed


def twin_population_allowed(
    pop_anchor,
    pop_twin,
    *,
    weights: TwinWeights,
) -> bool:
    try:
        fa = float(pop_anchor) if pop_anchor is not None else None
        fb = float(pop_twin) if pop_twin is not None else None
    except (TypeError, ValueError):
        fa = fb = None
    return pass_population_ratio(
        fa,
        fb,
        lo=weights.population_ratio_low,
        hi=weights.population_ratio_high,
    )


def effective_scope(region_level: str, scope: str | None) -> str:
    """레벨별 배치·API에 기록할 scope 문자열."""
    if region_level == "beopjungri":
        return "same_sigungu"
    if region_level == "sigungu":
        return "national"
    return scope or "region"
