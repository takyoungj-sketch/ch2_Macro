"""회귀 scope — 모형 선택용 primary level 표본."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.built.asset_scope import is_unified
from app.built.regression.engine import (
    CompareMode,
    _focus_admin_level,
    _label_for_level,
    _prepare_regression_scope,
    _region_col_for_scatter,
    _scope_for_level,
)
from app.built.schemas import AdminLevel, RegressionRunRequest, ResponseScale


@dataclass(frozen=True)
class SelectionContext:
    df: pd.DataFrame
    scope_label: str
    admin_level: AdminLevel
    addr4_city: bool
    mode: CompareMode
    unified: bool


def resolve_selection_context(conn, req: RegressionRunRequest) -> SelectionContext:
    wide_df, req, addr4_city, mode = _prepare_regression_scope(conn, req)
    level = _focus_admin_level(req, addr4_city)
    df = _scope_for_level(wide_df, req, level, addr4_city, mode)
    label = _label_for_level(req, wide_df, level, addr4_city)
    return SelectionContext(
        df=df,
        scope_label=label,
        admin_level=level,
        addr4_city=addr4_city,
        mode=mode,
        unified=is_unified(req.asset_type),
    )


def region_col_for_context(ctx: SelectionContext, spec) -> str | None:
    return _region_col_for_scatter(spec, ctx.admin_level, ctx.addr4_city)
