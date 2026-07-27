#!/usr/bin/env python3
"""
market_stats (+ population, 토지 composition/jimok Top, yearly_mix) → regional_profile JSON features.

설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md §12 (D-027 · D-029 Phase A)
예: --sido-code 43 --profile-version v2.1-national --window-years 3
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from built.db_utils import get_built_engine  # noqa: E402
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from land_domain_extraction import (  # noqa: E402
    composition_features,
    jimok_group_features,
    load_domain_config,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

BUILDER_VERSION = "2026.07.27.2"
DEFAULT_PROFILE_VERSION = "v1.1-national"
PROFILE_VERSION_V2 = "v2.0-national"
PROFILE_VERSION_V21 = "v2.1-national"  # D-029 Phase A

DOMAIN_FEATURES: dict[str, tuple[str, ...]] = {
    "apartment_market": ("count", "mean", "median", "std", "volatility", "p25", "p75"),
    "rowhouse_market": ("count", "mean", "median", "std", "volatility", "p25", "p75"),
    "officetel_market": ("count", "mean", "median", "std", "volatility", "p25", "p75"),
    "presale_market": ("count", "mean", "median", "std", "p25", "p75"),
    "land_residential": ("count", "mean", "median", "std"),
    "land_commercial": ("count", "mean", "median", "std"),
    "land_industrial": ("count", "mean", "median", "std"),
    "land_agricultural": ("count", "mean", "median"),
    "land_forest": ("count", "mean", "median"),
    # D-027: built(일반 3유형) + collective_commercial(집합상가·공장) market_stats 도메인
    "commercial_market": ("count", "mean", "median", "std", "p25", "p75"),
    "factory_market": ("count", "mean", "median", "std", "p25", "p75"),
    "detached_market": ("count", "mean", "median", "std", "p25", "p75"),
    "collective_shop_market": ("count", "mean", "median", "std", "p25", "p75"),
    "collective_factory_market": ("count", "mean", "median", "std", "p25", "p75"),
}

DOMAIN_PREFIX: dict[str, str] = {
    "apartment_market": "apartment",
    "rowhouse_market": "rowhouse",
    "officetel_market": "officetel",
    "presale_market": "presale",
    "commercial_market": "commercial",
    "factory_market": "factory",
    "detached_market": "detached",
    "collective_shop_market": "collective_shop",
    "collective_factory_market": "collective_factory",
}

# D-027: Regional Profile v2 — 3개년 × 8대 시장유형(yearly_mix). 상가=commercial+collective_shop,
# 공장=factory+collective_factory 를 이 단계에서만 병합(원천 market_stats/annual mart 도메인은 독립 유지).
YEARLY_MIX_TYPES: tuple[str, ...] = (
    "토지", "상가", "공장", "단독다가구", "아파트", "오피스텔", "연립다세대", "분양권",
)

TYPE_SOURCE_MAP: dict[str, tuple[tuple[str, str], ...]] = {
    "토지": (("land", ""),),
    "상가": (("built", "commercial"), ("cc", "collective_shop")),
    "공장": (("built", "factory"), ("cc", "collective_factory")),
    "단독다가구": (("built", "detached"),),
    "아파트": (("market", "apartment_market"),),
    "오피스텔": (("market", "officetel_market"),),
    "연립다세대": (("market", "rowhouse_market"),),
    "분양권": (("market", "presale_market"),),
}

_COLLECTIVE_ASSET_TO_MIX: dict[str, str] = {
    "apartment": "아파트",
    "rowhouse": "연립다세대",
    "officetel": "오피스텔",
    "presale": "분양권",
}
_BUILT_ASSET_TO_MIX: dict[str, str] = {
    "commercial": "상가",
    "factory": "공장",
    "detached": "단독다가구",
}
_CC_ASSET_TO_MIX: dict[str, str] = {
    "collective_shop": "상가",
    "collective_factory": "공장",
}


def _sigungu_to_city_bucket(sigungu_code: str) -> str:
    """시군구 5자리 → 의사 시 단위 버킷 (build_upper_stats_v2 와 동일)."""
    s = str(sigungu_code).strip()
    if not s.isdigit() or len(s) != 5:
        return ""
    return str((int(s) // 10) * 10).zfill(5)


def _fetch_beop_yearly_from_ledgers(
    coll_conn,
    built_conn,
    *,
    years: list[int],
    sido_code: str | None,
) -> dict[tuple[str, int], dict[str, dict]]:
    """리 grain — 집합·복합·집합상가 원장에서 8대유형(토지 제외) count/amount (D-029).

    annual mart는 eup+ 상위만 있어 beop Profile yearly_mix 보완용.
    성능: beopjungri_code 직접 집계(canonical 서브쿼리 per-row 회피).
    """
    out: dict[tuple[str, int], dict[str, dict]] = {}
    params: dict = {"years": years}
    sido_clause = ""
    if sido_code:
        sido_clause = "AND substring(btrim(t.beopjungri_code::text) from 1 for 2) = :sido"
        params["sido"] = sido_code
    beop_filter = """
              AND t.beopjungri_code IS NOT NULL
              AND btrim(t.beopjungri_code::text) <> ''
              AND length(btrim(t.beopjungri_code::text)) = 10
    """

    def _add(beop: str, cy: int, type_kr: str, count: int, amount: float) -> None:
        b = str(beop).strip()
        if len(b) != 10 or not b.isdigit() or count <= 0:
            return
        cell = out.setdefault((b, cy), {}).setdefault(type_kr, {"count": 0, "amount": 0.0})
        cell["count"] += int(count)
        cell["amount"] += float(amount)

    coll_rows = coll_conn.execute(
        text(
            f"""
            SELECT btrim(t.beopjungri_code::text) AS beop,
                   t.contract_year AS cy,
                   t.asset_type,
                   COUNT(*) AS n,
                   COALESCE(SUM(t.price), 0) AS amt
            FROM collective_transactions t
            WHERE t.is_valid = true
              AND t.contract_year = ANY(:years)
              {beop_filter}
              {sido_clause}
            GROUP BY 1, 2, 3
            """
        ),
        params,
    ).mappings().all()
    for r in coll_rows:
        mix = _COLLECTIVE_ASSET_TO_MIX.get(str(r["asset_type"]).strip())
        if mix:
            _add(r["beop"], int(r["cy"]), mix, int(r["n"]), float(r["amt"]))

    cc_rows = coll_conn.execute(
        text(
            f"""
            SELECT btrim(t.beopjungri_code::text) AS beop,
                   t.contract_year AS cy,
                   t.asset_type,
                   COUNT(*) AS n,
                   COALESCE(SUM(t.price), 0) AS amt
            FROM collective_commercial_transactions t
            WHERE t.is_valid = true
              AND t.contract_year = ANY(:years)
              {beop_filter}
              {sido_clause}
            GROUP BY 1, 2, 3
            """
        ),
        params,
    ).mappings().all()
    for r in cc_rows:
        mix = _CC_ASSET_TO_MIX.get(str(r["asset_type"]).strip())
        if mix:
            _add(r["beop"], int(r["cy"]), mix, int(r["n"]), float(r["amt"]))

    built_rows = built_conn.execute(
        text(
            f"""
            SELECT btrim(t.beopjungri_code::text) AS beop,
                   t.contract_year AS cy,
                   t.asset_type,
                   COUNT(*) AS n,
                   COALESCE(SUM(t.price), 0) AS amt
            FROM built_transactions t
            WHERE t.is_valid = true
              AND t.contract_year = ANY(:years)
              {beop_filter}
              {sido_clause}
            GROUP BY 1, 2, 3
            """
        ),
        params,
    ).mappings().all()
    for r in built_rows:
        mix = _BUILT_ASSET_TO_MIX.get(str(r["asset_type"]).strip())
        if mix:
            _add(r["beop"], int(r["cy"]), mix, int(r["n"]), float(r["amt"]))

    return out


def _rollup_yearly_maps_to_city(
    land_map: dict[tuple[str, str, int], dict],
    built_map: dict[tuple[str, str, str, int], dict],
    cc_map: dict[tuple[str, str, str, int], dict],
    market_map: dict[tuple[str, str, str, int], dict],
) -> None:
    """annual mart에 city grain 없음 → sigungu/eup 합산으로 city yearly_mix 보완."""

    def _merge_land(city: str, cy: int, agg: dict) -> None:
        dst = land_map.setdefault(("city", city, cy), {"count": 0, "amount": 0.0})
        dst["count"] += int(agg.get("count") or 0)
        dst["amount"] += float(agg.get("amount") or 0.0)

    for (level, rc, cy), agg in list(land_map.items()):
        if level == "sigungu":
            city = _sigungu_to_city_bucket(rc)
        elif level == "eupmyeondong":
            city = _sigungu_to_city_bucket(rc[:5])
        else:
            continue
        if city:
            _merge_land(city, cy, agg)

    def _merge_domain_map(src: dict[tuple[str, str, str, int], dict]) -> None:
        for key, agg in list(src.items()):
            domain, level, rc, cy = key
            if level == "sigungu":
                city = _sigungu_to_city_bucket(rc)
            elif level == "eupmyeondong":
                city = _sigungu_to_city_bucket(rc[:5])
            else:
                continue
            if not city:
                continue
            dst_key = (domain, "city", city, cy)
            dst = src.setdefault(dst_key, {"count": 0, "amount": 0.0})
            dst["count"] += int(agg.get("count") or 0)
            dst["amount"] += float(agg.get("amount") or 0.0)

    _merge_domain_map(built_map)
    _merge_domain_map(cc_map)
    _merge_domain_map(market_map)


def _region_matches_sido(level: str, code: str, sido: str | None) -> bool:
    if not sido:
        return True
    c = str(code).strip()
    if level == "sido":
        return c == sido
    return c.startswith(sido)


def _sigungu_from_eup(code8: str) -> str:
    return str(code8).strip()[:5]


def _fetch_market_rows(
    conn,
    *,
    as_of: date,
    window_years: int,
    sido_code: str | None,
) -> list[dict]:
    sql = """
        SELECT market_domain, region_level, region_code,
               count, mean, median, std, yoy, volatility, p25, p75
        FROM market_stats
        WHERE as_of_month = :as_of AND window_years = :wy
    """
    rows = conn.execute(text(sql), {"as_of": as_of, "wy": window_years}).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        if not _region_matches_sido(d["region_level"], d["region_code"], sido_code):
            continue
        out.append(d)
    return out


def _index_market_rows(rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    """(domain, level, code) → row."""
    idx: dict[tuple[str, str, str], dict] = {}
    for r in rows:
        key = (r["market_domain"], r["region_level"], str(r["region_code"]).strip())
        idx[key] = r
    return idx


def build_features_from_market(
    market_rows: list[dict],
    *,
    escalate_land: bool,
) -> dict[tuple[str, str], dict]:
    idx = _index_market_rows(market_rows)
    profiles: dict[tuple[str, str], dict] = {}

    land_domains = [d for d in DOMAIN_FEATURES if d.startswith("land_")]

    for r in market_rows:
        domain = r["market_domain"]
        level = r["region_level"]
        code = str(r["region_code"]).strip()
        key = (level, code)
        feats = profiles.setdefault(key, {})
        prefix = DOMAIN_PREFIX.get(domain, domain)
        cols = DOMAIN_FEATURES.get(domain, ("count", "mean", "median"))
        for col in cols:
            val = r.get(col)
            if val is None:
                continue
            feat_name = f"{prefix}_{col}" if domain.endswith("_market") else f"{domain}_{col}"
            feats[feat_name] = float(val) if col != "count" else int(val)
        if r.get("yoy") is not None and domain.endswith("_market"):
            feats[f"{DOMAIN_PREFIX.get(domain, domain.split('_')[0])}_yoy"] = float(r["yoy"])

    if escalate_land:
        for (level, code), feats in list(profiles.items()):
            if level != "eupmyeondong":
                continue
            sg = _sigungu_from_eup(code)
            for domain in land_domains:
                mean_key = f"{domain}_mean"
                if mean_key in feats:
                    continue
                parent = idx.get((domain, "sigungu", sg))
                if not parent:
                    continue
                for col in DOMAIN_FEATURES.get(domain, ()):
                    val = parent.get(col)
                    if val is None:
                        continue
                    feat_name = f"{domain}_{col}"
                    if feat_name not in feats:
                        feats[feat_name] = float(val) if col != "count" else int(val)
                feats[f"{domain}_source_level"] = "sigungu"

    return profiles


def _population_for_region(
    conn,
    *,
    region_level: str,
    region_code: str,
    stats_year: int,
) -> dict:
    code = str(region_code).strip()
    if region_level == "beopjungri":
        sql = """
            SELECT total_population AS pop
            FROM population_stats
            WHERE stats_year = :yr AND admin_code = :code
            LIMIT 1
        """
        params = {"yr": stats_year, "code": code}
    elif region_level == "eupmyeondong":
        prefix = code[:8]
        sql = """
            SELECT SUM(total_population) AS pop
            FROM population_stats
            WHERE stats_year = :yr AND admin_code LIKE :pfx
        """
        params = {"yr": stats_year, "pfx": f"{prefix}%"}
    elif region_level == "sigungu":
        prefix = code[:5]
        sql = """
            SELECT SUM(ps.total_population) AS pop
            FROM population_stats ps
            JOIN region_codes rc ON rc.beopjungri_code = ps.admin_code
            WHERE ps.stats_year = :yr AND rc.sigungu_code = :sg
        """
        params = {"yr": stats_year, "sg": prefix}
    elif region_level == "city":
        # 의사-시 버킷(43110 등): 동일 bucket sigungu 인구 합산
        sql = """
            SELECT SUM(ps.total_population) AS pop
            FROM population_stats ps
            JOIN region_codes rc ON rc.beopjungri_code = ps.admin_code
            WHERE ps.stats_year = :yr
              AND LPAD(
                    (FLOOR(CAST(NULLIF(TRIM(rc.sigungu_code), '') AS INTEGER) / 10) * 10)::TEXT,
                    5, '0'
                  ) = :city
        """
        params = {"yr": stats_year, "city": code}
    elif region_level == "sido":
        sql = """
            SELECT SUM(ps.total_population) AS pop
            FROM population_stats ps
            JOIN region_codes rc ON rc.beopjungri_code = ps.admin_code
            WHERE ps.stats_year = :yr AND rc.sido_code = :sido
        """
        params = {"yr": stats_year, "sido": code}
    else:
        return {}

    row = conn.execute(text(sql), params).mappings().first()
    if not row or row["pop"] is None:
        return {}
    return {"population": float(row["pop"])}


def _fetch_upper_stats_cells(
    land_conn,
    *,
    as_of: date,
    window_years: int,
    sido_code: str | None,
    col_axis: str,
) -> dict[tuple[str, str], list[dict]]:
    if not land_conn.execute(text("SELECT to_regclass('public.land_upper_stats_v2') IS NOT NULL")).scalar():
        return {}

    params = {
        "as_of": as_of,
        "wy": window_years,
        "axis": col_axis,
        "sido": sido_code,
        "sido_prefix": f"{sido_code}%" if sido_code else None,
    }
    rows = land_conn.execute(
        text(
            """
            SELECT region_level, region_code, zone_type, land_category, count, mean
            FROM land_upper_stats_v2
            WHERE as_of_month = :as_of AND window_years = :wy AND col_axis = :axis
              AND zone_type <> 'ALL' AND land_category <> 'ALL'
              AND (
                    (:sido IS NULL)
                 OR (region_level = 'sido' AND region_code = :sido)
                 OR (region_level IN ('sigungu', 'eupmyeondong', 'city')
                     AND region_code LIKE :sido_prefix)
              )
            """
        ),
        params,
    ).mappings().all()

    by_region: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        key = (str(r["region_level"]).strip(), str(r["region_code"]).strip())
        by_region.setdefault(key, []).append(dict(r))
    return by_region


def _fetch_basic_group_cells(
    land_conn,
    *,
    as_of: date,
    window_years: int,
    sido_code: str | None,
) -> dict[tuple[str, str], list[dict]]:
    """리 grain: land_basic_stats_v2 col_axis=group → region_level=beopjungri (D-029)."""
    if not land_conn.execute(text("SELECT to_regclass('public.land_basic_stats_v2') IS NOT NULL")).scalar():
        return {}

    params = {
        "as_of": as_of,
        "wy": window_years,
        "sido": sido_code,
        "sido_prefix": f"{sido_code}%" if sido_code else None,
    }
    rows = land_conn.execute(
        text(
            """
            SELECT beopjungri_code, zone_type, land_category, count, mean
            FROM land_basic_stats_v2
            WHERE as_of_month = :as_of AND window_years = :wy AND col_axis = 'group'
              AND zone_type <> 'ALL' AND land_category <> 'ALL'
              AND (:sido IS NULL OR beopjungri_code LIKE :sido_prefix)
            """
        ),
        params,
    ).mappings().all()

    by_region: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        code = str(r["beopjungri_code"]).strip()
        key = ("beopjungri", code)
        by_region.setdefault(key, []).append(
            {
                "zone_type": r["zone_type"],
                "land_category": r["land_category"],
                "count": r["count"],
                "mean": r["mean"],
            }
        )
    return by_region


def _fetch_composition_by_region(
    land_conn,
    *,
    as_of: date,
    window_years: int,
    sido_code: str | None,
    comp_rules,
) -> dict[tuple[str, str], dict]:
    by_region = _fetch_upper_stats_cells(
        land_conn, as_of=as_of, window_years=window_years, sido_code=sido_code, col_axis="category"
    )
    out: dict[tuple[str, str], dict] = {}
    for key, region_rows in by_region.items():
        feats = composition_features(region_rows, comp_rules)
        if feats:
            out[key] = feats
    return out


def _fetch_jimok_group_by_region(
    land_conn,
    *,
    as_of: date,
    window_years: int,
    sido_code: str | None,
) -> dict[tuple[str, str], dict]:
    """D-027/D-029: 지목군 구성비 + 용도×지목군 Top1~3 (upper + basic beop)."""
    by_region = _fetch_upper_stats_cells(
        land_conn, as_of=as_of, window_years=window_years, sido_code=sido_code, col_axis="group"
    )
    basic = _fetch_basic_group_cells(
        land_conn, as_of=as_of, window_years=window_years, sido_code=sido_code
    )
    for key, rows in basic.items():
        by_region.setdefault(key, []).extend(rows)

    out: dict[tuple[str, str], dict] = {}
    for key, region_rows in by_region.items():
        feats = jimok_group_features(region_rows)
        if feats:
            out[key] = feats
    return out


def _sanitize_apartment_nulls(profiles: dict[tuple[str, str], dict]) -> None:
    """D-029/D-030: 아파트 분위·단가는 해당 grain 표본 없으면 NULL. beop은 count>=15."""
    price_keys = (
        "apartment_mean",
        "apartment_median",
        "apartment_std",
        "apartment_volatility",
        "apartment_p25",
        "apartment_p75",
        "apartment_yoy",
    )
    for (level, _), feats in profiles.items():
        cnt = feats.get("apartment_count")
        min_count = 15 if level == "beopjungri" else 1
        if cnt is None or int(cnt) < min_count:
            for k in price_keys:
                feats.pop(k, None)


def _attach_mask_and_represent(feats: dict, mix: dict) -> None:
    """D-029: market_presence(0/1) + dominant_type 최상위 Feature."""
    totals = mix.get("totals_by_type") or {}
    feats["market_presence"] = {
        t: (1 if int((totals.get(t) or {}).get("count") or 0) > 0 else 0) for t in YEARLY_MIX_TYPES
    }
    if mix.get("dominant_type"):
        feats["dominant_type"] = mix["dominant_type"]


def empty_yearly_mix(years: list[int]) -> dict:
    """거래 0인 리 등 — yearly_mix 건수·금액은 0 (NULL 아님)."""
    totals = {t: {"count": 0, "amount": 0.0} for t in YEARLY_MIX_TYPES}
    by_year = {
        str(cy): {t: {"count": 0, "amount": 0.0} for t in YEARLY_MIX_TYPES} for cy in years
    }
    mix: dict = dict(by_year)
    mix["years"] = years
    mix["totals_by_type"] = totals
    mix["total_count_3y"] = 0
    mix["total_amount_3y"] = 0.0
    mix["dominant_type"] = YEARLY_MIX_TYPES[0]
    mix["count_share_by_type"] = {t: 0.0 for t in YEARLY_MIX_TYPES}
    mix["amount_share_by_type"] = {t: 0.0 for t in YEARLY_MIX_TYPES}
    return mix


# ---------------------------------------------------------------------------
# D-027: yearly_mix — 최근 완결 3개 연도 × 8대 시장유형 count/amount
# ---------------------------------------------------------------------------


def recent_complete_years(as_of: date, n: int = 3) -> list[int]:
    """as_of 연도 이전의 완결된 n개 달력 연도(예: as_of=2026-06 → 2023,2024,2025)."""
    return list(range(as_of.year - n, as_of.year))


def _fetch_land_yearly(
    land_conn, *, years: list[int], sido_code: str | None
) -> dict[tuple[str, str, int], dict]:
    rows = land_conn.execute(
        text(
            """
            SELECT beopjungri_code, calendar_year, transaction_count, amount_sum_10k
            FROM land_annual_stats
            WHERE col_axis = 'category' AND zone_type = 'ALL' AND land_category = 'ALL'
              AND calendar_year = ANY(:years)
              AND (:sido IS NULL OR substring(btrim(beopjungri_code::text) from 1 for 2) = :sido)
            """
        ),
        {"years": years, "sido": sido_code},
    ).mappings().all()

    out: dict[tuple[str, str, int], dict] = {}
    for r in rows:
        code = str(r["beopjungri_code"]).strip()
        cy = int(r["calendar_year"])
        cnt = int(r["transaction_count"] or 0)
        amt = float(r["amount_sum_10k"]) if r["amount_sum_10k"] is not None else 0.0
        for level, rc in (
            ("beopjungri", code),
            ("eupmyeondong", code[:8]),
            ("sigungu", code[:5]),
            ("sido", code[:2]),
        ):
            agg = out.setdefault((level, rc, cy), {"count": 0, "amount": 0.0})
            agg["count"] += cnt
            agg["amount"] += amt
    return out


def _fetch_region_annual_yearly(
    conn,
    *,
    table: str,
    domain_col: str,
    years: list[int],
    sido_code: str | None,
) -> dict[tuple[str, str, str, int], dict]:
    """built_annual_stats / collective_commercial_region_annual_stats / market_annual_stats
    처럼 이미 region_level×region_code×calendar_year 그레인을 갖는 mart 공용 fetch."""
    sido_prefix = f"{sido_code}%" if sido_code else None
    rows = conn.execute(
        text(
            f"""
            SELECT {domain_col} AS domain, region_level, region_code, calendar_year,
                   count, amount_sum
            FROM {table}
            WHERE calendar_year = ANY(:years)
              AND (
                    (:sido IS NULL)
                 OR (region_level = 'sido' AND region_code = :sido)
                 OR (region_level != 'sido' AND region_code LIKE :sido_prefix)
              )
            """
        ),
        {"years": years, "sido": sido_code, "sido_prefix": sido_prefix},
    ).mappings().all()

    out: dict[tuple[str, str, str, int], dict] = {}
    for r in rows:
        key = (
            str(r["domain"]).strip(),
            str(r["region_level"]).strip(),
            str(r["region_code"]).strip(),
            int(r["calendar_year"]),
        )
        out[key] = {
            "count": int(r["count"] or 0),
            "amount": float(r["amount_sum"]) if r["amount_sum"] is not None else 0.0,
        }
    return out


def build_yearly_mix(
    keys: list[tuple[str, str]],
    years: list[int],
    *,
    land_map: dict[tuple[str, str, int], dict],
    built_map: dict[tuple[str, str, str, int], dict],
    cc_map: dict[tuple[str, str, str, int], dict],
    market_map: dict[tuple[str, str, str, int], dict],
    beop_ledger_map: dict[tuple[str, int], dict[str, dict]] | None = None,
    include_empty_levels: frozenset[str] | None = None,
) -> dict[tuple[str, str], dict]:
    empty_levels = include_empty_levels or frozenset()
    beop_extra = beop_ledger_map or {}
    out: dict[tuple[str, str], dict] = {}
    for level, code in keys:
        by_year: dict[str, dict[str, dict]] = {}
        totals_by_type: dict[str, dict[str, float]] = {
            t: {"count": 0, "amount": 0.0} for t in YEARLY_MIX_TYPES
        }

        for cy in years:
            year_bucket: dict[str, dict] = {}
            for type_kr, sources in TYPE_SOURCE_MAP.items():
                count = 0
                amount = 0.0
                if level == "beopjungri" and type_kr != "토지":
                    cell = beop_extra.get((code, cy), {}).get(type_kr)
                    if cell:
                        count = int(cell["count"])
                        amount = float(cell["amount"])
                else:
                    for src, sub in sources:
                        if src == "land":
                            agg = land_map.get((level, code, cy))
                        elif src == "built":
                            agg = built_map.get((sub, level, code, cy))
                        elif src == "cc":
                            agg = cc_map.get((sub, level, code, cy))
                        else:
                            agg = market_map.get((sub, level, code, cy))
                        if agg:
                            count += agg["count"]
                            amount += agg["amount"]
                year_bucket[type_kr] = {"count": count, "amount": round(amount, 2)}
                totals_by_type[type_kr]["count"] += count
                totals_by_type[type_kr]["amount"] += amount
            by_year[str(cy)] = year_bucket

        total_count_3y = int(sum(v["count"] for v in totals_by_type.values()))
        if total_count_3y <= 0 and level not in empty_levels:
            continue
        total_amount_3y = round(sum(v["amount"] for v in totals_by_type.values()), 2)

        if total_count_3y <= 0:
            out[(level, code)] = empty_yearly_mix(years)
            continue

        dominant_type = max(totals_by_type.items(), key=lambda kv: kv[1]["count"])[0]
        count_share = {t: round(v["count"] / total_count_3y, 6) for t, v in totals_by_type.items()}
        amount_share = {
            t: round(v["amount"] / total_amount_3y, 6) if total_amount_3y > 0 else 0.0
            for t, v in totals_by_type.items()
        }

        mix: dict = dict(by_year)
        mix["years"] = years
        mix["totals_by_type"] = {
            t: {"count": int(v["count"]), "amount": round(v["amount"], 2)}
            for t, v in totals_by_type.items()
        }
        mix["total_count_3y"] = total_count_3y
        mix["total_amount_3y"] = total_amount_3y
        mix["dominant_type"] = dominant_type
        mix["count_share_by_type"] = count_share
        mix["amount_share_by_type"] = amount_share
        out[(level, code)] = mix
    return out


def upsert_profiles(
    engine: Engine,
    profiles: dict[tuple[str, str], dict],
    *,
    as_of: date,
    window_years: int,
    profile_version: str,
    batch_id: str,
) -> int:
    sql = text(
        """
        INSERT INTO regional_profile (
            profile_version, region_level, region_code, as_of_month, window_years,
            features, feature_count, builder_version, validation_status, batch_id
        ) VALUES (
            :profile_version, :level, :code, :as_of, :window_years,
            CAST(:features AS jsonb), :feature_count, :builder_version, 'PENDING', :batch_id
        )
        ON CONFLICT (profile_version, region_level, region_code, as_of_month, window_years)
        DO UPDATE SET
            features = EXCLUDED.features,
            feature_count = EXCLUDED.feature_count,
            builder_version = EXCLUDED.builder_version,
            computed_at = NOW(),
            batch_id = EXCLUDED.batch_id
        """
    )
    n = 0
    with engine.begin() as conn:
        for (level, code), feats in profiles.items():
            if not feats:
                continue
            conn.execute(
                sql,
                {
                    "profile_version": profile_version,
                    "level": level,
                    "code": code,
                    "as_of": as_of,
                    "window_years": window_years,
                    "features": json.dumps(feats, ensure_ascii=False),
                    "feature_count": len(feats),
                    "builder_version": BUILDER_VERSION,
                    "batch_id": batch_id,
                },
            )
            n += 1
    return n


def main() -> None:
    p = argparse.ArgumentParser(description="regional_profile 빌드 (충북 파일럿)")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--window-years", type=int, default=3, help="Profile 제품 창 (D-029: 기본 3)")
    p.add_argument("--profile-version", type=str, default=DEFAULT_PROFILE_VERSION)
    p.add_argument(
        "--sido-code",
        type=str,
        default=None,
        help="시도 코드 필터 (미지정=전국). 파일럿: 43",
    )
    p.add_argument("--no-escalate-land", action="store_true")
    p.add_argument("--skip-population", action="store_true")
    p.add_argument("--skip-composition", action="store_true")
    p.add_argument("--skip-jimok-group", action="store_true", help="지목군·용도×지목군 Top1~3 (D-029) 생략")
    p.add_argument("--skip-yearly-mix", action="store_true", help="3개년 8대유형 yearly_mix (D-027) 생략")
    p.add_argument("--yearly-mix-years", type=int, default=3, help="yearly_mix 최근 완결 연도 수")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    batch_id = str(uuid.uuid4())
    sido = str(args.sido_code).strip() if args.sido_code else None
    coll_eng = get_collective_engine()

    with coll_eng.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('public.market_stats') IS NOT NULL")).scalar():
            raise SystemExit("market_stats 없음 — build_land_market_stats / build_collective_market_stats 먼저")
        market_rows = _fetch_market_rows(
            conn, as_of=as_of, window_years=args.window_years, sido_code=sido
        )

    if not market_rows:
        raise SystemExit(f"market_stats 행 없음 (as_of={as_of}, sido={sido})")

    profiles = build_features_from_market(
        market_rows, escalate_land=not args.no_escalate_land
    )
    _sanitize_apartment_nulls(profiles)

    _, comp_rules = load_domain_config()

    if not args.skip_composition:
        try:
            with get_land_engine_for_region_copy().connect() as lconn:
                comp_map = _fetch_composition_by_region(
                    lconn,
                    as_of=as_of,
                    window_years=args.window_years,
                    sido_code=sido,
                    comp_rules=comp_rules,
                )
            for key, comp in comp_map.items():
                profiles.setdefault(key, {}).update(comp)
        except Exception as exc:
            log.warning("composition merge skipped: %s", exc)

    if not args.skip_jimok_group:
        try:
            with get_land_engine_for_region_copy().connect() as lconn:
                jimok_map = _fetch_jimok_group_by_region(
                    lconn, as_of=as_of, window_years=args.window_years, sido_code=sido
                )
            for key, feats in jimok_map.items():
                profiles.setdefault(key, {}).update(feats)
            beop_n = sum(1 for (lv, _) in jimok_map if lv == "beopjungri")
            log.info(
                "jimok_group/land_top merged for %s regions (beopjungri=%s)",
                len(jimok_map),
                beop_n,
            )
        except Exception as exc:
            log.warning("jimok_group merge skipped: %s", exc)

    if not args.skip_yearly_mix:
        try:
            years = recent_complete_years(as_of, args.yearly_mix_years)
            with get_land_engine_for_region_copy().connect() as lconn:
                land_map = _fetch_land_yearly(lconn, years=years, sido_code=sido)
            # D-029: land annual에만 있는 리도 프로필 시드
            for level, code, _cy in land_map:
                if level == "beopjungri":
                    profiles.setdefault((level, code), {})
            with get_built_engine().connect() as bconn:
                built_map = _fetch_region_annual_yearly(
                    bconn, table="built_annual_stats", domain_col="asset_type",
                    years=years, sido_code=sido,
                )
                with coll_eng.connect() as cconn:
                    cc_map = _fetch_region_annual_yearly(
                        cconn, table="collective_commercial_region_annual_stats", domain_col="asset_type",
                        years=years, sido_code=sido,
                    )
                    market_map = _fetch_region_annual_yearly(
                        cconn, table="market_annual_stats", domain_col="market_domain",
                        years=years, sido_code=sido,
                    )
                    beop_ledger_map = _fetch_beop_yearly_from_ledgers(
                        cconn, bconn, years=years, sido_code=sido
                    )
            _rollup_yearly_maps_to_city(land_map, built_map, cc_map, market_map)
            mix_map = build_yearly_mix(
                list(profiles.keys()),
                years,
                land_map=land_map,
                built_map=built_map,
                cc_map=cc_map,
                market_map=market_map,
                beop_ledger_map=beop_ledger_map,
                include_empty_levels=frozenset({"beopjungri", "eupmyeondong", "city"}),
            )
            for key, mix in mix_map.items():
                feats = profiles.setdefault(key, {})
                feats["yearly_mix"] = mix
                _attach_mask_and_represent(feats, mix)
            log.info(
                "yearly_mix merged for %s regions (years=%s, beop_ledger_cells=%s)",
                len(mix_map),
                years,
                len(beop_ledger_map),
            )
        except Exception as exc:
            log.warning("yearly_mix merge skipped: %s", exc)

    if not args.skip_population:
        pop_year = as_of.year - 1
        try:
            with get_land_engine_for_region_copy().connect() as lconn:
                if lconn.execute(text("SELECT to_regclass('public.population_stats') IS NOT NULL")).scalar():
                    for key in list(profiles.keys()):
                        level, code = key
                        pop = _population_for_region(
                            lconn, region_level=level, region_code=code, stats_year=pop_year
                        )
                        if pop:
                            profiles[key].update(pop)
        except Exception as exc:
            log.warning("population merge skipped: %s", exc)

    if args.dry_run:
        log.info("dry-run: would upsert %s profiles", len(profiles))
        return

    n = upsert_profiles(
        coll_eng,
        profiles,
        as_of=as_of,
        window_years=args.window_years,
        profile_version=args.profile_version,
        batch_id=batch_id,
    )
    log.info(
        "regional_profile upserted %s rows version=%s as_of=%s window=%sy sido=%s",
        n,
        args.profile_version,
        as_of,
        args.window_years,
        sido,
    )


if __name__ == "__main__":
    main()
