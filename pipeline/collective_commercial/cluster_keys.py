"""cluster_key · display_label · 면적구간 (집합상가·집합공장)."""

from __future__ import annotations

import hashlib
import re

AssetType = str  # collective_shop | collective_factory

SHOP_AREA_BUCKETS: list[tuple[float, float | None, str]] = [
    (0, 35, "35㎡ 미만"),
    (35, 50, "35~50㎡"),
    (50, 100, "50~100㎡"),
    (100, 300, "100~300㎡"),
    (300, None, "300㎡ 이상"),
]

FACTORY_AREA_BUCKETS: list[tuple[float, float | None, str]] = [
    (0, 100, "100㎡ 미만"),
    (100, 300, "100~300㎡"),
    (300, 1000, "300~1000㎡"),
    (1000, None, "1000㎡ 이상"),
]


def _norm(s: str | None) -> str:
    if s is None:
        return ""
    if isinstance(s, float) and s != s:
        return ""
    return re.sub(r"\s+", " ", str(s).strip())


def area_bucket_label(asset_type: str, gross_area: float | None) -> str:
    if gross_area is None or gross_area <= 0:
        return "면적 미상"
    buckets = SHOP_AREA_BUCKETS if asset_type == "collective_shop" else FACTORY_AREA_BUCKETS
    for lo, hi, label in buckets:
        if gross_area >= lo and (hi is None or gross_area < hi):
            return label
    return buckets[-1][2]


def derive_building_year(contract_year: int | None, building_age: float | None) -> int | None:
    if contract_year is None or building_age is None:
        return None
    try:
        v = float(building_age)
        if v != v:  # NaN
            return None
        cy = int(contract_year)
        if v >= 1900:
            y = int(round(v))
            if 1900 <= y <= cy + 1:
                return y
        age = int(round(v))
        if 0 <= age <= 150:
            by = cy - age
            if 1900 <= by <= cy:
                return by
    except (TypeError, ValueError):
        pass
    return None


def make_road_cluster_key(
    *,
    asset_type: str,
    addr1: str | None,
    addr2: str | None,
    addr3: str | None,
    addr4: str | None,
    road_name: str | None,
) -> str:
    raw = "|".join(
        [
            asset_type,
            _norm(addr1),
            _norm(addr2),
            _norm(addr3),
            _norm(addr4),
            _norm(road_name),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_road_display_label(
    *,
    road_name: str | None,
    addr3: str | None = None,
    addr4: str | None = None,
) -> str:
    road = _norm(road_name) or "도로명 미상"
    loc = " · ".join(x for x in (_norm(addr3), _norm(addr4)) if x)
    return f"{road} ({loc})" if loc else road


def make_cluster_key(
    *,
    asset_type: str,
    addr3: str | None,
    road_name: str | None,
    zone_type: str | None,
    building_use: str | None,
    building_year: int | None,
    area_bucket: str,
) -> str:
    raw = "|".join(
        [
            asset_type,
            _norm(addr3),
            _norm(road_name),
            _norm(zone_type),
            _norm(building_use),
            str(building_year or ""),
            _norm(area_bucket),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_display_label(
    *,
    road_name: str | None,
    building_use: str | None,
    building_year: int | None,
    area_bucket: str,
) -> str:
    road = _norm(road_name) or "도로명 미상"
    use = _norm(building_use) or "용도 미상"
    year = f"{building_year}년" if building_year not in (None, "") else "연식 미상"
    return f"{road} ({use} · {year} · {area_bucket})"


def confidence_tier(n: int, *, area_cv: float | None = None) -> str:
    if n >= 30:
        tier = "high"
    elif n >= 15:
        tier = "medium"
    else:
        tier = "low"
    if area_cv is not None and area_cv > 0.25 and tier == "high":
        return "medium"
    return tier
