"""Twin v8 점수·신뢰도·설명문 — 순수 함수 (DB 없음)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

ALGORITHM_VERSION = 8
CHUNGCHEONG_SIDO = frozenset({"30", "36", "43", "44"})
TOP_N_BY_LEVEL = {
    "sigungu": 10,
    "eupmyeondong": 5,
    "beopjungri": 3,
}

POP_RATIO_MIN = 0.6
POP_RATIO_MAX = 1.7

W_LAND_STRUCT = 30.0
W_LAND_PRICE = 30.0
W_COLLECTIVE = 40.0

LandCell = dict[str, Any]  # count: int, mean: float | None


@dataclass
class RegionProfile:
    region_code: str
    region_level: str
    land_cells: dict[str, LandCell] = field(default_factory=dict)
    land_total_tx: int = 0
    population: int | None = None
    collective: dict[str, float | None] | None = None  # p25, median, p75, count
    collective_source_level: str | None = None  # ri → eupmyeondong roll-up 표시용


@dataclass
class PairScoreResult:
    twin_score: float
    confidence: float
    land_struct_pts: float
    land_price_pts: float
    collective_pts: float
    jaccard: float
    intersection_cells: list[str]
    top_n_anchor: list[str]
    top_n_twin: list[str]
    explanation_ko: str
    detail: dict[str, Any]


def pass_population_ratio(
    pop_anchor: float | None,
    pop_twin: float | None,
    *,
    lo: float = POP_RATIO_MIN,
    hi: float = POP_RATIO_MAX,
) -> bool:
    if pop_anchor is None or pop_twin is None or pop_anchor <= 0 or pop_twin <= 0:
        return False
    r = pop_twin / pop_anchor
    if lo <= r <= hi:
        return True
    r2 = pop_anchor / pop_twin
    return lo <= r2 <= hi


def _top_n_cell_keys(cells: dict[str, LandCell], n: int) -> list[str]:
    ranked = sorted(
        cells.items(),
        key=lambda kv: (-int(kv[1].get("count") or 0), kv[0]),
    )
    return [k for k, _ in ranked[:n]]


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a and not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return float(inter / union) if union else 0.0


def price_ratio_similarity(price_a: float, price_b: float) -> float:
    if price_a <= 0 or price_b <= 0 or not math.isfinite(price_a) or not math.isfinite(price_b):
        return 0.0
    return float(math.exp(-abs(math.log(price_a / price_b))))


def _land_price_score(
    anchor: RegionProfile,
    twin: RegionProfile,
    top_a: set[str],
    top_b: set[str],
) -> tuple[float, list[str]]:
    common = sorted(top_a & top_b)
    if not common:
        return 0.0, common
    sims: list[float] = []
    for ck in common:
        ma = anchor.land_cells.get(ck, {}).get("mean")
        mb = twin.land_cells.get(ck, {}).get("mean")
        if ma is None or mb is None:
            continue
        try:
            fa, fb = float(ma), float(mb)
        except (TypeError, ValueError):
            continue
        sims.append(price_ratio_similarity(fa, fb))
    if not sims:
        return 0.0, common
    return float(sum(sims) / len(sims)), common


def _collective_score(
    anchor: RegionProfile,
    twin: RegionProfile,
) -> tuple[float, dict[str, float | None]]:
    keys = ("p25", "median", "p75")
    if not anchor.collective or not twin.collective:
        return 0.0, {k: None for k in keys}
    sims: list[float] = []
    per_key: dict[str, float | None] = {}
    for k in keys:
        va = anchor.collective.get(k)
        vb = twin.collective.get(k)
        if va is None or vb is None:
            per_key[k] = None
            continue
        try:
            fa, fb = float(va), float(vb)
        except (TypeError, ValueError):
            per_key[k] = None
            continue
        s = price_ratio_similarity(fa, fb)
        sims.append(s)
        per_key[k] = round(s, 4)
    pts = (float(sum(sims) / len(sims)) * W_COLLECTIVE) if sims else 0.0
    return pts, per_key


def compute_confidence(
    *,
    anchor: RegionProfile,
    twin: RegionProfile,
    top_n: int,
    intersection: list[str],
    collective_pts: float,
) -> float:
    """0~100 신뢰도 — 거래량·교집합·집합 데이터 존재."""
    parts: list[float] = []

    # 총 토지 거래 (anchor 기준)
    tx = max(0, int(anchor.land_total_tx))
    parts.append(min(1.0, tx / 200.0) * 35.0)

    # Top-N 셀 거래 합
    top_keys = _top_n_cell_keys(anchor.land_cells, top_n)
    top_tx = sum(int(anchor.land_cells.get(k, {}).get("count") or 0) for k in top_keys)
    parts.append(min(1.0, top_tx / max(top_n * 15, 1)) * 25.0)

    # 교집합 셀 수
    parts.append(min(1.0, len(intersection) / max(top_n, 1)) * 20.0)

    # 집합 데이터
    if anchor.collective and twin.collective:
        ac = int(anchor.collective.get("count") or 0)
        tc = int(twin.collective.get("count") or 0)
        coll_factor = min(1.0, min(ac, tc) / 50.0)
        parts.append(coll_factor * 20.0)
    else:
        parts.append(0.0)

    return round(min(100.0, sum(parts)), 2)


def build_explanation_ko(
    *,
    region_level: str,
    top_n: int,
    top_a: set[str],
    top_b: set[str],
    intersection: list[str],
    jaccard: float,
    land_price_avg_sim: float,
    collective_per_key: dict[str, float | None],
    pop_anchor: int | None,
    pop_twin: int | None,
    twin_score: float,
    collective_source: str | None,
) -> str:
    match_n = len(intersection)
    level_label = {"sigungu": "시군구", "eupmyeondong": "읍·면·동", "beopjungri": "리"}.get(
        region_level, region_level
    )

    price_pct: str | None = None
    if land_price_avg_sim > 0:
        # sim=exp(-|log ratio|) → 대략적 차이 % 추정
        approx_diff = max(0.0, (1.0 - land_price_avg_sim) * 100.0)
        price_pct = f"{approx_diff:.0f}%"

    med_sim = collective_per_key.get("median")
    apt_pct: str | None = None
    if med_sim is not None and med_sim > 0:
        apt_pct = f"{max(0.0, (1.0 - med_sim) * 100):.0f}%"

    pop_pct: str | None = None
    if pop_anchor and pop_twin and pop_anchor > 0:
        pop_pct = f"{abs(pop_twin - pop_anchor) / pop_anchor * 100:.0f}%"

    lines = [
        f"Twin Score {twin_score:.1f}점 ({level_label} · Top{top_n} 토지 셀 기준).",
        f"Top{top_n} 토지 셀 중 {match_n}개 용도×지목이 일치하였으며 (Jaccard {jaccard:.2f}),",
    ]
    if price_pct:
        lines.append(f"공통 셀 평균단가 유사도는 {land_price_avg_sim:.2f} (체감 차이 약 {price_pct}).")
    if apt_pct:
        src = f" (집합: {collective_source} 대표)" if collective_source else ""
        lines.append(f"아파트 중위가격(p50) 유사도 {med_sim:.2f}{src} (체감 차이 약 {apt_pct}).")
    elif collective_source:
        lines.append(f"집합(아파트) 통계는 {collective_source} 읍·면·동 대표값을 사용하였습니다.")
    if pop_pct:
        lines.append(f"인구 규모 차이는 약 {pop_pct}입니다 (인구 필터 0.6~1.7배 적용).")
    return " ".join(lines)


def compute_pair_scores(
    anchor: RegionProfile,
    twin: RegionProfile,
    *,
    top_n: int | None = None,
) -> PairScoreResult | None:
    n = top_n or TOP_N_BY_LEVEL.get(anchor.region_level, 5)
    top_a_list = _top_n_cell_keys(anchor.land_cells, n)
    top_b_list = _top_n_cell_keys(twin.land_cells, n)
    top_a, top_b = set(top_a_list), set(top_b_list)

    jac = jaccard_similarity(top_a, top_b)
    land_struct_pts = jac * W_LAND_STRUCT

    price_sim_avg, intersection = _land_price_score(anchor, twin, top_a, top_b)
    land_price_pts = price_sim_avg * W_LAND_PRICE

    coll_pts, coll_per_key = _collective_score(anchor, twin)

    twin_score = round(land_struct_pts + land_price_pts + coll_pts, 2)
    confidence = compute_confidence(
        anchor=anchor,
        twin=twin,
        top_n=n,
        intersection=intersection,
        collective_pts=coll_pts,
    )

    src = None
    if anchor.region_level == "beopjungri" and anchor.collective_source_level:
        src = anchor.collective_source_level

    explanation = build_explanation_ko(
        region_level=anchor.region_level,
        top_n=n,
        top_a=top_a,
        top_b=top_b,
        intersection=intersection,
        jaccard=jac,
        land_price_avg_sim=price_sim_avg,
        collective_per_key=coll_per_key,
        pop_anchor=anchor.population,
        pop_twin=twin.population,
        twin_score=twin_score,
        collective_source=src,
    )

    detail = {
        "algorithm": "twin_v8",
        "weights": {
            "land_structure": W_LAND_STRUCT,
            "land_price": W_LAND_PRICE,
            "collective": W_COLLECTIVE,
        },
        "land_structure_pts": round(land_struct_pts, 2),
        "land_price_pts": round(land_price_pts, 2),
        "collective_pts": round(coll_pts, 2),
        "jaccard": round(jac, 4),
        "land_price_avg_sim": round(price_sim_avg, 4),
        "collective_sims": coll_per_key,
        "top_n_anchor": top_a_list,
        "top_n_twin": top_b_list,
        "intersection_cells": intersection,
        "pop_anchor": anchor.population,
        "pop_twin": twin.population,
        "collective_source_level": src,
    }

    return PairScoreResult(
        twin_score=twin_score,
        confidence=confidence,
        land_struct_pts=land_struct_pts,
        land_price_pts=land_price_pts,
        collective_pts=coll_pts,
        jaccard=jac,
        intersection_cells=intersection,
        top_n_anchor=top_a_list,
        top_n_twin=top_b_list,
        explanation_ko=explanation,
        detail=detail,
    )
