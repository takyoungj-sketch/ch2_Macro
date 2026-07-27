from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from profile_twin.catalog import TwinCatalog, TwinFeatureSpec, load_twin_catalog
from profile_twin.paths import get_profile_path

# SSOT order — build_regional_profile.YEARLY_MIX_TYPES 와 동일
MARKET_MIX_TYPES: tuple[str, ...] = (
    "토지",
    "상가",
    "공장",
    "단독다가구",
    "아파트",
    "오피스텔",
    "연립다세대",
    "분양권",
)


@dataclass
class TwinVector:
    region_level: str
    region_code: str
    catalog_version: str
    values: dict[str, Any] = field(default_factory=dict)
    masks: dict[str, float] = field(default_factory=dict)
    blocks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def mask(self, key: str) -> float:
        return float(self.masks.get(key, 0.0))


def _land_cell_key(obj: dict[str, Any]) -> str | None:
    zone = str(obj.get("zone") or "").strip()
    jimok = str(obj.get("jimok_code") or obj.get("jimok") or "").strip()
    if not zone and not jimok:
        return None
    return f"{zone}|{jimok}"


def _resolve_mask(spec: TwinFeatureSpec, features: dict[str, Any]) -> float:
    if spec.mask_from:
        raw = get_profile_path(features, spec.mask_from)
        active = False
        if isinstance(raw, dict):
            active = any(float(v or 0) > 0 for v in raw.values())
        elif isinstance(raw, (int, float)):
            active = float(raw) > 0
        elif isinstance(raw, bool):
            active = raw
        if not active:
            return 0.0
    if spec.mask_min_count_from:
        count_raw = get_profile_path(features, spec.mask_min_count_from)
        try:
            count = int(count_raw or 0)
        except (TypeError, ValueError):
            count = 0
        min_n = spec.mask_min_count if spec.mask_min_count is not None else 15
        if count < min_n:
            return 0.0
    if spec.optional and spec.dtype == "numeric":
        val = get_profile_path(features, spec.profile_path)
        return 1.0 if val is not None else 0.0
    return 1.0


def project_profile(
    features: dict[str, Any],
    *,
    region_level: str,
    region_code: str,
    catalog: TwinCatalog | None = None,
) -> TwinVector:
    """Catalog twin_vector 기준으로 Profile features → 런타임 Vector (DB 미저장)."""
    cat = catalog or load_twin_catalog()
    vec = TwinVector(
        region_level=str(region_level),
        region_code=str(region_code).strip(),
        catalog_version=cat.version,
    )

    for spec in cat.features:
        mask = _resolve_mask(spec, features)
        vec.masks[spec.key] = mask
        raw = get_profile_path(features, spec.profile_path)

        if spec.dtype == "ratio_vector":
            shares = raw if isinstance(raw, dict) else {}
            vec.values[spec.key] = [float(shares.get(t) or 0.0) for t in MARKET_MIX_TYPES]
        elif spec.dtype == "land_top":
            if isinstance(raw, dict):
                vec.values[spec.key] = {
                    "cell_key": _land_cell_key(raw),
                    "zone": raw.get("zone"),
                    "jimok_code": raw.get("jimok_code") or raw.get("jimok"),
                    "count": int(raw.get("count") or 0),
                    "mean_manwon_per_sqm": raw.get("mean_manwon_per_sqm"),
                }
            else:
                vec.values[spec.key] = None
        elif spec.dtype == "mask":
            vec.values[spec.key] = raw if isinstance(raw, dict) else {}
        elif spec.dtype == "categorical":
            vec.values[spec.key] = str(raw).strip() if raw is not None else None
        else:
            if raw is None:
                vec.values[spec.key] = None
            else:
                try:
                    vec.values[spec.key] = float(raw)
                except (TypeError, ValueError):
                    vec.values[spec.key] = None

        if mask <= 0 and spec.dtype not in ("mask",):
            vec.values[spec.key] = None

    for block, specs in cat.by_block().items():
        vec.blocks[block] = {s.key: vec.values.get(s.key) for s in specs}

    return vec
