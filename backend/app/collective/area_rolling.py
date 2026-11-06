"""롤링 구간 면적형. 열린 건물·cluster의 거래를 한 번 읽어 구간×면적으로 나눈다.

주거 효용지수의 30㎡ 면적형과는 다른 눈금이다. 이 화면은 전용면적을 5㎡로 반올림한다.
상가·공장은 효용지수와 같은 연면적 구간을 쓴다.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.collective.area_buckets import label_for_gross_area
from app.stats_utils import compute_stats

RESIDENTIAL_AREA_STEP_M2 = 5
RESIDENTIAL_AREA_RULE = "전용면적을 5㎡ 단위로 반올림했습니다. 전용면적이 없는 거래는 이 화면에 넣지 않습니다."
SHOP_AREA_RULE = "연면적은 35㎡ 미만, 35~50㎡, 50~100㎡, 100~300㎡, 300㎡ 이상입니다. 연면적이 없는 거래는 이 화면에 넣지 않습니다."
FACTORY_AREA_RULE = "연면적은 100㎡ 미만, 100~300㎡, 300~1000㎡, 1000㎡ 이상입니다. 연면적이 없는 거래는 이 화면에 넣지 않습니다."


def residential_area_type(exclusive_area: float | None) -> tuple[str, float] | None:
    """전용면적을 5㎡ 단위로 반올림한다. 0㎡ 이하는 면적형에 넣지 않는다."""
    if exclusive_area is None:
        return None
    try:
        value = float(exclusive_area)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    hundredths = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    bucket = (hundredths / Decimal(RESIDENTIAL_AREA_STEP_M2)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    ) * Decimal(RESIDENTIAL_AREA_STEP_M2)
    rounded = int(bucket)
    if rounded <= 0:
        return None
    return f"{rounded}㎡", float(rounded)


def commercial_area_type(asset_type: str | None, gross_area: float | None) -> tuple[str, float] | None:
    if asset_type not in ("collective_shop", "collective_factory"):
        return None
    try:
        area = float(gross_area) if gross_area is not None else None
    except (TypeError, ValueError):
        return None
    if area is None or not math.isfinite(area) or area <= 0:
        return None
    label, sort_key = label_for_gross_area(asset_type, area)
    if sort_key is None or label == "—":
        return None
    return label, float(sort_key)


def commercial_area_rule(asset_types: set[str]) -> str:
    kinds = {t for t in asset_types if t in ("collective_shop", "collective_factory")}
    if kinds == {"collective_factory"}:
        return FACTORY_AREA_RULE
    if kinds == {"collective_shop"}:
        return SHOP_AREA_RULE
    if kinds == {"collective_shop", "collective_factory"}:
        return f"{SHOP_AREA_RULE} {FACTORY_AREA_RULE}"
    return SHOP_AREA_RULE


def _bucket_index(contract_date: date, buckets: list[tuple[date, date, int]]) -> int | None:
    for start, end, index in buckets:
        if start <= contract_date <= end:
            return index
    return None


def _bucket_label(period_start: date, period_end: date) -> str:
    return (
        f"{period_start.year % 100:02d}.{period_start.month:02d}"
        f"~{period_end.year % 100:02d}.{period_end.month:02d}"
    )


def build_area_series(
    labeled: list[tuple[date, float, str, float]],
    buckets: list[tuple[date, date, int]],
) -> list[dict]:
    """(계약일, ㎡당가, 면적라벨, 정렬키)를 구간×면적형으로 모은다. 건수 하한은 두지 않는다."""
    meta = {index: (start, end) for start, end, index in buckets}
    grouped: dict[tuple[str, float], dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for contract_date, price, label, sort_key in labeled:
        if contract_date is None or price is None or price <= 0:
            continue
        index = _bucket_index(contract_date, buckets)
        if index is None:
            continue
        grouped[(label, sort_key)][index].append(float(price))

    series: list[dict] = []
    for (label, sort_key), by_bucket in grouped.items():
        points: list[dict] = []
        for index in sorted(by_bucket):
            start, end = meta[index]
            stats = compute_stats(by_bucket[index])
            if stats["count"] <= 0:
                continue
            points.append(
                {
                    "bucket_index": index,
                    "period_start": start.isoformat(),
                    "period_end": end.isoformat(),
                    "label": _bucket_label(start, end),
                    "count": stats["count"],
                    "mean": stats["mean"],
                    "median": stats["median"],
                }
            )
        if points:
            series.append({"area_label": label, "area_sort": sort_key, "points": points})
    series.sort(key=lambda item: (item["area_sort"], item["area_label"]))
    return series
