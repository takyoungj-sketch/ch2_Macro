"""Local vs Twin Pooling 실측 비교 (V2 — hard gate + 복수 pool 조합).

CH2 Macro 철학("후보는 제안하고 Validation이 선택한다")을 API에서 구현한다.
검증(candidate validation)을 통과한 Twin 후보에 두 가지 hard gate를 추가로
적용한 뒤, 통과한 Twin들로 pool 조합(상위 1개 / 상위 3개 / 전체)을 만들어
Local과 **동일 변수블록**으로 함께 적합·비교한다.

Hard gate (D-066):
- 인접성: anchor와 같은 시도이거나 인접 시도 — 우주 제한.
- 거래가격·㎡당 중위는 선정 문이 아님. 붙인 뒤 탐색/확인 CV와 계수 안정으로 검증.

V1.5(단일 pool, hard gate 없음)의 후속이며, `PoolingEvaluation.candidates`가
Local 포함 N개 후보를 모두 담는다는 점이 이전 버전과의 주요 차이다.
"""

from __future__ import annotations

from typing import Literal

from app.built.regression.candidates.adjacency import is_adjacent_region
from app.built.regression.candidates.base import CandidateSpec
from app.built.regression.candidates.factory import fetch_candidate_rows, region_price_levels_from_db
from app.built.regression.region_features import (
    attach_region_features,
    is_region_block,
    normalize_region_feature_tier,
    region_blocks_for_asset,
)
from app.recommendation.built_pool import filter_pool_by_coverage
from app.built.regression.selection.blocks import BlockId, spec_from_blocks
from app.built.regression.selection.context import SelectionContext, with_complete_case
from app.built.regression.selection.fit import BlockFitResult, fit_best_scale, fit_block_subset, rolling_time_cv_split
from app.built.regression.selection.best_subset import run_group_best_subset
from app.built.schemas import (
    DecisionConfidence,
    PoolingCandidateMetrics,
    PoolingEvaluation,
    RegressionSelectionRequest,
    ResponseScale,
    TwinGateResult,
)
from app.recommendation.twin_structure import key_coefficients_from_fit

PRICE_RATIO_MIN = 0.5
PRICE_RATIO_MAX = 2.0
PoolingMode = Literal["diagnose", "optimize"]


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
                    f"㎡당 중위 비율 {price_ratio:.2f} (참고, 선정 제외 아님)"
                )
        else:
            reasons.append("가격수준 표본 부족으로 gate 생략")

        # 거래가격·㎡당 중위는 후보 선정 문이 아니다 (D-066). 인접만 하드 컷.
        if price_ratio is not None:
            reasons.append("가격 비율은 참고만 — 선정 기준으로 쓰지 않음")
        accepted = adjacency_ok
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


def research_full_twin_pool(
    conn,
    *,
    local_ctx: SelectionContext,
    req: RegressionSelectionRequest,
    search_pool: list[BlockId] | list[str],
    anchor_region_codes: tuple[str, ...],
    twin_region_codes: tuple[str, ...],
    admin_level: str,
    region_col: str | None,
) -> PoolingCandidateMetrics | None:
    """Local+통과 Twin 1위 표본에서 Stage1과 같은 예측형 풀로 식을 다시 고른다."""
    _gates, passed = filter_twins_by_hard_gates(
        conn,
        req=req,
        anchor_region_codes=anchor_region_codes,
        twin_region_codes=twin_region_codes,
        admin_level=admin_level,
    )
    if not passed:
        return None
    rank1 = (passed[0],)
    return _research_pool_variant(
        conn,
        local_ctx=local_ctx,
        req=req,
        search_pool=search_pool,
        variant_id="twin_research",
        label="Local + Twin 1위 · 재탐색",
        anchor_region_codes=anchor_region_codes,
        twin_codes=rank1,
        admin_level=admin_level,
        region_col=region_col,
        prefix_k=1,
    )


def filter_twins_by_hard_gates(
    conn,
    *,
    req: RegressionSelectionRequest,
    anchor_region_codes: tuple[str, ...],
    twin_region_codes: tuple[str, ...],
    admin_level: str,
) -> tuple[list[TwinGateResult], list[str]]:
    """Twin hard gate만 적용 — 통과 region_code 목록(순위 유지)을 반환한다."""
    ordered_twins = _ordered_twin_rows(req.profile_twin_neighbors, set(twin_region_codes))
    if not ordered_twins:
        return [], []

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
        include_partial=bool(getattr(req, "include_partial", False)),
    )
    gates = _apply_hard_gates(
        ordered_twins,
        anchor_region_codes=anchor_region_codes,
        price_levels=price_levels,
    )
    passed = [g.region_code for g in gates if g.accepted]
    return gates, passed


def _pool_variants(gate_passed_codes: list[str]) -> list[tuple[str, str, tuple[str, ...], int]]:
    """구조 순위 접두만 실험 — 1위, 1·2위, … (조합 검색 없음)."""
    out: list[tuple[str, str, tuple[str, ...], int]] = []
    for k in range(1, len(gate_passed_codes) + 1):
        codes = tuple(gate_passed_codes[:k])
        if k == 1:
            label = "Local + Twin 1위"
        else:
            nums = "·".join(str(i) for i in range(1, k + 1))
            label = f"Local + Twin {nums}위"
        out.append((f"twin_prefix_k{k}", label, codes, k))
    return out


def _metrics_from_fit(
    candidate_id: str,
    label: str,
    fit: BlockFitResult,
    region_codes: tuple[str, ...],
    *,
    blocks: list[BlockId] | list[str] | None = None,
    prefix_k: int = 0,
) -> PoolingCandidateMetrics:
    block_list = list(blocks) if blocks is not None else []
    return PoolingCandidateMetrics(
        candidate_id=candidate_id,
        label=label,
        n=fit.n,
        region_codes=list(region_codes),
        adj_r_squared=fit.adj_r_squared,
        mape=fit.mape,
        cv_mape=fit.cv_mape,
        cv_folds=fit.cv_folds,
        confirm_cv_mape=fit.confirm_cv_mape,
        confirm_cv_folds=fit.confirm_cv_folds,
        aic=fit.aic,
        bic=fit.bic,
        joint_f_tests=fit.joint_f_tests,
        blocks=block_list,
        response_scale=fit.response_scale,
        prefix_k=prefix_k,
        key_coefficients=key_coefficients_from_fit(fit),
    )


def _attach_search_confirm_cv(
    metrics: PoolingCandidateMetrics,
    df,
    *,
    unified: bool,
    region_col: str | None,
) -> PoolingCandidateMetrics:
    if not metrics.blocks or metrics.response_scale is None:
        return metrics
    spec = spec_from_blocks(metrics.blocks)
    search, s_folds, confirm, c_folds, _skip = rolling_time_cv_split(
        df,
        spec,
        unified=unified,
        response_scale=metrics.response_scale,
        region_col=region_col,
    )
    if search is not None:
        metrics.cv_mape = search
        metrics.cv_folds = s_folds
    metrics.confirm_cv_mape = confirm
    metrics.confirm_cv_folds = c_folds
    return metrics


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
    prefix_k: int = 0,
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
        include_partial=bool(getattr(req, "include_partial", False)),
        enrich=bool(getattr(req, "enrich", False)),
    )
    if pooled_rows.empty:
        return None

    if getattr(req, "include_region_features", False) or any(is_region_block(str(b)) for b in blocks):
        pv = (req.profile_version or "v2.1-national").strip() or "v2.1-national"
        wy = int(req.profile_window_years or req.window_years or 3)
        tier = normalize_region_feature_tier(getattr(req, "region_feature_tier", None))
        pooled_rows = attach_region_features(
            pooled_rows,
            profile_version=pv,
            window_years=wy,
            block_ids=region_blocks_for_asset(req.asset_type, tier=tier),
        )

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
    metrics = _metrics_from_fit(
        variant_id,
        label,
        pooled_fit,
        pool_codes,
        blocks=blocks,
        prefix_k=prefix_k,
    )
    return _attach_search_confirm_cv(
        metrics,
        pooled_ctx.df,
        unified=local_ctx.unified,
        region_col=region_col,
    )


def _research_pool_variant(
    conn,
    *,
    local_ctx: SelectionContext,
    req: RegressionSelectionRequest,
    search_pool: list[BlockId] | list[str],
    variant_id: str,
    label: str,
    anchor_region_codes: tuple[str, ...],
    twin_codes: tuple[str, ...],
    admin_level: str,
    region_col: str | None,
    prefix_k: int = 0,
) -> PoolingCandidateMetrics | None:
    """확장 표본 위에서 stage1과 동일 SSOT 풀로 best-subset 재탐색."""
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
        include_partial=bool(getattr(req, "include_partial", False)),
        enrich=bool(getattr(req, "enrich", False)),
    )
    if pooled_rows.empty:
        return None

    if getattr(req, "include_region_features", False) or any(
        is_region_block(str(b)) for b in search_pool
    ):
        pv = (req.profile_version or "v2.1-national").strip() or "v2.1-national"
        wy = int(req.profile_window_years or req.window_years or 3)
        tier = normalize_region_feature_tier(getattr(req, "region_feature_tier", None))
        pooled_rows = attach_region_features(
            pooled_rows,
            profile_version=pv,
            window_years=wy,
            block_ids=region_blocks_for_asset(req.asset_type, tier=tier),
        )

    probe_ctx = SelectionContext(
        df=pooled_rows,
        scope_label=variant_id,
        admin_level=admin_level,
        addr4_city=local_ctx.addr4_city,
        mode=local_ctx.mode,
        unified=local_ctx.unified,
    )
    pool_blocks, _ = filter_pool_by_coverage(probe_ctx, list(search_pool))  # type: ignore[arg-type]
    if not pool_blocks:
        return None
    pool_spec = spec_from_blocks(pool_blocks)
    pooled_ctx = SelectionContext(
        df=pooled_rows,
        scope_label=variant_id,
        admin_level=admin_level,
        addr4_city=local_ctx.addr4_city,
        mode=local_ctx.mode,
        unified=local_ctx.unified,
    )
    pooled_ctx = with_complete_case(pooled_ctx, pool_blocks, region_col=region_col)
    if pooled_ctx.selection_n < local_ctx.selection_n:
        return None

    req_for_fit = req.model_copy(update={"variables": pool_spec})
    result = run_group_best_subset(pooled_ctx, req_for_fit, pool_blocks)
    if result is None:
        return None
    from app.recommendation.ranks import pick_primary_predictive

    primary = pick_primary_predictive(result.by_cv_mape, result.by_mape, result.by_aic)
    if primary is None:
        return None
    metrics = _metrics_from_fit(
        variant_id,
        label,
        primary.fit,
        pool_codes,
        blocks=list(primary.blocks),
        prefix_k=prefix_k,
    )
    return _attach_search_confirm_cv(
        metrics,
        pooled_ctx.df,
        unified=local_ctx.unified,
        region_col=region_col,
    )


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
    mode: PoolingMode = "diagnose",
    twin_blocks: list[BlockId] | list[str] | None = None,
    twin_region_col: str | None = None,
) -> PoolingEvaluation:
    """Local과 Twin 접두 표본을 실측 비교한다.

    mode=diagnose (제품 Stage2): Twin 적합은 twin_blocks(없으면 Local 식)와 척도를
    고정하고 Twin n만 보탠다. Local 후보는 local_fit 그대로.
    mode=optimize: 확장 표본에서 best-subset 재탐색 — 관리자 Lab 전용.
    """
    frozen_blocks = list(local_fit.blocks or blocks)
    diagnose_blocks = list(twin_blocks) if twin_blocks is not None else frozen_blocks
    diagnose_region_col = region_col if twin_region_col is None else twin_region_col
    local_metrics = _metrics_from_fit(
        "local",
        "현재 지역만 (Local)",
        local_fit,
        anchor_region_codes,
        blocks=frozen_blocks,
        prefix_k=0,
    )
    local_metrics = _attach_search_confirm_cv(
        local_metrics,
        local_ctx.df,
        unified=local_ctx.unified,
        region_col=region_col,
    )

    gates, gate_passed_codes = filter_twins_by_hard_gates(
        conn,
        req=req,
        anchor_region_codes=anchor_region_codes,
        twin_region_codes=twin_region_codes,
        admin_level=admin_level,
    )
    if not twin_region_codes or not gates:
        return PoolingEvaluation(
            candidates=[local_metrics],
            decision="local",
            decision_reason="검증을 통과한 Twin 후보가 없어 Local만 사용합니다.",
            twin_gates=gates,
        )

    if not gate_passed_codes:
        return PoolingEvaluation(
            candidates=[local_metrics],
            decision="local",
            decision_reason="Twin 후보가 인접 시도 문에서 모두 제외되어 Local만 사용합니다.",
            twin_gates=gates,
        )

    all_candidates = [local_metrics]
    for variant_id, label, codes, prefix_k in _pool_variants(gate_passed_codes):
        if mode == "optimize":
            metrics = _research_pool_variant(
                conn,
                local_ctx=local_ctx,
                req=req,
                search_pool=blocks,
                variant_id=variant_id,
                label=label,
                anchor_region_codes=anchor_region_codes,
                twin_codes=codes,
                admin_level=admin_level,
                region_col=region_col,
                prefix_k=prefix_k,
            )
        else:
            metrics = _fit_pool_variant(
                conn,
                local_ctx=local_ctx,
                req=req,
                blocks=diagnose_blocks,
                variant_id=variant_id,
                label=label,
                anchor_region_codes=anchor_region_codes,
                twin_codes=codes,
                admin_level=admin_level,
                region_col=diagnose_region_col,
                response_scale=fixed_response_scale or getattr(local_fit, "response_scale", None),
                prefix_k=prefix_k,
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
