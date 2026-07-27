#!/usr/bin/env python3
"""
Profile-native Twin 빌더 (D-029 Phase B).

Catalog → Vector → Weight → Similarity. Feature 재생성 금지 — regional_profile JSONB만 소비.

예:
  cd pipeline
  python build_twin_profile.py --dry-run --sido-code 43
  python build_twin_profile.py --region-level sigungu --top-k 10
  python build_twin_profile.py --region-level beopjungri --top-k 3
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from db_utils import execute_sql_file, get_engine  # noqa: E402
from profile_twin import compute_similarity, load_twin_catalog, load_twin_weights, project_profile  # noqa: E402
from profile_twin.candidate import effective_scope, twin_candidate_allowed, twin_population_allowed  # noqa: E402
from region_scope import DEFAULT_SCOPE, SCOPES, ensure_region_scope_master  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ALGORITHM_VERSION = 21
DEFAULT_PROFILE_VERSION = "v2.1-national"
DEFAULT_WINDOW_YEARS = 3
def _scope_label(scope: str) -> str:
    """twin_*_mvp.sido_scope_codes VARCHAR(20) 제한."""
    return scope.upper()[:20]

TOP_K_BY_LEVEL = {"eupmyeondong": 5, "sigungu": 10, "beopjungri": 3}
DEFAULT_SCOPE_BY_LEVEL = {
    "eupmyeondong": DEFAULT_SCOPE,
    "sigungu": "national",
    "beopjungri": "same_sigungu",
}


def _load_meta(conn, region_level: str) -> dict[str, dict]:
    if region_level == "eupmyeondong":
        sql = """
            SELECT DISTINCT ON (eupmyeondong_code)
                btrim(eupmyeondong_code::text) AS region_code,
                eupmyeondong_name AS region_name,
                btrim(sigungu_code::text) AS sigungu_code,
                sigungu_name,
                btrim(sido_code::text) AS sido_code,
                sido_name
            FROM region_codes
            WHERE is_active
            ORDER BY eupmyeondong_code, beopjungri_code
        """
    elif region_level == "sigungu":
        sql = """
            SELECT DISTINCT ON (sigungu_code)
                btrim(sigungu_code::text) AS region_code,
                sigungu_name AS region_name,
                btrim(sigungu_code::text) AS sigungu_code,
                sigungu_name,
                btrim(sido_code::text) AS sido_code,
                sido_name
            FROM region_codes
            WHERE is_active
            ORDER BY sigungu_code, beopjungri_code
        """
    elif region_level == "beopjungri":
        sql = """
            SELECT DISTINCT ON (beopjungri_code)
                btrim(beopjungri_code::text) AS region_code,
                beopjungri_name AS region_name,
                btrim(sigungu_code::text) AS sigungu_code,
                sigungu_name,
                btrim(sido_code::text) AS sido_code,
                sido_name
            FROM region_codes
            WHERE is_active
              AND btrim(beopjungri_code::text) <> ''
            ORDER BY beopjungri_code
        """
    else:
        raise ValueError(f"unsupported level: {region_level}")

    rows = conn.execute(text(sql)).mappings().all()
    return {str(r["region_code"]).strip(): dict(r) for r in rows}


def _load_profiles(
    conn,
    *,
    profile_version: str,
    as_of: date,
    window_years: int,
    region_level: str,
    sido_code: str | None,
) -> list[dict]:
    params: dict[str, Any] = {
        "pv": profile_version,
        "as_of": as_of,
        "wy": window_years,
        "level": region_level,
    }
    sido_clause = ""
    if sido_code:
        sido_clause = " AND region_code LIKE :sido_prefix "
        params["sido_prefix"] = f"{sido_code}%"

    rows = conn.execute(
        text(
            f"""
            SELECT region_code, features
            FROM regional_profile
            WHERE profile_version = :pv
              AND as_of_month = :as_of
              AND window_years = :wy
              AND region_level = :level
              {sido_clause}
            """
        ),
        params,
    ).mappings().all()

    out: list[dict] = []
    for r in rows:
        feats = r["features"] or {}
        if not isinstance(feats, dict):
            continue
        out.append({"region_code": str(r["region_code"]).strip(), "features": feats})
    return out


def _detail_payload(
    sim,
    *,
    profile_version: str,
    window_years: int,
    scope: str,
    as_of: date,
) -> dict:
    return {
        "algorithm": "profile_twin_v2.1",
        "profile_version": profile_version,
        "window_years": window_years,
        "scope": scope,
        "as_of_month": as_of.isoformat(),
        "catalog_version": sim.catalog_version,
        "weight_version": sim.weight_version,
        "block_scores": sim.block_scores,
        "represent_market_adjustment": sim.represent_market_adjustment,
        "features": {
            k: {"score": v.score, "weight": v.weight, "note": v.note}
            for k, v in sim.score_detail.items()
        },
    }


def _build_twin_rows(
    profiles: list[dict],
    meta: dict[str, dict],
    *,
    region_level: str,
    top_k: int,
    scope: str,
    profile_version: str,
    window_years: int,
    as_of: date,
    weights,
) -> list[dict]:
    catalog = load_twin_catalog()
    vectors = [
        project_profile(
            p["features"],
            region_level=region_level,
            region_code=p["region_code"],
            catalog=catalog,
        )
        for p in profiles
    ]

    rows: list[dict] = []
    for anchor in vectors:
        am = meta.get(anchor.region_code)
        if not am:
            continue
        pop_a = anchor.values.get("population")

        scored: list[tuple[str, float, dict]] = []
        for twin in vectors:
            if twin.region_code == anchor.region_code:
                continue
            tm = meta.get(twin.region_code)
            if not tm:
                continue
            if not twin_candidate_allowed(
                region_level=region_level,
                anchor_meta=am,
                twin_meta=tm,
                scope=scope,
            ):
                continue
            if not twin_population_allowed(
                pop_a,
                twin.values.get("population"),
                weights=weights,
            ):
                continue

            sim = compute_similarity(anchor, twin, catalog=catalog, weights=weights)
            if sim.similarity <= 0:
                continue
            detail = _detail_payload(
                sim,
                profile_version=profile_version,
                window_years=window_years,
                scope=scope,
                as_of=as_of,
            )
            scored.append((twin.region_code, sim.similarity, detail))

        scored.sort(key=lambda x: (-x[1], x[0]))
        for rank, (twin_code, score, detail) in enumerate(scored[:top_k], start=1):
            tm = meta[twin_code]
            rows.append(_format_row(region_level, rank, anchor.region_code, am, twin_code, tm, score, detail))
    return rows


def _format_row(
    region_level: str,
    rank: int,
    anchor_code: str,
    am: dict,
    twin_code: str,
    tm: dict,
    score: float,
    detail: dict,
) -> dict:
    base = {
        "rank": rank,
        "similarity_score": round(score, 10),
        "detail_scores": json.dumps(detail, ensure_ascii=False),
        "anchor_sido_code": str(am["sido_code"]),
        "anchor_sido_name": str(am["sido_name"]),
        "anchor_sigungu_code": str(am["sigungu_code"]),
        "anchor_sigungu_name": str(am["sigungu_name"]),
        "twin_sido_code": str(tm["sido_code"]),
        "twin_sido_name": str(tm["sido_name"]),
        "twin_sigungu_code": str(tm["sigungu_code"]),
        "twin_sigungu_name": str(tm["sigungu_name"]),
    }
    if region_level == "eupmyeondong":
        return {
            **base,
            "anchor_eupmyeondong_code": anchor_code,
            "anchor_eupmyeondong_name": str(am["region_name"]),
            "twin_eupmyeondong_code": twin_code,
            "twin_eupmyeondong_name": str(tm["region_name"]),
        }
    if region_level == "sigungu":
        return {
            **base,
            "anchor_sigungu_code": anchor_code,
            "anchor_sigungu_name": str(am["region_name"]),
            "twin_sigungu_code": twin_code,
            "twin_sigungu_name": str(tm["region_name"]),
        }
    return {
        **base,
        "region_level": "beopjungri",
        "anchor_region_code": anchor_code,
        "anchor_region_name": str(am["region_name"]),
        "twin_region_code": twin_code,
        "twin_region_name": str(tm["region_name"]),
        "confidence_score": round(min(100.0, score * 100.0), 2),
    }


INSERT_EUP = text(
    """
    INSERT INTO twin_eupmyeondong_neighbor_mvp (
        batch_key, algorithm_version, sido_scope_codes,
        anchor_eupmyeondong_code, anchor_eupmyeondong_name,
        anchor_sigungu_code, anchor_sigungu_name,
        anchor_sido_code, anchor_sido_name,
        rank,
        twin_eupmyeondong_code, twin_eupmyeondong_name,
        twin_sigungu_code, twin_sigungu_name,
        twin_sido_code, twin_sido_name,
        similarity_score, detail_scores
    ) VALUES (
        :batch_key, :algorithm_version, :sido_scope_codes,
        :anchor_eupmyeondong_code, :anchor_eupmyeondong_name,
        :anchor_sigungu_code, :anchor_sigungu_name,
        :anchor_sido_code, :anchor_sido_name,
        :rank,
        :twin_eupmyeondong_code, :twin_eupmyeondong_name,
        :twin_sigungu_code, :twin_sigungu_name,
        :twin_sido_code, :twin_sido_name,
        :similarity_score, CAST(:detail_scores AS jsonb)
    )
    """
)

INSERT_SIGUNGU = text(
    """
    INSERT INTO twin_region_neighbor_mvp (
        batch_key, algorithm_version, sido_scope_codes,
        anchor_sigungu_code, anchor_sigungu_name,
        anchor_sido_code, anchor_sido_name,
        rank,
        twin_sigungu_code, twin_sigungu_name,
        twin_sido_code, twin_sido_name,
        similarity_score, detail_scores
    ) VALUES (
        :batch_key, :algorithm_version, :sido_scope_codes,
        :anchor_sigungu_code, :anchor_sigungu_name,
        :anchor_sido_code, :anchor_sido_name,
        :rank,
        :twin_sigungu_code, :twin_sigungu_name,
        :twin_sido_code, :twin_sido_name,
        :similarity_score, CAST(:detail_scores AS jsonb)
    )
    """
)

INSERT_BEOP = text(
    """
    INSERT INTO twin_neighbor_v8 (
        batch_key, algorithm_version, scope_label, region_level,
        anchor_region_code, anchor_region_name,
        anchor_sigungu_code, anchor_sigungu_name,
        anchor_sido_code, anchor_sido_name,
        rank,
        twin_region_code, twin_region_name,
        twin_sigungu_code, twin_sigungu_name,
        twin_sido_code, twin_sido_name,
        similarity_score, confidence_score, detail_scores
    ) VALUES (
        :batch_key, :algorithm_version, :scope_label, :region_level,
        :anchor_region_code, :anchor_region_name,
        :anchor_sigungu_code, :anchor_sigungu_name,
        :anchor_sido_code, :anchor_sido_name,
        :rank,
        :twin_region_code, :twin_region_name,
        :twin_sigungu_code, :twin_sigungu_name,
        :twin_sido_code, :twin_sido_name,
        :similarity_score, :confidence_score, CAST(:detail_scores AS jsonb)
    )
    """
)


def _insert_rows(
    region_level: str,
    twin_rows: list[dict],
    *,
    batch_key: str,
    scope: str,
    coll_eng,
    main_eng,
    skip_ddl: bool,
) -> None:
    ins_map: dict[str, tuple[Any, Any]] = {
        "eupmyeondong": (INSERT_EUP, coll_eng),
        "sigungu": (INSERT_SIGUNGU, coll_eng),
        "beopjungri": (INSERT_BEOP, main_eng),
    }
    ins_sql, eng = ins_map[region_level]
    if region_level == "beopjungri" and not skip_ddl:
        ddl = REPO / "db" / "031_twin_neighbor_v8.sql"
        if ddl.is_file():
            execute_sql_file(main_eng, str(ddl))

    payload = [
        {
            **r,
            "batch_key": batch_key,
            "algorithm_version": ALGORITHM_VERSION,
            "sido_scope_codes": _scope_label(scope),
            "scope_label": "PTWIN",
        }
        for r in twin_rows
    ]
    with eng.begin() as conn:
        for i in range(0, len(payload), 500):
            conn.execute(ins_sql, payload[i : i + 500])
    table = {
        "eupmyeondong": "twin_eupmyeondong_neighbor_mvp",
        "sigungu": "twin_region_neighbor_mvp",
        "beopjungri": "twin_neighbor_v8",
    }[region_level]
    log.info("%s inserted %s rows batch_key=%s", table, len(payload), batch_key)


def main() -> None:
    p = argparse.ArgumentParser(description="Profile-native Twin (Catalog engine)")
    p.add_argument("--profile-version", type=str, default=DEFAULT_PROFILE_VERSION)
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--window-years", type=int, default=DEFAULT_WINDOW_YEARS)
    p.add_argument("--region-level", type=str, default="eupmyeondong")
    p.add_argument("--sido-code", type=str, default=None)
    p.add_argument("--top-k", type=int, default=None)
    p.add_argument("--scope", type=str, default=None, choices=(*SCOPES, "same_sigungu"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-ddl", action="store_true")
    p.add_argument("--skip-scope-ddl", action="store_true")
    args = p.parse_args()

    if args.region_level not in ("eupmyeondong", "sigungu", "beopjungri"):
        raise SystemExit("eupmyeondong|sigungu|beopjungri 만 지원")

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    top_k = args.top_k if args.top_k is not None else TOP_K_BY_LEVEL[args.region_level]
    scope = effective_scope(
        args.region_level,
        args.scope or DEFAULT_SCOPE_BY_LEVEL[args.region_level],
    )
    batch_key = (
        f"ptwin_{args.region_level}_{scope}_{args.profile_version}_"
        f"{as_of:%Y%m}_w{args.window_years}_{uuid.uuid4().hex[:8]}"
    )
    weights = load_twin_weights()

    coll = get_collective_engine()
    land = get_land_engine_for_region_copy()
    main = get_engine()

    scope_ddl = REPO / "db" / "047_region_scope_master.sql"
    if not args.skip_scope_ddl and scope_ddl.is_file():
        ensure_region_scope_master(coll, ddl_path=str(scope_ddl))

    with coll.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('public.regional_profile') IS NOT NULL")).scalar():
            raise SystemExit("regional_profile 없음")
        profiles = _load_profiles(
            conn,
            profile_version=args.profile_version,
            as_of=as_of,
            window_years=args.window_years,
            region_level=args.region_level,
            sido_code=args.sido_code,
        )

    if not profiles:
        raise SystemExit(
            f"Profile 없음: {args.profile_version} level={args.region_level} as_of={as_of}"
        )

    with land.connect() as lconn:
        meta = _load_meta(lconn, args.region_level)

    twin_rows = _build_twin_rows(
        profiles,
        meta,
        region_level=args.region_level,
        top_k=top_k,
        scope=scope,
        profile_version=args.profile_version,
        window_years=args.window_years,
        as_of=as_of,
        weights=weights,
    )

    log.info(
        "batch=%s profile=%s level=%s scope=%s anchors=%s twin_rows=%s dry_run=%s",
        batch_key,
        args.profile_version,
        args.region_level,
        scope,
        len(profiles),
        len(twin_rows),
        args.dry_run,
    )

    if args.dry_run or not twin_rows:
        return

    _insert_rows(
        args.region_level,
        twin_rows,
        batch_key=batch_key,
        scope=scope,
        coll_eng=coll,
        main_eng=main,
        skip_ddl=args.skip_ddl,
    )


if __name__ == "__main__":
    main()
