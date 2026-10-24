"""복합 모형추천2.

현행 ``recommend_built_regression`` 과 ``with_complete_case`` 를 호출하지 않는다.
후보마다 그 후보의 열만으로 적합하고, 같은 행 집합 안에서만 CV-MAPE 순위를 매긴다.
화면에 올리는 식은 통계분석 ``_fit_ols`` 와 같은 호출이다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.built.regression.engine import (
    _build_design_matrix,
    _fit_ols,
    _region_dummy_column,
)
from app.built.regression.selection.best_subset import MAX_SUBSETS, enumerate_block_subsets
from app.built.regression.selection.blocks import (
    BlockId,
    block_label,
    spec_from_blocks,
    subset_count,
)
from app.built.regression.selection.context import (
    SelectionContext,
    region_col_for_context,
    resolve_selection_context,
)
from app.built.regression.selection.fit import (
    BlockFitResult,
    common_scale_frame,
    fit_scale_candidates,
    pick_explanatory_scale,
    pick_predictive_scale,
    rolling_time_cv_split,
    subset_allows_loglog,
)
from app.built.schemas import (
    Recommend2Excluded,
    Recommend2Response,
    Recommend2Side,
    RegressionLevelResult,
    RegressionRunRequest,
    RegressionVariableSpec,
    ResponseScale,
)
from app.recommendation.built_pool import (
    count_scope_leaves,
    filter_pool_by_coverage,
)
from app.regression_sample_judge import judge_exog

NOTICE = (
    "이 창은 왼쪽에서 고른 변수와 회귀모형, 결측 거래 제외를 탐색에 쓰지 않습니다. "
    "지역·기간·지분·이상치·건축물대장 보강만 표본 조건입니다. "
    "구조와 개별공시지가는 보강을 켜고 체크한 경우에만 후보에 넣습니다."
)
CV_NOTE = "CV-MAPE는 학습 표본의 오차가 아닙니다. 같은 조합에서 척도를 견줄 때 맞춘 양수 가격·면적 행의 교차검증 오차입니다."
SIDE_NOTE = "개별공시지가가 있는 거래만 쓴 식입니다. 행이 달라 위의 예측형 순위가 아닙니다."
MIN_OFFER_N = 10
SIDE_LIMIT = 5

_CORE_BLOCKS: tuple[BlockId, ...] = (
    "gross_area",
    "land_area",
    "building_age",
    "road_width",
    "zone_type",
    "building_use",
)
_SCALE_KO = {"linear": "선형", "log": "log(금액)", "loglog": "log-log"}


@dataclass(frozen=True)
class RowCandidate:
    """순위 단위. 같은 row_key 만 CV-MAPE로 견준다."""

    row_key: tuple[str, ...]
    n: int
    cv: float | None
    offerable: bool


def winning_row_key(candidates: list[RowCandidate]) -> tuple[str, ...] | None:
    """제공 가능한 후보 가운데 행이 가장 많은 집합을 고른다.

    건수가 같으면 그 집합에서 CV-MAPE가 더 낮은 쪽을 고른다.
    행이 적은 집합의 CV가 더 낮아도 대표 집합이 되지 않는다.
    """
    offerable = [row for row in candidates if row.offerable]
    if not offerable:
        return None
    groups: dict[tuple[str, ...], list[RowCandidate]] = {}
    for row in offerable:
        groups.setdefault(row.row_key, []).append(row)

    def sort_key(item: tuple[tuple[str, ...], list[RowCandidate]]) -> tuple[int, float]:
        _key, rows = item
        best_cv = min(row.cv if row.cv is not None else 1e18 for row in rows)
        return (rows[0].n, -best_cv)

    return max(groups.items(), key=sort_key)[0]


def _row_key(fit: BlockFitResult) -> tuple[str, ...]:
    values = [str(value) for value in fit.model.fittedvalues.index]
    values.sort()
    return tuple(values)


def _offerable(fit: BlockFitResult) -> bool:
    if int(fit.n) < MIN_OFFER_N:
        return False
    try:
        verdict = judge_exog(fit.model.model.exog)
    except (AttributeError, TypeError, ValueError, np.linalg.LinAlgError):
        return False
    return verdict.tier != "blocked"


@dataclass
class _Hit:
    blocks: tuple[str, ...]
    scale: str
    n: int
    cv: float | None
    confirm: float | None
    row_key: tuple[str, ...]
    offerable: bool
    expl_scale: str | None
    expl_aic: float | None


def _blocks_ko(blocks: tuple[str, ...] | list[str]) -> str:
    return " · ".join(block_label(block) for block in blocks)


def _default_pool(ctx: SelectionContext, req: RegressionRunRequest) -> list[BlockId]:
    pool: list[BlockId] = list(_CORE_BLOCKS)
    enrich = bool(getattr(req, "enrich", False))
    if enrich and bool(req.variables.structure_dummy):
        pool.append("structure")
    if ctx.unified:
        pool.append("asset_type")
    if count_scope_leaves(ctx) >= 2:
        pool.append("region_leaf")
    return pool


def _fit_pool(
    df: pd.DataFrame,
    pool: list[BlockId],
    *,
    unified: bool,
    region_col: str | None,
    admin_level: str,
) -> list[_Hit]:
    hits: list[_Hit] = []
    for blocks in enumerate_block_subsets(pool, max_count=MAX_SUBSETS):
        fits = fit_scale_candidates(
            df,
            blocks,
            unified=unified,
            region_col=region_col,
            admin_level=admin_level,
        )
        if not fits:
            continue
        predictive = pick_predictive_scale(fits)
        explanatory = pick_explanatory_scale(fits)
        hits.append(
            _Hit(
                blocks=tuple(blocks),
                scale=predictive.response_scale,
                n=int(predictive.n),
                cv=predictive.cv_mape,
                confirm=predictive.confirm_cv_mape,
                row_key=_row_key(predictive),
                offerable=_offerable(predictive),
                expl_scale=None if explanatory is None else explanatory.response_scale,
                expl_aic=None if explanatory is None else float(explanatory.aic),
            )
        )
    return hits


def _explanatory_note(primary: _Hit, group: list[_Hit]) -> tuple[str | None, str]:
    ranked = [hit for hit in group if hit.expl_scale is not None and hit.expl_aic is not None]
    if not ranked:
        return None, "같은 행에서 log 가족 AIC를 낼 수 없습니다."
    best = min(ranked, key=lambda hit: hit.expl_aic or 0.0)
    if best.blocks == primary.blocks and best.expl_scale == primary.scale:
        return best.expl_scale, "같은 행의 설명형 AIC도 이 식입니다."
    scale_name = _SCALE_KO.get(best.expl_scale or "", best.expl_scale or "")
    return (
        best.expl_scale,
        f"같은 행에서 AIC로 본 설명형은 {scale_name} · {_blocks_ko(best.blocks)}입니다. "
        "위의 식은 CV-MAPE 예측형입니다.",
    )


def _display_fit(
    df: pd.DataFrame,
    spec: RegressionVariableSpec,
    scale: ResponseScale,
    *,
    admin_level: str,
    scope_label: str,
    unified: bool,
    addr4_city: bool,
) -> RegressionLevelResult:
    return _fit_ols(
        df,
        spec,
        admin_level,
        scope_label,
        unified=unified,
        response_scale=scale,
        addr4_city=addr4_city,
        categorical_missing="keep_unknown",
    )


def _side_scale(
    df,
    spec: RegressionVariableSpec,
    *,
    unified: bool,
    admin_level: str,
    addr4_city: bool,
) -> tuple[ResponseScale, float | None, float | None, int]:
    """공시지가를 더한 식의 척도. CV만 견주고 식은 나중에 _fit_ols 로 만든다."""
    import statsmodels.api as sm

    area_blocks = [
        block
        for block, flag in (
            ("gross_area", spec.gross_area),
            ("land_area", spec.land_area),
        )
        if flag
    ]
    frame = common_scale_frame(df, area_blocks)
    region_col = None
    if spec.region_leaf_dummy and admin_level in {"eupmyeondong", "beopjungri"}:
        region_col = _region_dummy_column(spec, admin_level, addr4_city=addr4_city)
    scales: list[ResponseScale] = ["linear", "log"]
    if subset_allows_loglog(area_blocks):
        scales.append("loglog")
    best_scale: ResponseScale = "linear"
    best_key: tuple[int, float] | None = None
    best_cv: float | None = None
    best_confirm: float | None = None
    best_n = 0
    for scale in scales:
        y, x_frame, _meta = _build_design_matrix(
            frame,
            spec,
            unified=unified,
            response_scale=scale,
            region_col=region_col,
            categorical_missing="keep_unknown",
        )
        if len(y) < MIN_OFFER_N or x_frame.empty:
            continue
        try:
            model = sm.OLS(y, sm.add_constant(x_frame, has_constant="add")).fit()
            if judge_exog(model.model.exog).tier == "blocked":
                continue
        except (AttributeError, TypeError, ValueError, np.linalg.LinAlgError):
            continue
        search, _folds, confirm, _cfolds, _skip = rolling_time_cv_split(
            frame,
            spec,
            unified=unified,
            response_scale=scale,
            region_col=region_col,
        )
        key = (0, float(search)) if search is not None else (1, 1e18)
        if best_key is None or key < best_key:
            best_key = key
            best_scale = scale
            best_cv = search
            best_confirm = confirm
            best_n = int(len(y))
    return best_scale, best_cv, best_confirm, best_n


def recommend2_from_context(
    ctx: SelectionContext,
    req: RegressionRunRequest,
    *,
    blocks: list[str] | None = None,
) -> Recommend2Response:
    """이미 읽은 초점 표본으로 추천2를 만든다. 범주 결측 스위치는 읽지 않는다."""
    pool = [block for block in (blocks or _default_pool(ctx, req))]
    kept, excluded = filter_pool_by_coverage(ctx, pool)  # type: ignore[arg-type]
    if not kept:
        detail = "추천2 변수 풀이 비어 있습니다."
        if excluded:
            detail += " 제외: " + "; ".join(excluded)
        raise ValueError(detail)

    region_col = region_col_for_context(ctx, spec_from_blocks(kept))
    hits = _fit_pool(
        ctx.df,
        kept,  # type: ignore[arg-type]
        unified=ctx.unified,
        region_col=region_col,
        admin_level=ctx.admin_level,
    )
    if not hits:
        raise ValueError("추천2 후보를 적합할 수 없습니다. 표본을 확인하세요.")

    chosen_key = winning_row_key(
        [
            RowCandidate(row_key=hit.row_key, n=hit.n, cv=hit.cv, offerable=hit.offerable)
            for hit in hits
        ]
    )
    group = [hit for hit in hits if hit.offerable and hit.row_key == chosen_key]
    if chosen_key is None or not group:
        fallback = min(hits, key=lambda hit: hit.cv if hit.cv is not None else 1e18)
        spec = spec_from_blocks(list(fallback.blocks))
        primary = _display_fit(
            ctx.df,
            spec,
            fallback.scale,  # type: ignore[arg-type]
            admin_level=ctx.admin_level,
            scope_label=ctx.scope_label,
            unified=ctx.unified,
            addr4_city=ctx.addr4_city,
        )
        return _response(
            ctx,
            kept,
            excluded,
            primary=primary,
            variables=spec,
            scale=fallback.scale,  # type: ignore[arg-type]
            cv=fallback.cv,
            confirm=fallback.confirm,
            cv_n=fallback.n,
            explanatory_scale=None,
            explanatory_note="제공 기준을 통과한 같은 행 집합이 없습니다.",
            sides=[],
            total=subset_count(kept),  # type: ignore[arg-type]
        )

    group.sort(key=lambda hit: orig_cv_sort_key_from_hit(hit))
    primary_hit = group[0]
    spec = spec_from_blocks(list(primary_hit.blocks))
    primary = _display_fit(
        ctx.df,
        spec,
        primary_hit.scale,  # type: ignore[arg-type]
        admin_level=ctx.admin_level,
        scope_label=ctx.scope_label,
        unified=ctx.unified,
        addr4_city=ctx.addr4_city,
    )
    expl_scale, expl_note = _explanatory_note(primary_hit, group)
    sides = _assessed_sides(ctx, req, group[:SIDE_LIMIT])
    return _response(
        ctx,
        kept,
        excluded,
        primary=primary,
        variables=spec,
        scale=primary_hit.scale,  # type: ignore[arg-type]
        cv=primary_hit.cv,
        confirm=primary_hit.confirm,
        cv_n=primary_hit.n,
        explanatory_scale=expl_scale,  # type: ignore[arg-type]
        explanatory_note=expl_note,
        sides=sides,
        total=subset_count(kept),  # type: ignore[arg-type]
    )


def orig_cv_sort_key_from_hit(hit: _Hit) -> tuple[int, float, float]:
    if hit.cv is not None:
        return (0, float(hit.cv), 0.0)
    return (2, 0.0, 0.0)


def _assessed_sides(
    ctx: SelectionContext,
    req: RegressionRunRequest,
    top: list[_Hit],
) -> list[Recommend2Side]:
    enrich = bool(getattr(req, "enrich", False))
    if not enrich or not bool(req.variables.assessed_land_price):
        return []
    if "assessed_land_price" not in ctx.df.columns:
        return []
    sides: list[Recommend2Side] = []
    n_pool = int(len(ctx.df))
    for hit in top:
        spec = spec_from_blocks(list(hit.blocks)).model_copy(
            update={"assessed_land_price": True}
        )
        scale, cv, confirm, cv_n = _side_scale(
            ctx.df,
            spec,
            unified=ctx.unified,
            admin_level=ctx.admin_level,
            addr4_city=ctx.addr4_city,
        )
        result = _display_fit(
            ctx.df,
            spec,
            scale,
            admin_level=ctx.admin_level,
            scope_label=ctx.scope_label,
            unified=ctx.unified,
            addr4_city=ctx.addr4_city,
        )
        ratio = round(result.n / n_pool, 4) if n_pool else None
        sides.append(
            Recommend2Side(
                block_summary=_blocks_ko(hit.blocks) + " · 개별공시지가",
                response_scale=scale,
                n=int(result.n),
                n_rank=cv_n,
                coverage_ratio=ratio,
                cv_mape=cv,
                confirm_cv_mape=confirm,
                result=result,
            )
        )
    return sides


def _response(
    ctx: SelectionContext,
    kept: list[str],
    excluded: list[str],
    *,
    primary: RegressionLevelResult,
    variables: RegressionVariableSpec,
    scale: ResponseScale,
    cv: float | None,
    confirm: float | None,
    cv_n: int,
    explanatory_scale: ResponseScale | None,
    explanatory_note: str,
    sides: list[Recommend2Side],
    total: int,
) -> Recommend2Response:
    return Recommend2Response(
        notice=NOTICE,
        scope_label=ctx.scope_label,
        n_pool=int(len(ctx.df)),
        pool_summary=_blocks_ko(kept),
        excluded=[Recommend2Excluded(detail=line) for line in excluded],
        primary=primary,
        variables=variables,
        response_scale=scale,
        cv_mape=cv,
        confirm_cv_mape=confirm,
        cv_n=cv_n,
        explanatory_scale=explanatory_scale,
        explanatory_note=explanatory_note,
        sides=sides,
        total_subsets=total,
    )


def recommend2_built(conn, req: RegressionRunRequest) -> Recommend2Response:
    """통계분석과 같은 범위 조회 뒤 추천2. 결측 거래 제외 스위치는 무시한다."""
    fixed = req.model_copy(update={"categorical_missing": "keep_unknown"})
    ctx = resolve_selection_context(conn, fixed)
    return recommend2_from_context(ctx, fixed)
