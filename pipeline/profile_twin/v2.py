"""Twin Engine V2 (D-044) — 거리 엔진. V1 마트·카탈로그를 폐기하지 않는다.

제품 Twin 카드를 바꾸지 않는다. 랩에서 비교/풀을 검증한다.
클러스터링 · ML · 자동 가중 학습 없음.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from profile_twin.math_utils import cosine_similarity, log_price_similarity
from profile_twin.vector import MARKET_MIX_TYPES

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_V2_WEIGHT_PATH = CONFIG_DIR / "profile_weight_v2.yaml"

JIMOK_GROUP_KEYS: tuple[str, ...] = (
    "agri",
    "forest",
    "dev",
    "infra",
    "water",
    "special",
    "other",
)

STRUCTURE_TERM_KEYS: tuple[str, ...] = ("market_mix", "jimok_group", "land_top_jaccard")
MARKET_TERM_KEYS: tuple[str, ...] = ("land_price", "apt_p50", "apt_spread", "apt_volume")
ROLES: tuple[str, ...] = ("compare", "pool")


@dataclass(frozen=True)
class V2RoleWeights:
    structure_weight: float
    market_weight: float
    universe: str
    n_hop: int | None = None


@dataclass(frozen=True)
class V2Weights:
    version: str
    population_max_ratio: float
    roles: dict[str, V2RoleWeights]
    structure: dict[str, float]
    market: dict[str, float]
    apt_min_count: int

    def role(self, name: str) -> V2RoleWeights:
        key = (name or "compare").strip().lower()
        if key not in self.roles:
            raise ValueError(f"unknown v2 role: {name}")
        return self.roles[key]


@dataclass
class V2Snapshot:
    region_code: str
    sido_code: str
    sigungu_code: str
    population: float | None
    mix: list[float]
    jimok: list[float]
    land_top_keys: frozenset[str]
    land_price: float | None
    apt_count: float | None
    apt_p50: float | None
    apt_spread: float | None
    apt_price_ok: bool


@dataclass
class V2Term:
    key: str
    layer: str
    score: float
    design_weight: float
    used: bool
    note: str = ""


@dataclass
class V2Score:
    twin_score: float
    confidence: float
    structure_score: float | None
    market_score: float | None
    terms: list[V2Term] = field(default_factory=list)
    used_blocks: list[str] = field(default_factory=list)
    dropped_blocks: list[str] = field(default_factory=list)
    weight_version: str = ""
    role: str = ""


def load_v2_weights(path: Path | None = None) -> V2Weights:
    p = path or DEFAULT_V2_WEIGHT_PATH
    raw: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    gate = raw.get("population_gate") or {}
    roles_raw = raw.get("roles") or {}
    roles: dict[str, V2RoleWeights] = {}
    for name in ROLES:
        block = roles_raw.get(name) or {}
        hop = block.get("n_hop")
        roles[name] = V2RoleWeights(
            structure_weight=float(block.get("structure_weight") or 0.0),
            market_weight=float(block.get("market_weight") or 0.0),
            universe=str(block.get("universe") or ""),
            n_hop=int(hop) if hop is not None else None,
        )
    masks = raw.get("masks") or {}
    return V2Weights(
        version=str(raw.get("version") or "0"),
        population_max_ratio=float(gate.get("max_ratio") or 2.0),
        roles=roles,
        structure={str(k): float(v) for k, v in (raw.get("structure") or {}).items()},
        market={str(k): float(v) for k, v in (raw.get("market") or {}).items()},
        apt_min_count=int(masks.get("apt_min_count") or 15),
    )


def pass_population_log_gate(
    pop_anchor: float | None,
    pop_twin: float | None,
    *,
    max_ratio: float = 2.0,
) -> bool:
    """인구 최대 max_ratio배. NULL·비양수 → 탈락 (V1과 다름)."""
    if pop_anchor is None or pop_twin is None:
        return False
    try:
        fa = float(pop_anchor)
        fb = float(pop_twin)
    except (TypeError, ValueError):
        return False
    if fa <= 0 or fb <= 0 or max_ratio <= 1.0:
        return False
    return abs(math.log(fa) - math.log(fb)) <= math.log(max_ratio) + 1e-12


def _as_float(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return v


def _mix_vector(features: Mapping[str, Any]) -> list[float]:
    yearly = features.get("yearly_mix")
    shares: Mapping[str, Any] = {}
    if isinstance(yearly, dict):
        raw = yearly.get("count_share_by_type")
        if isinstance(raw, dict):
            shares = raw
    return [float(shares.get(t) or 0.0) for t in MARKET_MIX_TYPES]


def _jimok_vector(features: Mapping[str, Any]) -> list[float]:
    raw = features.get("jimok_group_composition")
    comp: Mapping[str, Any] = raw if isinstance(raw, dict) else {}
    out: list[float] = []
    for key in JIMOK_GROUP_KEYS:
        if key in comp:
            out.append(float(comp.get(key) or 0.0))
            continue
        alt = f"jimok_group_share_{key}"
        out.append(float(comp.get(alt) or 0.0))
    return out


def _land_cell_key(obj: Mapping[str, Any]) -> str | None:
    zone = str(obj.get("zone") or "").strip()
    jimok = str(obj.get("jimok_code") or obj.get("jimok") or "").strip()
    if not zone and not jimok:
        return None
    return f"{zone}|{jimok}"


def _land_top_keys(features: Mapping[str, Any]) -> frozenset[str]:
    keys: set[str] = set()
    for i in (1, 2, 3):
        obj = features.get(f"land_top{i}")
        if isinstance(obj, dict):
            ck = _land_cell_key(obj)
            if ck:
                keys.add(ck)
            continue
        zone = str(features.get(f"land_top{i}_zone") or "").strip()
        jimok = str(
            features.get(f"land_top{i}_jimok_code") or features.get(f"land_top{i}_jimok") or ""
        ).strip()
        if zone or jimok:
            keys.add(f"{zone}|{jimok}")
    return frozenset(keys)


def _land_price(features: Mapping[str, Any]) -> float | None:
    top1 = features.get("land_top1")
    if isinstance(top1, dict):
        v = _as_float(top1.get("mean_manwon_per_sqm"))
        if v is not None and v > 0:
            return v
    v = _as_float(features.get("land_top1_mean_manwon_per_sqm"))
    if v is not None and v > 0:
        return v
    return None


def _apt_spread(p25: float | None, p50: float | None, p75: float | None) -> float | None:
    if p25 is None or p50 is None or p75 is None:
        return None
    if p50 <= 0:
        return None
    return (p75 - p25) / p50


def extract_snapshot(
    features: Mapping[str, Any],
    *,
    region_code: str,
    apt_min_count: int = 15,
    sido_code: str | None = None,
    sigungu_code: str | None = None,
) -> V2Snapshot:
    code = str(region_code or "").strip()
    sido = (sido_code or code[:2]).strip()[:2]
    sigungu = (sigungu_code or code[:5]).strip()[:5]
    p25 = _as_float(features.get("apartment_p25"))
    p50 = _as_float(features.get("apartment_median"))
    if p50 is None:
        p50 = _as_float(features.get("apartment_p50"))
    p75 = _as_float(features.get("apartment_p75"))
    apt_count = _as_float(features.get("apartment_count"))
    if apt_count is None:
        yearly = features.get("yearly_mix")
        if isinstance(yearly, dict):
            totals = yearly.get("totals_by_type")
            if isinstance(totals, dict):
                apt = totals.get("아파트")
                if isinstance(apt, dict):
                    apt_count = _as_float(apt.get("count"))
    apt_ok = (
        apt_count is not None
        and apt_count >= apt_min_count
        and p50 is not None
        and p50 > 0
    )
    pop = _as_float(features.get("population"))
    return V2Snapshot(
        region_code=code,
        sido_code=sido,
        sigungu_code=sigungu,
        population=pop if pop is not None and pop > 0 else None,
        mix=_mix_vector(features),
        jimok=_jimok_vector(features),
        land_top_keys=_land_top_keys(features),
        land_price=_land_price(features),
        apt_count=apt_count if apt_count is not None and apt_count > 0 else None,
        apt_p50=p50 if p50 is not None and p50 > 0 else None,
        apt_spread=_apt_spread(p25, p50, p75),
        apt_price_ok=bool(apt_ok),
    )


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float | None:
    if not a or not b:
        return None
    union = a | b
    if not union:
        return None
    return len(a & b) / len(union)


def _ratio_similarity(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    if a < 0 or b < 0:
        return None
    if a == 0 and b == 0:
        return 1.0
    if a == 0 or b == 0:
        return 0.0
    return log_price_similarity(a, b)


def _layer_mean(terms: list[V2Term], layer: str) -> tuple[float | None, float, float]:
    used = [t for t in terms if t.layer == layer and t.used and t.design_weight > 0]
    design = sum(t.design_weight for t in terms if t.layer == layer)
    used_w = sum(t.design_weight for t in used)
    if not used or used_w <= 0:
        return None, used_w, design
    score = sum(t.score * t.design_weight for t in used) / used_w
    return float(max(0.0, min(1.0, score))), used_w, design


def compute_similarity_v2(
    anchor: V2Snapshot,
    twin: V2Snapshot,
    *,
    role: str = "compare",
    weights: V2Weights | None = None,
) -> V2Score:
    wts = weights or load_v2_weights()
    rw = wts.role(role)

    mix = cosine_similarity(anchor.mix, twin.mix)
    jimok = cosine_similarity(anchor.jimok, twin.jimok)
    jaccard = _jaccard(anchor.land_top_keys, twin.land_top_keys)

    land_price = None
    if anchor.land_price and twin.land_price:
        land_price = log_price_similarity(anchor.land_price, twin.land_price)

    apt_p50 = None
    apt_spread = None
    apt_volume = None
    if anchor.apt_price_ok and twin.apt_price_ok:
        apt_p50 = log_price_similarity(anchor.apt_p50, twin.apt_p50)
        apt_spread = _ratio_similarity(anchor.apt_spread, twin.apt_spread)
    if anchor.apt_count and twin.apt_count:
        apt_volume = log_price_similarity(anchor.apt_count, twin.apt_count)

    raw_scores: dict[str, float | None] = {
        "market_mix": mix,
        "jimok_group": jimok,
        "land_top_jaccard": jaccard,
        "land_price": land_price,
        "apt_p50": apt_p50,
        "apt_spread": apt_spread,
        "apt_volume": apt_volume,
    }
    notes = {
        "market_mix": f"8대 구성 cosine {mix:.2f}",
        "jimok_group": f"지목군 7 cosine {jimok:.2f}",
        "land_top_jaccard": (
            f"Top3 Jaccard {jaccard:.2f}" if jaccard is not None else "Top3 셀 없음"
        ),
        "land_price": (
            f"토지 단가 log-sim {land_price:.2f}" if land_price is not None else "토지 단가 없음"
        ),
        "apt_p50": (
            f"아파트 P50 log-sim {apt_p50:.2f}" if apt_p50 is not None else "아파트 P50 마스크 실패"
        ),
        "apt_spread": (
            f"아파트 분포 sim {apt_spread:.2f}" if apt_spread is not None else "아파트 분포 없음"
        ),
        "apt_volume": (
            f"아파트 거래량 log-sim {apt_volume:.2f}"
            if apt_volume is not None
            else "아파트 거래량 없음"
        ),
    }

    terms: list[V2Term] = []
    for key in STRUCTURE_TERM_KEYS:
        dw = float(wts.structure.get(key) or 0.0) * rw.structure_weight
        val = raw_scores[key]
        used = val is not None and dw > 0
        terms.append(
            V2Term(
                key=key,
                layer="structure",
                score=float(val) if val is not None else 0.0,
                design_weight=dw,
                used=used,
                note=notes[key],
            )
        )
    for key in MARKET_TERM_KEYS:
        dw = float(wts.market.get(key) or 0.0) * rw.market_weight
        val = raw_scores[key]
        used = val is not None and dw > 0
        terms.append(
            V2Term(
                key=key,
                layer="market",
                score=float(val) if val is not None else 0.0,
                design_weight=dw,
                used=used,
                note=notes[key],
            )
        )

    structure_score, struct_used_w, struct_design = _layer_mean(terms, "structure")
    market_score, market_used_w, market_design = _layer_mean(terms, "market")

    layer_parts: list[tuple[float, float]] = []
    if structure_score is not None and rw.structure_weight > 0:
        layer_parts.append((structure_score, rw.structure_weight))
    if market_score is not None and rw.market_weight > 0:
        layer_parts.append((market_score, rw.market_weight))

    if layer_parts:
        twin_score = sum(s * w for s, w in layer_parts) / sum(w for _, w in layer_parts)
    else:
        twin_score = 0.0

    design_sum = struct_design + market_design
    used_sum = struct_used_w + market_used_w
    confidence = (used_sum / design_sum) if design_sum > 0 else 0.0

    used_blocks = [t.key for t in terms if t.used]
    dropped_blocks = [t.key for t in terms if not t.used and t.design_weight > 0]

    return V2Score(
        twin_score=float(max(0.0, min(1.0, twin_score))),
        confidence=float(max(0.0, min(1.0, confidence))),
        structure_score=structure_score,
        market_score=market_score,
        terms=terms,
        used_blocks=used_blocks,
        dropped_blocks=dropped_blocks,
        weight_version=wts.version,
        role=role,
    )


def expand_nhop(
    adjacency: Mapping[str, Iterable[str]],
    seeds: Iterable[str],
    n_hop: int,
) -> set[str]:
    """무향 그래프 BFS. n_hop=0 이면 seed만."""
    seen = {str(c).strip() for c in seeds if str(c).strip()}
    frontier = set(seen)
    hops = max(0, int(n_hop))
    for _ in range(hops):
        nxt: set[str] = set()
        for node in frontier:
            for nb in adjacency.get(node, ()):
                c = str(nb).strip()
                if c and c not in seen:
                    seen.add(c)
                    nxt.add(c)
        if not nxt:
            break
        frontier = nxt
    return seen


def in_region_scope(sido_code: str, allowed_sidoes: frozenset[str] | None) -> bool:
    if allowed_sidoes is None:
        return True
    return (sido_code or "").strip()[:2] in allowed_sidoes
