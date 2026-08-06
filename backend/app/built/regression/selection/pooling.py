"""Local vs Twin Pooling 실측 비교 (V2 — hard gate + 복수 pool 조합).

CH2 Macro 철학("후보는 제안하고 Validation이 선택한다")을 API에서 구현한다.
검증(candidate validation)을 통과한 Twin 후보에 두 가지 hard gate를 추가로
적용한 뒤, 통과한 Twin들로 pool 조합(상위 1개 / 상위 3개 / 전체)을 만들어
Local과 **동일 변수블록**으로 함께 적합·비교한다.

Hard gate (CANDIDATE_EVALUATION_DESIGN §3.3):
- 가격수준: anchor 대비 ㎡당 가격 median ratio ∈ [0.5, 2.0] — Twin 유사도(v21)는
  상가 가격 수준을 반영하지 않으므로 별도 검증한다. 표본 부족으로 계산 불가한
  경우는 실패가 아니라 "생략"으로 처리한다.
- 인접성: anchor와 같은 시도이거나 인접 시도(`candidates/adjacency.py`) — Twin
  candidate scope에서 이미 적용되는 규칙의 재검증(이상치 방어).

V1.5(단일 pool, hard gate 없음)의 후속이며, `PoolingEvaluation.candidates`가
Local 포함 N개 후보를 모두 담는다는 점이 이전 버전과의 주요 차이다.
"""

from __future__ import annotations

from app.built.regression.candidates.adjacency import is_adjacent_region
from app.built.regression.candidates.base import CandidateSpec
from app.built.regression.candidates.factory import fetch_candidate_rows, region_price_levels_from_db
from app.built.regression.selection.blocks import BlockId
from app.built.regression.selection.context import SelectionContext, with_complete_case
from app.built.regression.selection.fit import BlockFitResult, fit_best_scale, fit_block_subset
from app.built.schemas import (
    DecisionConfidence,
    PoolingCandidateMetrics,
    PoolingEvaluation,
    RegressionSelectionRequest,
    ResponseScale,
    TwinGateResult,
)

PRICE_RATIO_MIN = 0.5
PRICE_RATIO_MAX = 2.0
_POOL_SIZES = (1, 3)  # + 전체(len(codes))는 항상 포함


def accepted_twin_region_codes(
    accepted: tuple[CandidateSpec, ...],
    anchor_codes: tuple[str, ...],
) -> tuple[str, ...]:
    """검증을 통과한 Twin 후보들의 지역코드 합집합 — anchor 자체는 제외."""
    twin_codes: set[str] = set()
    for spec in accepted:
        if spec.provider_id == "profile_twin":
            twin_codes.update(spec.region_codes)
    twin_codes.difference_update(anchor_codes)
    return tuple(sorted(twin_codes))


def _ordered_twin_rows(
    profile_twin_neighbors: list[dict[str, object]] | None,
    structurally_accepted: set[str],
) -> list[tuple[str, float | None]]:
    """요청에 담긴 순위 순서를 보존하며 구조 검증을 통과한 Twin만 남긴다."""
    out: list[tuple[str, float | None]] = []
    seen: set[str] = set()
    for row in profile_twin_neighbors or []:
        code = str(row.get("region_code") or row.get("twin_region_code") or "").strip()
        if not code or code not in structurally_accepted or code in seen:
            continue
        seen.add(code)
        score = row.get("similarity_score")
        out.append((code, float(score) if isinstance(score, (int, float)) else None))
    return out


def _combine_anchor_price(price_levels: dict[str, float], anchor_codes: tuple[str, ...]) -> float | None:
    values = [price_levels[c] for c in anchor_codes if c in price_levels]
    if not values:
        return None
    return sum(values) / len(values)


def _apply_hard_gates(
    ordered_twins: list[tuple[str, float | None]],
    *,
    anchor_region_codes: tuple[str, ...],
    price_levels: dict[str, float],
) -> list[TwinGateResult]:
    anchor_price = _combine_anchor_price(price_levels, anchor_region_codes)
    gates: list[TwinGateResult] = []
    for rank, (code, similarity) in enumerate(ordered_twins, start=1):
        reasons: list[str] = []
        adjacency_ok = is_adjacent_region(anchor_region_codes, code)
        if not adjacency_ok:
            reasons.append("인접성 gate 실패 — anchor와 같거나 인접한 시도가 아님")

        price_ratio: float | None = None
        price_gate: bool | None = None
        twin_price = price_levels.get(code)
        if anchor_price and twin_price is not None:
            price_ratio = round(twin_price / anchor_price, 3)
            price_gate = PRICE_RATIO_MIN <= price_ratio <= PRICE_RATIO_MAX
            if not price_gate:
                reasons.append(
                    f"가격수준 gate 실패 — anchor 대비 ratio {price_ratio:.2f}"
                    f"(허용 {PRICE_RATIO_MIN}~{PRICE_RATIO_MAX})"
                )
        else:
            reasons.append("가격수준 표본 부족으로 gate 생략")

        accepted = adjacency_ok and price_gate is not False
        gates.append(
            TwinGateResult(
                region_code=code,
                rank=rank,
                similarity_score=similarity,
                price_ratio=price_ratio,
                price_gate=price_gate,
                adjacency_gate=adjacency_ok,
                accepted=accepted,
                reasons=reasons,
            )
        )
    return gates


def _pool_variants(gate_passed_codes: list[str]) -> list[tuple[str, str, tuple[str, ...]]]:
    """gate 통과 Twin(순위순) 목록에서 pool 조합을 만든다 — 크기 중복은 생략."""
    total = len(gate_passed_codes)
    out: list[tuple[str, str, tuple[str, ...]]] = []
    seen_sizes: set[int] = set()
    for size in (*_POOL_SIZES, total):
        n = min(size, total)
        if n <= 0 or n in seen_sizes:
            continue
        seen_sizes.add(n)
        label = "Twin Pooling (전체)" if n == total else f"Twin Pooling (상위 {n}개)"
        out.append((f"twin_pool_n{n}", label, tuple(gate_passed_codes[:n])))
    return out


def _metrics_from_fit(
    candidate_id: str,
    label: str,
    fit: BlockFitResult,
    region_codes: tuple[str, ...],
) -> PoolingCandidateMetrics:
    return PoolingCandidateMetrics(
        candidate_id=candidate_id,
        label=label,
        n=fit.n,
        region_codes=list(region_codes),
        adj_r_squared=fit.adj_r_squared,
        mape=fit.mape,
        cv_mape=fit.cv_mape,
        cv_folds=fit.cv_folds,
        aic=fit.aic,
        bic=fit.bic,
        joint_f_tests=fit.joint_f_tests,
    )


def _fit_pool_variant(
    conn,
    *,
    local_ctx: SelectionContext,
    req: RegressionSelectionRequest,
    blocks: list[BlockId] | list[str],
    variant_id: str,
    label: str,
    anchor_region_codes: tuple[str, ...],
    twin_codes: tuple[str, ...],
    admin_level: str,
    region_col: str | None,
    response_scale: ResponseScale | None = None,
) -> PoolingCandidateMetrics | None:
    pool_codes = tuple(dict.fromkeys((*anchor_region_codes, *twin_codes)))
    pooled_rows = fetch_candidate_rows(
        conn,
        admin_level=admin_level,
        region_codes=pool_codes,
        asset_type=req.asset_type,
        contract_year_from=req.contract_year_from,
        contract_year_to=req.contract_year_to,
        as_of_month=req.as_of_month,
        window_years=req.window_years,
    )
    if pooled_rows.empty:
        return None

    pooled_ctx = SelectionContext(
        df=pooled_rows,
        scope_label=variant_id,
        admin_level=admin_level,
        addr4_city=local_ctx.addr4_city,
        mode=local_ctx.mode,
        unified=local_ctx.unified,
    )
    pooled_ctx = with_complete_case(pooled_ctx, list(blocks), region_col=region_col)
    if pooled_ctx.selection_n < local_ctx.selection_n:
        # pool은 anchor를 포함하므로 정상적으로는 Local 표본 이상이어야 한다.
        return None

    if response_scale is not None:
        pooled_fit = fit_block_subset(
            pooled_ctx.df,
            blocks,
            unified=local_ctx.unified,
            response_scale=response_scale,
            region_col=region_col,
            admin_level=admin_level,
        )
        _cmp = None
    else:
        pooled_fit, _cmp = fit_best_scale(
            pooled_ctx.df,
            blocks,
            unified=local_ctx.unified,
            region_col=region_col,
            admin_level=admin_level,
        )
    if pooled_fit is None:
        return None
    return _metrics_from_fit(variant_id, label, pooled_fit, pool_codes)


def _primary_value(c: PoolingCandidateMetrics) -> float | None:
    return c.cv_mape if c.cv_mape is not None else c.aic


def _rank_candidates(candidates: list[PoolingCandidateMetrics]) -> list[PoolingCandidateMetrics]:
    scored = [(c, v) for c in candidates if (v := _primary_value(c)) is not None]
    scored.sort(key=lambda pair: pair[1])
    return [c for c, _ in scored] or list(candidates[:1])


def _decision_confidence(a: float, b: float) -> DecisionConfidence:
    """1·2위 후보 간 상대 격차 기반 별점 — CANDIDATE_EVALUATION_DESIGN §5.4 1차 구현.

    임계값은 초기 휴리스틱이며 운영 데이터로 재보정할 계획이다 (`[현재]`).
    """
    top, second = sorted((a, b))
    gap = second - top
    rel_gap = gap / top if top else 0.0
    if rel_gap >= 0.30:
        stars, grade = 5, "A"
    elif rel_gap >= 0.15:
        stars, grade = 4, "B"
    elif rel_gap >= 0.07:
        stars, grade = 3, "C"
    elif rel_gap >= 0.02:
        stars, grade = 2, "D"
    else:
        stars, grade = 1, "E"
    return DecisionConfidence(
        stars=stars,
        grade=grade,
        metric_gap_pct=round(rel_gap * 100, 1),
        note=f"1위·2위 후보 간 격차 {rel_gap * 100:.1f}%p 기준 (V1 휴리스틱)",
    )


def _decision_reason(ranked: list[PoolingCandidateMetrics]) -> str:
    winner = ranked[0]
    winner_value = _primary_value(winner)
    metric_name = "CV-MAPE" if winner.cv_mape is not None else "AIC"
    unit = "%" if winner.cv_mape is not None else ""
    if len(ranked) < 2 or winner_value is None:
        return f"{winner.label}만 적합 가능해 선택합니다."
    runner = ranked[1]
    runner_value = _primary_value(runner)
    return (
        f"{metric_name} 기준 {winner.label}({winner_value:.2f}{unit})이 "
        f"{runner.label}({runner_value:.2f}{unit})보다 우수해 선택합니다. "
        f"(Local + Twin Pooling {len(ranked) - 1}개 조합 중 비교)"
    )


def evaluate_pooling_candidates(
    conn,
    *,
    local_ctx: SelectionContext,
    req: RegressionSelectionRequest,
    blocks: list[BlockId] | list[str],
    local_fit: BlockFitResult,
    anchor_region_codes: tuple[str, ...],
    twin_region_codes: tuple[str, ...],
    admin_level: str,
    region_col: str | None,
    fixed_response_scale: ResponseScale | None = None,
) -> PoolingEvaluation:
    """Local과 (hard gate를 통과한) Twin pool 조합들을 실측 비교한다."""
    local_metrics = _metrics_from_fit("local", "현재 지역만 (Local)", local_fit, anchor_region_codes)

    ordered_twins = _ordered_twin_rows(req.profile_twin_neighbors, set(twin_region_codes))
    if not ordered_twins:
        return PoolingEvaluation(
            candidates=[local_metrics],
            decision="local",
            decision_reason="검증을 통과한 Twin 후보가 없어 Local만 사용합니다.",
        )

    twin_codes = tuple(code for code, _ in ordered_twins)
    price_levels = region_price_levels_from_db(
        conn,
        admin_level=admin_level,
        region_codes=tuple(dict.fromkeys((*anchor_region_codes, *twin_codes))),
        asset_type=req.asset_type,
        contract_year_from=req.contract_year_from,
        contract_year_to=req.contract_year_to,
        as_of_month=req.as_of_month,
        window_years=req.window_years,
    )
    gates = _apply_hard_gates(
        ordered_twins,
        anchor_region_codes=anchor_region_codes,
        price_levels=price_levels,
    )
    gate_passed_codes = [g.region_code for g in gates if g.accepted]

    if not gate_passed_codes:
        return PoolingEvaluation(
            candidates=[local_metrics],
            decision="local",
            decision_reason="Twin 후보가 모두 가격수준·인접성 gate에서 제외되어 Local만 사용합니다.",
            twin_gates=gates,
        )

    all_candidates = [local_metrics]
    for variant_id, label, codes in _pool_variants(gate_passed_codes):
        metrics = _fit_pool_variant(
            conn,
            local_ctx=local_ctx,
            req=req,
            blocks=blocks,
            variant_id=variant_id,
            label=label,
            anchor_region_codes=anchor_region_codes,
            twin_codes=codes,
            admin_level=admin_level,
            region_col=region_col,
            response_scale=fixed_response_scale,
        )
        if metrics is not None:
            all_candidates.append(metrics)

    if len(all_candidates) == 1:
        return PoolingEvaluation(
            candidates=all_candidates,
            decision="local",
            decision_reason="gate를 통과한 Twin으로 pool을 적합할 수 없어 Local만 사용합니다.",
            twin_gates=gates,
        )

    ranked = _rank_candidates(all_candidates)
    confidence = None
    ranked_values = [c for c in ranked if _primary_value(c) is not None]
    if len(ranked_values) >= 2:
        confidence = _decision_confidence(
            _primary_value(ranked_values[0]), _primary_value(ranked_values[1])
        )

    return PoolingEvaluation(
        candidates=all_candidates,
        decision=ranked[0].candidate_id,
        decision_reason=_decision_reason(ranked),
        decision_confidence=confidence,
        twin_gates=gates,
    )
