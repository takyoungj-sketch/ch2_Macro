"""원장 단가 배열 → 전세/반전세/순수월세 통계. 전환율 없음."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from stats import compute_stats

ASSET_TYPES = ("apartment", "rowhouse", "officetel", "detached")

BUILDING_KEY_SQL = """
COALESCE(
  NULLIF(btrim(building_key::text), ''),
  encode(
    sha256(
      convert_to(
        concat_ws(
          '|',
          coalesce(asset_type, ''),
          coalesce(addr1, ''),
          coalesce(addr2, ''),
          coalesce(addr3, ''),
          coalesce(lot_number, ''),
          coalesce(road_name, '')
        ),
        'UTF8'
      )
    ),
    'hex'
  )
)
"""


def _floats(values: Iterable[Any] | None) -> list[float]:
    out: list[float] = []
    if not values:
        return out
    for x in values:
        if x is None:
            continue
        try:
            v = float(x)
        except (TypeError, ValueError):
            continue
        if v == v:  # not NaN
            out.append(v)
    return out


def pack_metric(values: Sequence[Any] | None) -> dict[str, Any]:
    st = compute_stats(_floats(values))
    n = int(st["count"] or 0)
    if n <= 0:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "ci_lower": None,
            "ci_upper": None,
        }
    return {
        "n": n,
        "mean": st["mean"],
        "median": st["median"],
        "ci_lower": st["ci_lower"],
        "ci_upper": st["ci_upper"],
    }


def pack_building_lease_stats(row: Mapping[str, Any]) -> dict[str, Any]:
    jeonse = pack_metric(row.get("jeonse_deposit"))
    mixed_dep = pack_metric(row.get("mixed_deposit"))
    mixed_mon = pack_metric(row.get("mixed_monthly"))
    monthly = pack_metric(row.get("monthly_rent"))
    mixed_n = max(int(mixed_dep["n"]), int(mixed_mon["n"]))
    return {
        "jeonse_n": jeonse["n"],
        "jeonse_mean": jeonse["mean"],
        "jeonse_median": jeonse["median"],
        "jeonse_ci_lower": jeonse["ci_lower"],
        "jeonse_ci_upper": jeonse["ci_upper"],
        "mixed_n": mixed_n,
        "mixed_deposit_mean": mixed_dep["mean"],
        "mixed_deposit_median": mixed_dep["median"],
        "mixed_deposit_ci_lower": mixed_dep["ci_lower"],
        "mixed_deposit_ci_upper": mixed_dep["ci_upper"],
        "mixed_monthly_mean": mixed_mon["mean"],
        "mixed_monthly_median": mixed_mon["median"],
        "mixed_monthly_ci_lower": mixed_mon["ci_lower"],
        "mixed_monthly_ci_upper": mixed_mon["ci_upper"],
        "monthly_n": monthly["n"],
        "monthly_mean": monthly["mean"],
        "monthly_median": monthly["median"],
        "monthly_ci_lower": monthly["ci_lower"],
        "monthly_ci_upper": monthly["ci_upper"],
    }


def has_any_lease(stats: Mapping[str, Any]) -> bool:
    return (
        int(stats.get("jeonse_n") or 0)
        + int(stats.get("mixed_n") or 0)
        + int(stats.get("monthly_n") or 0)
    ) > 0
