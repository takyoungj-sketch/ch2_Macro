"""
토지 land_upper_stats_v2 → market_stats land_* domain 추출.

설계 SSOT: pipeline/config/land_domain_extraction.yaml
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "pipeline" / "config" / "land_domain_extraction.yaml"


@dataclass(frozen=True)
class DomainCell:
    zone_type: str
    land_category: str


@dataclass(frozen=True)
class DomainRule:
    name: str
    description: str
    cells: tuple[DomainCell, ...]


@dataclass(frozen=True)
class CompositionRule:
    name: str
    zone_types: frozenset[str]
    land_categories: frozenset[str]


def load_domain_config(path: Path | None = None) -> tuple[dict[str, DomainRule], dict[str, CompositionRule]]:
    cfg_path = path or DEFAULT_CONFIG
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    domains: dict[str, DomainRule] = {}
    for name, spec in (raw.get("domains") or {}).items():
        cells = tuple(
            DomainCell(
                zone_type=str(c["zone_type"]).strip(),
                land_category=str(c["land_category"]).strip(),
            )
            for c in (spec.get("cells") or [])
        )
        domains[name] = DomainRule(
            name=name,
            description=str(spec.get("description") or ""),
            cells=cells,
        )

    composition: dict[str, CompositionRule] = {}
    for name, spec in (raw.get("composition") or {}).items():
        composition[name] = CompositionRule(
            name=name,
            zone_types=frozenset(str(z).strip() for z in (spec.get("zone_types") or [])),
            land_categories=frozenset(str(c).strip() for c in (spec.get("land_categories") or [])),
        )
    return domains, composition


def _cell_key(zone_type: str, land_category: str) -> tuple[str, str]:
    return (zone_type.strip(), land_category.strip())


def pick_domain_row(
    cell_map: dict[tuple[str, str], dict[str, Any]],
    rule: DomainRule,
    *,
    min_count: int = 1,
) -> dict[str, Any] | None:
    """규칙 cells 순서대로 첫 유효 셀 반환."""
    for cell in rule.cells:
        z, c = cell.zone_type, cell.land_category
        if z == "ALL" and c != "ALL":
            # 지목 전용: zone=ALL 행에서 land_category 매칭
            row = cell_map.get(("ALL", c))
        elif c == "ALL" and z != "ALL":
            row = cell_map.get((z, "ALL"))
        else:
            row = cell_map.get(_cell_key(z, c))
        if not row:
            continue
        if int(row.get("count") or 0) >= min_count:
            return row
    return None


def build_domain_market_record(
    *,
    market_domain: str,
    region_level: str,
    region_code: str,
    row: dict[str, Any],
    as_of_month,
    window_years: int,
    batch_id: str,
) -> dict[str, Any]:
    return {
        "market_domain": market_domain,
        "region_level": region_level,
        "region_code": str(region_code).strip(),
        "as_of_month": as_of_month,
        "window_years": window_years,
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "count": int(row.get("count") or 0),
        "mean": row.get("mean"),
        "std": row.get("std"),
        "ci_lower": row.get("ci_lower"),
        "ci_upper": row.get("ci_upper"),
        "p25": row.get("p25"),
        "median": row.get("median"),
        "p75": row.get("p75"),
        "yoy": None,
        "volatility": None,
        "batch_id": batch_id,
    }


JIMOK_GROUP_LABELS: dict[str, str] = {
    "agri": "농경지",
    "forest": "산림지",
    "dev": "개발지",
    "infra": "기반시설",
    "water": "수면",
    "special": "특수용도",
    "other": "기타",
}


def jimok_group_features(
    rows: list[dict[str, Any]],
    *,
    top_n: int = 3,
) -> dict[str, Any]:
    """land_upper_stats_v2(col_axis='group') zone×group 행 목록 → 지목군 구성비·TOP N (D-027).

    입력 rows 는 composition_features() 와 동일하게 zone_type<>'ALL' AND land_category<>'ALL'
    로 필터된 (zone, group_code) 셀 목록이어야 한다(land_category 컬럼에 group_code 저장).
    """
    by_group: dict[str, int] = {}
    total = 0
    for r in rows:
        g = str(r.get("land_category") or "").strip()
        if not g or g == "ALL":
            continue
        n = int(r.get("count") or 0)
        if n <= 0:
            continue
        by_group[g] = by_group.get(g, 0) + n
        total += n

    if total <= 0:
        return {}

    composition = {f"jimok_group_share_{g}": round(n / total, 6) for g, n in by_group.items()}
    ranked = sorted(by_group.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    top_list = [
        {
            "group": g,
            "label": JIMOK_GROUP_LABELS.get(g, g),
            "count": n,
            "share": round(n / total, 6),
        }
        for g, n in ranked
    ]
    return {
        "jimok_group_composition": composition,
        "jimok_group_top3": top_list,
        "jimok_group_total_count": total,
    }


def composition_features(
    rows: list[dict[str, Any]],
    rules: dict[str, CompositionRule],
) -> dict[str, float]:
    """land_upper_stats_v2 zone×cat 행 목록 → 거래건수 비중 feature."""
    total = 0
    by_zone: dict[str, int] = {}
    by_cat: dict[str, int] = {}
    for r in rows:
        z = str(r.get("zone_type") or "").strip()
        c = str(r.get("land_category") or "").strip()
        if z == "ALL" or c == "ALL":
            continue
        n = int(r.get("count") or 0)
        if n <= 0:
            continue
        total += n
        by_zone[z] = by_zone.get(z, 0) + n
        by_cat[c] = by_cat.get(c, 0) + n

    if total <= 0:
        return {}

    out: dict[str, float] = {}
    for name, rule in rules.items():
        if rule.zone_types:
            num = sum(by_zone.get(z, 0) for z in rule.zone_types)
        else:
            num = sum(by_cat.get(c, 0) for c in rule.land_categories)
        out[name] = round(num / total, 6)
    return out
