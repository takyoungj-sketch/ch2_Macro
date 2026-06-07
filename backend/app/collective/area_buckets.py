"""집합상가·집합공장 연면적 구간 (pipeline/cluster_keys.py 와 동일 규칙)."""

from __future__ import annotations

# (lo, hi_exclusive, label, sort_key)
FACTORY_AREA_BUCKETS: list[tuple[float, float | None, str, float]] = [
    (0, 100, "100㎡ 미만", 0),
    (100, 300, "100~300㎡", 100),
    (300, 1000, "300~1000㎡", 300),
    (1000, None, "1000㎡ 이상", 1000),
]

SHOP_AREA_BUCKETS: list[tuple[float, float | None, str, float]] = [
    (0, 35, "35㎡ 미만", 0),
    (35, 50, "35~50㎡", 35),
    (50, 100, "50~100㎡", 50),
    (100, 300, "100~300㎡", 100),
    (300, None, "300㎡ 이상", 300),
]

SHOP_AREA_BUCKET_M2 = 30

FACTORY_BUCKET_ORDER = {label: sort_key for _, _, label, sort_key in FACTORY_AREA_BUCKETS}


def label_for_gross_area(asset_type: str, gross_area: float | None) -> tuple[str, float | None]:
    """(표시 라벨, 정렬키) — 매핑 불가 시 ('—', None)."""
    if gross_area is None or gross_area <= 0:
        return "—", None
    buckets = SHOP_AREA_BUCKETS if asset_type == "collective_shop" else FACTORY_AREA_BUCKETS
    for lo, hi, label, sort_key in buckets:
        if gross_area >= lo and (hi is None or gross_area < hi):
            return label, sort_key
    last = buckets[-1]
    return last[2], last[3]


def shop_fixed_bucket_label(gross_area: float) -> tuple[str, float]:
    """상가 면적형 탭: 30㎡ 단위 반올림."""
    bucket = round(gross_area / SHOP_AREA_BUCKET_M2) * SHOP_AREA_BUCKET_M2
    label = f"{int(bucket)}㎡" if bucket == int(bucket) else f"{bucket:g}㎡"
    return label, bucket
