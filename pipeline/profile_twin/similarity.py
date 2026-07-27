from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from profile_twin.catalog import TwinCatalog, load_twin_catalog
from profile_twin.math_utils import cosine_similarity, log_price_similarity
from profile_twin.vector import TwinVector
from profile_twin.weight import TwinWeights, load_twin_weights


@dataclass
class FeatureScoreDetail:
    score: float
    weight: float
    masked: bool
    note: str = ""


@dataclass
class SimilarityResult:
    similarity: float
    score_detail: dict[str, FeatureScoreDetail] = field(default_factory=dict)
    block_scores: dict[str, float] = field(default_factory=dict)
    represent_market_adjustment: float = 0.0
    catalog_version: str = ""
    weight_version: str = ""


def _land_top_block_score(a: TwinVector, b: TwinVector) -> tuple[float, str]:
    keys_a: set[str] = set()
    keys_b: set[str] = set()
    cells_a: dict[str, dict[str, Any]] = {}
    cells_b: dict[str, dict[str, Any]] = {}

    for key in ("land_top1", "land_top2", "land_top3"):
        va = a.values.get(key)
        vb = b.values.get(key)
        if isinstance(va, dict) and va.get("cell_key"):
            ck = str(va["cell_key"])
            keys_a.add(ck)
            cells_a[ck] = va
        if isinstance(vb, dict) and vb.get("cell_key"):
            ck = str(vb["cell_key"])
            keys_b.add(ck)
            cells_b[ck] = vb

    if not keys_a or not keys_b:
        return 0.0, "토지 Top 셀 없음"

    inter = keys_a & keys_b
    union = keys_a | keys_b
    jaccard = len(inter) / len(union) if union else 0.0

    price_sims: list[float] = []
    for ck in inter:
        ma = cells_a[ck].get("mean_manwon_per_sqm")
        mb = cells_b[ck].get("mean_manwon_per_sqm")
        try:
            fa = float(ma) if ma is not None else None
            fb = float(mb) if mb is not None else None
        except (TypeError, ValueError):
            continue
        s = log_price_similarity(fa, fb)
        if s > 0:
            price_sims.append(s)

    price_avg = sum(price_sims) / len(price_sims) if price_sims else 0.0
    score = 0.6 * jaccard + 0.4 * price_avg
    note = f"Top3 Jaccard {jaccard:.2f}, 공통셀 단가 sim {price_avg:.2f}"
    return float(max(0.0, min(1.0, score))), note


def _apartment_block_score(a: TwinVector, b: TwinVector) -> tuple[float, str]:
    specs = ("apt_p25", "apt_p50", "apt_p75")
    sims: list[float] = []
    for key in specs:
        if a.mask(key) <= 0 or b.mask(key) <= 0:
            continue
        va = a.values.get(key)
        vb = b.values.get(key)
        try:
            fa = float(va) if va is not None else None
            fb = float(vb) if vb is not None else None
        except (TypeError, ValueError):
            continue
        s = log_price_similarity(fa, fb)
        if s > 0:
            sims.append(s)
    if not sims:
        return 0.0, "아파트 분위 mask=0 또는 데이터 없음"
    avg = sum(sims) / len(sims)
    return avg, f"아파트 ㎡당 분위 sim {avg:.2f} (n={len(sims)})"


def compute_similarity(
    anchor: TwinVector,
    twin: TwinVector,
    *,
    catalog: TwinCatalog | None = None,
    weights: TwinWeights | None = None,
) -> SimilarityResult:
    cat = catalog or load_twin_catalog()
    wts = weights or load_twin_weights()

    detail: dict[str, FeatureScoreDetail] = {}
    block_scores: dict[str, float] = {}

    # population
    pop_w = wts.blocks.get("population", 0.0)
    pa = anchor.values.get("population")
    pb = twin.values.get("population")
    pop_score = 0.0
    pop_note = "인구 없음"
    if pa is not None and pb is not None:
        try:
            fa, fb = float(pa), float(pb)
            if fa > 0 and fb > 0:
                pop_score = log_price_similarity(fa, fb)
                pop_note = f"인구 log-sim {pop_score:.2f}"
        except (TypeError, ValueError):
            pass
    block_scores["population"] = pop_score
    detail["population"] = FeatureScoreDetail(
        score=pop_score, weight=pop_w, masked=False, note=pop_note
    )

    # market_mix
    mix_w = wts.blocks.get("market_mix", 0.0)
    va = anchor.values.get("market_mix")
    vb = twin.values.get("market_mix")
    mix_score = 0.0
    if isinstance(va, list) and isinstance(vb, list):
        mix_score = cosine_similarity(va, vb)
    block_scores["market_mix"] = mix_score
    detail["market_mix"] = FeatureScoreDetail(
        score=mix_score,
        weight=mix_w,
        masked=False,
        note=f"8대 시장 구성 cosine {mix_score:.2f}",
    )

    # land_profile
    land_w = wts.blocks.get("land_profile", 0.0)
    land_score, land_note = _land_top_block_score(anchor, twin)
    block_scores["land_profile"] = land_score
    detail["land_profile"] = FeatureScoreDetail(
        score=land_score, weight=land_w, masked=False, note=land_note
    )

    # apartment_profile
    apt_w = wts.blocks.get("apartment_profile", 0.0)
    apt_score, apt_note = _apartment_block_score(anchor, twin)
    apt_masked = apt_score <= 0
    block_scores["apartment_profile"] = apt_score
    detail["apartment_profile"] = FeatureScoreDetail(
        score=apt_score, weight=apt_w, masked=apt_masked, note=apt_note
    )

    block_weight_sum = sum(wts.blocks.get(b, 0.0) for b in block_scores)
    if block_weight_sum <= 0:
        block_weight_sum = 1.0

    weighted = sum(
        block_scores[b] * (wts.blocks.get(b, 0.0) / block_weight_sum) for b in block_scores
    )

    # represent_market bonus/penalty
    da = anchor.values.get("represent_market")
    db = twin.values.get("represent_market")
    adj = 0.0
    rm_note = ""
    if da and db:
        if str(da) == str(db):
            adj = wts.represent_market_match_bonus
            rm_note = f"대표시장 일치 ({da}) +{adj:.2f}"
        else:
            adj = -wts.represent_market_mismatch_penalty
            rm_note = f"대표시장 상이 ({da} vs {db}) -{wts.represent_market_mismatch_penalty:.2f}"

    similarity = float(max(0.0, min(1.0, weighted + adj)))
    if rm_note:
        detail["represent_market"] = FeatureScoreDetail(
            score=adj, weight=0.0, masked=False, note=rm_note
        )

    return SimilarityResult(
        similarity=similarity,
        score_detail=detail,
        block_scores=block_scores,
        represent_market_adjustment=adj,
        catalog_version=cat.version,
        weight_version=wts.version,
    )
