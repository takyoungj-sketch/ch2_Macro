"""asset_type 필터 — 단일·복수(콤마) 또는 통합(all)."""

from __future__ import annotations

BUILT_ASSET_TYPES = frozenset({"commercial", "factory", "detached"})
_ASSET_ORDER = ("commercial", "factory", "detached")


def parse_asset_types(asset_type: str | None) -> list[str] | None:
    """유효 유형 목록. None = 필터 없음(전체 / 3유형 전부)."""
    if not asset_type or not str(asset_type).strip() or str(asset_type).strip() == "all":
        return None
    raw = str(asset_type).replace("|", ",")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p in BUILT_ASSET_TYPES and p not in seen:
            seen.add(p)
            out.append(p)
    if not out:
        return None
    if seen == BUILT_ASSET_TYPES:
        return None
    return out


def encode_asset_types(types: list[str] | None) -> str:
    """정규 문자열. 전체면 all."""
    if not types:
        return "all"
    ordered = [t for t in _ASSET_ORDER if t in set(types)]
    if len(ordered) >= len(BUILT_ASSET_TYPES):
        return "all"
    if len(ordered) == 1:
        return ordered[0]
    return ",".join(ordered)


def normalize_asset_type(asset_type: str | None) -> str | None:
    """하위 호환: 단일 유형만 반환, 복수·all 은 None."""
    types = parse_asset_types(asset_type)
    if types and len(types) == 1:
        return types[0]
    return None


def apply_asset_type_filter(
    clauses: list[str],
    params: dict,
    asset_type: str | None,
    *,
    col_prefix: str = "",
) -> None:
    types = parse_asset_types(asset_type)
    if not types:
        return
    p = f"{col_prefix}." if col_prefix else ""
    if len(types) == 1:
        clauses.append(f"{p}asset_type = :asset_type")
        params["asset_type"] = types[0]
    else:
        clauses.append(f"{p}asset_type = ANY(:asset_types)")
        params["asset_types"] = types


def is_unified(asset_type: str | None) -> bool:
    """2개 이상 유형(또는 all)이면 통합 분석(유형 더미 등)."""
    if not asset_type:
        return False
    raw = str(asset_type).strip()
    if raw == "all":
        return True
    types = parse_asset_types(asset_type)
    if types is None:
        parts = {p.strip() for p in raw.replace("|", ",").split(",") if p.strip()}
        return parts == BUILT_ASSET_TYPES
    return len(types) >= 2
