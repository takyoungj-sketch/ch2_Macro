"""Twin v8 — land_upper_stats / land_basic_stats / market_stats 로더."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from twin_v8.scoring import CHUNGCHEONG_SIDO, RegionProfile

log = logging.getLogger(__name__)

CHUNGCHEONG_PREFIXES = tuple(sorted(CHUNGCHEONG_SIDO))


def _sido_filter_sql(col: str = "region_code") -> str:
    parts = " OR ".join(f"{col} LIKE :sp{i}" for i in range(len(CHUNGCHEONG_PREFIXES)))
    params = {f"sp{i}": f"{p}%" for i, p in enumerate(CHUNGCHEONG_PREFIXES)}
    return parts, params


def load_land_cells_upper(
    land_eng: Engine,
    *,
    region_level: str,
    as_of_month: date,
    window_years: int,
) -> dict[str, dict[str, dict[str, Any]]]:
    """sigungu | eupmyeondong — land_upper_stats_v2."""
    sido_clause, sido_params = _sido_filter_sql("region_code")
    q = text(
        f"""
        SELECT region_code, zone_type, land_category, count, mean
        FROM land_upper_stats_v2
        WHERE as_of_month = :as_of
          AND window_years = :wy
          AND region_level = :rl
          AND zone_type <> 'ALL'
          AND land_category <> 'ALL'
          AND count > 0
          AND ({sido_clause})
        """
    )
    params = {
        "as_of": as_of_month,
        "wy": window_years,
        "rl": region_level,
        **sido_params,
    }
    with land_eng.connect() as conn:
        rows = conn.execute(q, params).mappings().all()

    out: dict[str, dict[str, dict]] = {}
    totals: dict[str, int] = {}
    for r in rows:
        rc = str(r["region_code"]).strip()
        z = str(r["zone_type"] or "").strip()
        lc = str(r["land_category"] or "").strip()
        if not z or not lc:
            continue
        ck = f"{z}|{lc}"
        cnt = int(r["count"] or 0)
        mean = float(r["mean"]) if r["mean"] is not None else None
        out.setdefault(rc, {})[ck] = {"count": cnt, "mean": mean}
        totals[rc] = totals.get(rc, 0) + cnt
    return {rc: {"cells": cells, "total_tx": totals.get(rc, 0)} for rc, cells in out.items()}


def load_land_cells_beopjungri(
    land_eng: Engine,
    *,
    as_of_month: date,
    window_years: int,
) -> dict[str, dict[str, dict[str, Any]]]:
    """리 — land_basic_stats_v2 (beopjungri 10자리)."""
    sido_clause, sido_params = _sido_filter_sql("beopjungri_code")
    q = text(
        f"""
        SELECT beopjungri_code, zone_type, land_category, count, mean
        FROM land_basic_stats_v2
        WHERE as_of_month = :as_of
          AND window_years = :wy
          AND zone_type <> 'ALL'
          AND land_category <> 'ALL'
          AND count > 0
          AND ({sido_clause})
        """
    )
    params = {"as_of": as_of_month, "wy": window_years, **sido_params}
    with land_eng.connect() as conn:
        rows = conn.execute(q, params).mappings().all()

    out: dict[str, dict[str, dict]] = {}
    totals: dict[str, int] = {}
    for r in rows:
        rc = str(r["beopjungri_code"]).strip()
        z = str(r["zone_type"] or "").strip()
        lc = str(r["land_category"] or "").strip()
        if not z or not lc:
            continue
        ck = f"{z}|{lc}"
        cnt = int(r["count"] or 0)
        mean = float(r["mean"]) if r["mean"] is not None else None
        out.setdefault(rc, {})[ck] = {"count": cnt, "mean": mean}
        totals[rc] = totals.get(rc, 0) + cnt
    return {rc: {"cells": cells, "total_tx": totals.get(rc, 0)} for rc, cells in out.items()}


def load_collective_apartment(
    coll_eng: Engine,
    *,
    region_level: str,
    as_of_month: date,
    window_years: int,
) -> dict[str, dict[str, Any]]:
    """market_stats apartment_market — p25/median/p75."""
    sido_clause, sido_params = _sido_filter_sql("region_code")
    q = text(
        f"""
        SELECT region_code, p25, median, p75, count
        FROM market_stats
        WHERE market_domain = 'apartment_market'
          AND region_level = :rl
          AND as_of_month = :as_of
          AND window_years = :wy
          AND count > 0
          AND ({sido_clause})
        """
    )
    params = {
        "rl": region_level,
        "as_of": as_of_month,
        "wy": window_years,
        **sido_params,
    }
    with coll_eng.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('public.market_stats') IS NOT NULL")).scalar():
            log.warning("market_stats 없음 — 집합 블록 0점")
            return {}
        rows = conn.execute(q, params).mappings().all()

    out: dict[str, dict] = {}
    for r in rows:
        rc = str(r["region_code"]).strip()
        out[rc] = {
            "p25": float(r["p25"]) if r["p25"] is not None else None,
            "median": float(r["median"]) if r["median"] is not None else None,
            "p75": float(r["p75"]) if r["p75"] is not None else None,
            "count": int(r["count"] or 0),
        }
    return out


def load_population_sigungu(land_eng: Engine) -> pd.Series:
    from build_twin_regions_mvp import _load_pop_by_sigungu

    with land_eng.connect() as conn:
        df = _load_pop_by_sigungu(conn)
    if df.empty:
        return pd.Series(dtype=int)
    return df.set_index("sigungu_code")["population"]


def load_population_eup(land_eng: Engine) -> pd.Series:
    from build_twin_eupmyeondong_mvp import _load_pop_by_eup

    with land_eng.connect() as conn:
        df = _load_pop_by_eup(conn)
    if df.empty:
        return pd.Series(dtype=int)
    return df.set_index("eupmyeondong_code")["population"]


def load_population_beopjungri(land_eng: Engine) -> pd.Series:
    q = text(
        """
        WITH lp0 AS (
            SELECT btrim(admin_code::text) AS beopjungri_code,
                   total_population::bigint AS pop,
                   stats_year, loaded_at
            FROM population_stats
            WHERE admin_level = 'beopjungri'
              AND total_population IS NOT NULL AND total_population > 0
        ),
        latest AS (
            SELECT DISTINCT ON (beopjungri_code) beopjungri_code, pop
            FROM lp0
            ORDER BY beopjungri_code, stats_year DESC, loaded_at DESC NULLS LAST
        )
        SELECT beopjungri_code, pop AS population FROM latest
        WHERE substring(beopjungri_code, 1, 2) IN ('30','36','43','44')
        """
    )
    with land_eng.connect() as conn:
        df = pd.read_sql(q, conn)
    if df.empty:
        return pd.Series(dtype=int)
    return df.set_index("beopjungri_code")["population"]


def load_region_meta(land_eng: Engine) -> pd.DataFrame:
    q = text(
        """
        SELECT DISTINCT ON (beopjungri_code)
            btrim(beopjungri_code::text) AS beopjungri_code,
            btrim(eupmyeondong_code::text) AS eupmyeondong_code,
            eupmyeondong_name,
            btrim(sigungu_code::text) AS sigungu_code,
            sigungu_name,
            btrim(sido_code::text) AS sido_code,
            sido_name,
            beopjungri_name
        FROM region_codes
        WHERE is_active
        ORDER BY beopjungri_code
        """
    )
    with land_eng.connect() as conn:
        return pd.read_sql(q, conn)


def build_profiles_for_level(
    *,
    region_level: str,
    land_pack: dict[str, dict],
    coll_stats: dict[str, dict],
    coll_eup_stats: dict[str, dict] | None,
    population: pd.Series,
    meta: pd.DataFrame,
) -> dict[str, RegionProfile]:
    profiles: dict[str, RegionProfile] = {}

    if region_level == "sigungu":
        meta_idx = meta.drop_duplicates("sigungu_code").set_index("sigungu_code")
    elif region_level == "eupmyeondong":
        meta_idx = meta.drop_duplicates("eupmyeondong_code").set_index("eupmyeondong_code")
    else:
        meta_idx = meta.set_index("beopjungri_code")

    for rc, pack in land_pack.items():
        rc = str(rc).strip()
        if len(rc) < 2 or rc[:2] not in CHUNGCHEONG_SIDO:
            continue
        pop = int(population.get(rc)) if rc in population.index and pd.notna(population.get(rc)) else None

        coll = coll_stats.get(rc)
        coll_src = region_level
        if region_level == "beopjungri":
            eup = rc[:8]
            coll = coll_eup_stats.get(eup) if coll_eup_stats else None
            coll_src = "eupmyeondong"

        profiles[rc] = RegionProfile(
            region_code=rc,
            region_level=region_level,
            land_cells=pack.get("cells") or {},
            land_total_tx=int(pack.get("total_tx") or 0),
            population=pop,
            collective=coll,
            collective_source_level=coll_src if region_level == "beopjungri" else None,
        )
    return profiles
