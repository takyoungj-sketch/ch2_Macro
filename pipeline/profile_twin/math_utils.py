from __future__ import annotations

import math


def pass_population_ratio(
    pop_anchor: float | None,
    pop_twin: float | None,
    *,
    lo: float = 0.5,
    hi: float = 1.5,
) -> bool:
    """인구 ±50% Candidate gate. NULL → 스킵(통과)."""
    if pop_anchor is None or pop_twin is None:
        return True
    if pop_anchor <= 0 or pop_twin <= 0:
        return True
    r = pop_twin / pop_anchor
    if lo <= r <= hi:
        return True
    r2 = pop_anchor / pop_twin
    return lo <= r2 <= hi


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return float(max(0.0, min(1.0, dot / (na * nb))))


def log_price_similarity(a: float | None, b: float | None) -> float:
    if a is None or b is None or a <= 0 or b <= 0:
        return 0.0
    return float(math.exp(-abs(math.log(a / b))))
