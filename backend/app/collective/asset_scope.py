"""집합 asset_type 필터 — 단일·복수(콤마) 또는 통합(all).

주거(apartment…)와 상업(collective_shop…) 허용 집합을 분리한다.
"""

from __future__ import annotations

RESIDENTIAL_ASSET_TYPES = frozenset({"apartment", "rowhouse", "officetel", "presale"})
COMMERCIAL_ASSET_TYPES = frozenset({"collective_shop", "collective_factory"})
_RESIDENTIAL_ORDER = ("apartment", "rowhouse", "officetel", "presale")
_COMMERCIAL_ORDER = ("collective_shop", "collective_factory")


def parse_asset_types(
    asset_type: str | None,
    *,
    allowed: frozenset[str],
) -> list[str] | None:
    """유효 유형 목록. None = 필터 없음(전체 / 허용 유형 전부)."""
    if not asset_type or not str(asset_type).strip() or str(asset_type).strip() == "all":
        return None
    raw = str(asset_type).replace("|", ",")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p in allowed and p not in seen:
            seen.add(p)
            out.append(p)
    if not out:
        return None
    if seen == set(allowed):
        return None
    return out


def apply_asset_type_filter(
    clauses: list[str],
    params: dict,
    asset_type: str | None,
    *,
    allowed: frozenset[str],
    col_prefix: str = "",
) -> None:
    types = parse_asset_types(asset_type, allowed=allowed)
    if not types:
        return
    p = f"{col_prefix}." if col_prefix else ""
    if len(types) == 1:
        clauses.append(f"{p}asset_type = :asset_type")
        params["asset_type"] = types[0]
    else:
        clauses.append(f"{p}asset_type = ANY(:asset_types)")
        params["asset_types"] = types


def apply_collective_asset_filter(
    clauses: list[str],
    params: dict,
    asset_type: str | None,
    *,
    col_prefix: str = "",
) -> None:
    """주거·상업 공통 — 알려진 집합 유형만 인식."""
    allowed = RESIDENTIAL_ASSET_TYPES | COMMERCIAL_ASSET_TYPES
    apply_asset_type_filter(
        clauses, params, asset_type, allowed=allowed, col_prefix=col_prefix
    )


def normalize_asset_type(
    asset_type: str | None,
    *,
    allowed: frozenset[str] | None = None,
) -> str | None:
    """하위 호환: 단일 유형만 반환. 복수·all 은 None."""
    allowed = allowed if allowed is not None else (RESIDENTIAL_ASSET_TYPES | COMMERCIAL_ASSET_TYPES)
    types = parse_asset_types(asset_type, allowed=allowed)
    if types and len(types) == 1:
        return types[0]
    return None


def residential_types_selected(asset_type: str | None) -> list[str] | None:
    """주거 필터 목록. None = 주거 전체."""
    return parse_asset_types(asset_type, allowed=RESIDENTIAL_ASSET_TYPES)


def includes_presale(asset_type: str | None) -> bool:
    types = residential_types_selected(asset_type)
    if types is None:
        return True
    return "presale" in types


def is_presale_only(asset_type: str | None) -> bool:
    types = residential_types_selected(asset_type)
    return types == ["presale"]


def without_presale_asset_param(asset_type: str | None) -> str | None:
    """목록 롤링 조회용 — 분양권 제외. 전부만이면 None(스킵)."""
    types = residential_types_selected(asset_type)
    if types is None:
        return ",".join(t for t in _RESIDENTIAL_ORDER if t != "presale")
    rest = [t for t in types if t != "presale"]
    if not rest:
        return None
    return ",".join(rest)


def is_multi_or_all(asset_type: str | None, *, allowed: frozenset[str]) -> bool:
    if not asset_type:
        return False
    raw = str(asset_type).strip()
    if raw == "all":
        return True
    types = parse_asset_types(asset_type, allowed=allowed)
    if types is None:
        parts = {p.strip() for p in raw.replace("|", ",").split(",") if p.strip()}
        return parts == set(allowed)
    return len(types) >= 2
