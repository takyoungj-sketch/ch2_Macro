"""Pareto archetype picks — 설명형 · 균형형 · 예측형 (정답 1개 ✗)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.built.regression.selection.blocks import BlockId
from app.built.regression.selection.fit import BlockFitResult

ArchetypeKind = Literal["explanation", "balanced", "prediction"]
ConfidenceLevel = Literal["high", "medium", "low"]

ARCHETYPE_LABELS: dict[ArchetypeKind, str] = {
    "explanation": "설명형",
    "balanced": "균형형",
    "prediction": "예측형",
}

PURPOSE_HINTS: dict[ArchetypeKind, str] = {
    "explanation": "보고서 설명·요인 해석",
    "balanced": "설명력과 예측 오차를 함께 고려",
    "prediction": "금액 예측·오차 최소화",
}

CONFIDENCE_LABELS: dict[ConfidenceLevel, str] = {
    "high": "높음",
    "medium": "보통",
    "low": "낮음",
}

ScoredRow = tuple[list[BlockId], BlockFitResult, object | None]


@dataclass(frozen=True)
class ArchetypePick:
    kind: ArchetypeKind
    blocks: list[BlockId]
    fit: BlockFitResult
    model_comparison: object | None
    confidence: ConfidenceLevel
    confidence_label: str
    reasons: list[str]
    purpose_hint: str


def _block_key(blocks: list[BlockId]) -> frozenset[str]:
    return frozenset(blocks)


def _minmax_norm(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _balanced_score(fit: BlockFitResult, pool: list[BlockFitResult]) -> float:
    adjs = [f.adj_r_squared for f in pool if f.adj_r_squared is not None]
    mapes = [f.mape for f in pool if f.mape is not None]
    aics = [f.aic for f in pool]
    params = [f.n_params for f in pool]

    adj = fit.adj_r_squared if fit.adj_r_squared is not None else min(adjs, default=0.0)
    mape = fit.mape if fit.mape is not None else max(mapes, default=999.0)

    adj_n = _minmax_norm(adjs)
    mape_n = _minmax_norm(mapes)
    aic_n = _minmax_norm(aics)
    param_n = _minmax_norm([float(p) for p in params])

    idx_adj = adjs.index(adj) if adj in adjs else 0
    idx_mape = mapes.index(mape) if mape in mapes else 0
    idx_aic = aics.index(fit.aic)
    idx_param = params.index(fit.n_params)

    mape_inv = 1.0 - (mape_n[idx_mape] if mape_n else 0.5)
    aic_inv = 1.0 - (aic_n[idx_aic] if aic_n else 0.5)
    param_inv = 1.0 - (param_n[idx_param] if param_n else 0.5)
    adj_score = adj_n[idx_adj] if adj_n else 0.5

    return 0.38 * adj_score + 0.38 * mape_inv + 0.14 * aic_inv + 0.10 * param_inv


def _vs_baseline_reasons(
    fit: BlockFitResult,
    baseline: BlockFitResult | None,
    *,
    kind: ArchetypeKind,
) -> list[str]:
    out: list[str] = []
    n_blocks = len(fit.blocks)
    if baseline:
        if fit.adj_r_squared is not None and baseline.adj_r_squared is not None:
            d = fit.adj_r_squared - baseline.adj_r_squared
            if d >= 0.02:
                out.append(f"✓ Adj R² +{d:.2f} (현재 대비)")
            elif d <= -0.02:
                out.append(f"△ Adj R² {d:.2f} (현재 대비)")
        if fit.mape is not None and baseline.mape is not None:
            dm = baseline.mape - fit.mape
            if dm >= 5:
                out.append(f"✓ MAPE {dm:.0f}%p 개선")
            elif dm <= -5:
                out.append(f"△ MAPE {abs(dm):.0f}%p 증가")
        if fit.aic < baseline.aic - 0.5:
            out.append(f"✓ AIC {baseline.aic - fit.aic:.1f} 감소")
        elif fit.aic > baseline.aic + 0.5:
            out.append(f"△ AIC +{fit.aic - baseline.aic:.1f}")
        b_blocks = len(baseline.blocks)
        if n_blocks < b_blocks:
            out.append(f"✓ 변수 {b_blocks}→{n_blocks}블록 감소")
        elif n_blocks > b_blocks:
            out.append(f"△ 변수 {b_blocks}→{n_blocks}블록 증가")
    else:
        out.append(f"· 변수 {n_blocks}블록")

    if kind == "explanation" and fit.adj_r_squared is not None:
        out.insert(0, f"✓ Adj R² {fit.adj_r_squared:.2f} (설명력 우선)")
    elif kind == "prediction" and fit.mape is not None:
        out.insert(0, f"✓ MAPE {fit.mape:.1f}% (예측 오차 우선)")
    elif kind == "balanced":
        out.insert(0, "✓ Adj R²·MAPE·AIC 균형 점수 상위")

    return out


def _confidence(
    fit: BlockFitResult,
    baseline: BlockFitResult | None,
    pool: list[BlockFitResult],
    *,
    kind: ArchetypeKind,
) -> ConfidenceLevel:
    n = fit.n
    adjs = [f.adj_r_squared for f in pool if f.adj_r_squared is not None]
    mapes = [f.mape for f in pool if f.mape is not None]
    adj = fit.adj_r_squared
    mape = fit.mape

    if n < 30:
        return "low"

    if kind == "explanation":
        if adj is not None and adjs and adj >= max(adjs) - 0.01:
            if mape is not None and mapes and mape <= sorted(mapes)[len(mapes) // 2]:
                return "high"
            return "medium"
        return "medium"

    if kind == "prediction":
        if mape is not None and mapes and mape <= min(mapes) + 0.01:
            if adj is not None and adjs and adj >= sorted(adjs)[len(adjs) // 4]:
                return "high"
            return "medium"
        return "medium"

    # balanced
    if adj is not None and mape is not None and adjs and mapes:
        adj_ok = adj >= sorted(adjs)[len(adjs) * 2 // 3]
        mape_ok = mape <= sorted(mapes)[len(mapes) // 3]
        if adj_ok and mape_ok:
            return "high"
        if adj_ok or mape_ok:
            return "medium"
    return "medium"


def _pick_unique(
    scored: list[ScoredRow],
    *,
    key,
    exclude: set[frozenset[str]],
) -> ScoredRow | None:
    for row in sorted(scored, key=key):
        k = _block_key(row[0])
        if k not in exclude:
            return row
    return None


def pick_archetypes(
    scored: list[ScoredRow],
    baseline: BlockFitResult | None = None,
) -> list[ArchetypePick]:
    """Best subset scored pool → 설명형 · 균형형 · 예측형 (중복 블록집합 최소화)."""
    if not scored:
        return []

    pool = [f for _, f, _ in scored]
    used: set[frozenset[str]] = set()
    picks: list[ArchetypePick] = []

    def _add(kind: ArchetypeKind, row: ScoredRow | None) -> None:
        if row is None:
            return
        blocks, fit, cmp = row
        k = _block_key(blocks)
        if k in used:
            return
        used.add(k)
        conf = _confidence(fit, baseline, pool, kind=kind)
        reasons = _vs_baseline_reasons(fit, baseline, kind=kind)
        if conf == "low":
            reasons.append(f"△ n={fit.n} — 표본 작음, 신뢰도 낮을 수 있음")
        picks.append(
            ArchetypePick(
                kind=kind,
                blocks=list(blocks),
                fit=fit,
                model_comparison=cmp,
                confidence=conf,
                confidence_label=CONFIDENCE_LABELS[conf],
                reasons=reasons,
                purpose_hint=PURPOSE_HINTS[kind],
            )
        )

    expl = _pick_unique(
        scored,
        key=lambda r: (-(r[1].adj_r_squared or -999), r[1].mape or 999),
        exclude=used,
    )
    _add("explanation", expl)

    pred = _pick_unique(
        [r for r in scored if r[1].mape is not None],
        key=lambda r: (r[1].mape, -(r[1].adj_r_squared or -999)),
        exclude=used,
    )
    _add("prediction", pred)

    bal = _pick_unique(
        scored,
        key=lambda r: (-_balanced_score(r[1], pool), r[1].aic),
        exclude=used,
    )
    _add("balanced", bal)

    # fallback: pool이 작으면 중복 허용해 3칸 채움
    for kind in ("balanced", "prediction", "explanation"):
        if len(picks) >= 3:
            break
        if any(p.kind == kind for p in picks):
            continue
        if kind == "explanation":
            row = _pick_unique(scored, key=lambda r: (-(r[1].adj_r_squared or -999),), exclude=set())
        elif kind == "prediction":
            row = _pick_unique(
                [r for r in scored if r[1].mape is not None],
                key=lambda r: (r[1].mape,),
                exclude=set(),
            )
        else:
            row = _pick_unique(
                scored, key=lambda r: (-_balanced_score(r[1], pool),), exclude=set()
            )
        if row and _block_key(row[0]) not in { _block_key(p.blocks) for p in picks }:
            _add(kind, row)  # type: ignore[arg-type]

    order = {"explanation": 0, "balanced": 1, "prediction": 2}
    picks.sort(key=lambda p: order[p.kind])
    return picks
