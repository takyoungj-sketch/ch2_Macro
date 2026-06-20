#!/usr/bin/env python3
"""
market_stats (+ population, 토지 composition) → regional_profile JSON features.

설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md Phase D
충북 파일럿: --sido-code 43 --profile-version v1.0-chungbuk
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
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from land_domain_extraction import composition_features, load_domain_config  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

BUILDER_VERSION = "2026.06.19"
DEFAULT_PROFILE_VERSION = "v1.0-chungbuk"

DOMAIN_FEATURES: dict[str, tuple[str, ...]] = {
    "apartment_market": ("count", "mean", "median", "std", "volatility"),
    "rowhouse_market": ("count", "mean", "median", "std", "volatility"),
    "officetel_market": ("count", "mean", "median", "std", "volatility"),
    "land_residential": ("count", "mean", "median", "std"),
    "land_commercial": ("count", "mean", "median", "std"),
    "land_industrial": ("count", "mean", "median", "std"),
    "land_agricultural": ("count", "mean", "median"),
    "land_forest": ("count", "mean", "median"),
}

DOMAIN_PREFIX: dict[str, str] = {
    "apartment_market": "apartment",
    "rowhouse_market": "rowhouse",
    "officetel_market": "officetel",
}


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
               count, mean, median, std, yoy, volatility
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
    if region_level == "eupmyeondong":
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


def _fetch_composition_by_region(
    land_conn,
    *,
    as_of: date,
    window_years: int,
    sido_code: str | None,
    comp_rules,
) -> dict[tuple[str, str], dict]:
    if not land_conn.execute(text("SELECT to_regclass('public.land_upper_stats_v2') IS NOT NULL")).scalar():
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
            SELECT region_level, region_code, zone_type, land_category, count
            FROM land_upper_stats_v2
            WHERE as_of_month = :as_of AND window_years = :wy
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

    out: dict[tuple[str, str], dict] = {}
    for key, region_rows in by_region.items():
        feats = composition_features(region_rows, comp_rules)
        if feats:
            out[key] = feats
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
    p.add_argument("--window-years", type=int, default=5)
    p.add_argument("--profile-version", type=str, default=DEFAULT_PROFILE_VERSION)
    p.add_argument("--sido-code", type=str, default="43", help="시도 코드 필터 (기본 43=충북)")
    p.add_argument("--no-escalate-land", action="store_true")
    p.add_argument("--skip-population", action="store_true")
    p.add_argument("--skip-composition", action="store_true")
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
