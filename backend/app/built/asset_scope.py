"""asset_type 필터 — 단일 유형 또는 통합(all)."""

from __future__ import annotations

BUILT_ASSET_TYPES = frozenset({"commercial", "factory", "detached"})


def normalize_asset_type(asset_type: str | None) -> str | None:
    if not asset_type or asset_type == "all":
        return None
    return asset_type


def apply_asset_type_filter(
    clauses: list[str],
    params: dict,
    asset_type: str | None,
    *,
    col_prefix: str = "",
) -> None:
    norm = normalize_asset_type(asset_type)
    if not norm:
        return
    p = f"{col_prefix}." if col_prefix else ""
    clauses.append(f"{p}asset_type = :asset_type")
    params["asset_type"] = norm


def is_unified(asset_type: str | None) -> bool:
    return asset_type == "all"
