#!/usr/bin/env python3
"""
Twin v8 빌더 — 충청권 (30·36·43·44), 시군구·읍면동·리.

  cd pipeline
  python build_twin_v8.py
  python build_twin_v8.py --dry-run --top-k 10
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

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from db_utils import get_engine, execute_sql_file  # noqa: E402
from twin_v8.loaders import (  # noqa: E402
    build_profiles_for_level,
    load_collective_apartment,
    load_land_cells_beopjungri,
    load_land_cells_upper,
    load_population_beopjungri,
    load_population_eup,
    load_population_sigungu,
    load_region_meta,
)
from twin_v8.scoring import (  # noqa: E402
    ALGORITHM_VERSION,
    TOP_N_BY_LEVEL,
    compute_pair_scores,
    pass_population_ratio,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SCOPE_LABEL = "충청권"
INSERT_SQL = text(
    """
    INSERT INTO twin_neighbor_v8 (
        batch_key, algorithm_version, scope_label,
        region_level, anchor_region_code, anchor_region_name,
        anchor_sigungu_code, anchor_sigungu_name,
        anchor_sido_code, anchor_sido_name,
        rank, twin_region_code, twin_region_name,
        twin_sigungu_code, twin_sigungu_name,
        twin_sido_code, twin_sido_name,
        similarity_score, confidence_score, detail_scores, explanation_ko
    ) VALUES (
        :batch_key, :algorithm_version, :scope_label,
        :region_level, :anchor_region_code, :anchor_region_name,
        :anchor_sigungu_code, :anchor_sigungu_name,
        :anchor_sido_code, :anchor_sido_name,
        :rank, :twin_region_code, :twin_region_name,
        :twin_sigungu_code, :twin_sigungu_name,
        :twin_sido_code, :twin_sido_name,
        :similarity_score, :confidence_score, CAST(:detail_scores AS jsonb), :explanation_ko
    )
    """
)


def _meta_row(meta_df, code: str, level: str) -> dict | None:
    if level == "sigungu":
        rows = meta_df[meta_df["sigungu_code"].astype(str).str.strip() == code]
        if rows.empty:
            return None
        r = rows.iloc[0]
        return {
            "name": str(r["sigungu_name"]),
            "sigungu_code": code,
            "sigungu_name": str(r["sigungu_name"]),
            "sido_code": str(r["sido_code"]).strip(),
            "sido_name": str(r["sido_name"]),
        }
    if level == "eupmyeondong":
        rows = meta_df[meta_df["eupmyeondong_code"].astype(str).str.strip() == code]
        if rows.empty:
            return None
        r = rows.iloc[0]
        return {
            "name": str(r["eupmyeondong_name"]),
            "sigungu_code": str(r["sigungu_code"]).strip(),
            "sigungu_name": str(r["sigungu_name"]),
            "sido_code": str(r["sido_code"]).strip(),
            "sido_name": str(r["sido_name"]),
        }
    rows = meta_df[meta_df["beopjungri_code"].astype(str).str.strip() == code]
    if rows.empty:
        return None
    r = rows.iloc[0]
    bn = str(r.get("beopjungri_name") or r["eupmyeondong_name"])
    return {
        "name": bn,
        "sigungu_code": str(r["sigungu_code"]).strip(),
        "sigungu_name": str(r["sigungu_name"]),
        "sido_code": str(r["sido_code"]).strip(),
        "sido_name": str(r["sido_name"]),
    }


def _pair_rows(
    profiles: dict,
    meta_df,
    *,
    region_level: str,
    top_k: int,
    min_land_tx: int,
) -> list[dict]:
    codes = sorted(
        c
        for c, p in profiles.items()
        if p.land_total_tx >= min_land_tx and len(p.land_cells) >= 1
    )

    # 리: 충청 전역 O(n²) 방지 — 동일 시군구(코드 앞 5자) 내 후보만
    if region_level == "beopjungri":
        by_sg: dict[str, list[str]] = {}
        for c in codes:
            by_sg.setdefault(c[:5], []).append(c)
        code_groups = list(by_sg.values())
    else:
        code_groups = [codes]

    rows: list[dict] = []
    for group in code_groups:
        for anchor_code in group:
            anchor = profiles[anchor_code]
            am = _meta_row(meta_df, anchor_code, region_level)
            if am is None:
                continue
            scored: list[tuple[float, str, object]] = []
            for twin_code in group:
                if twin_code == anchor_code:
                    continue
                twin = profiles[twin_code]
                if not pass_population_ratio(anchor.population, twin.population):
                    continue
                result = compute_pair_scores(anchor, twin)
                if result is None:
                    continue
                scored.append((result.twin_score, twin_code, result))
            scored.sort(key=lambda x: (-x[0], x[1]))
            for rank, (_, twin_code, result) in enumerate(scored[:top_k], start=1):
                tm = _meta_row(meta_df, twin_code, region_level)
                if tm is None:
                    continue
                rows.append(
                    {
                        "region_level": region_level,
                        "anchor_region_code": anchor_code,
                        "anchor_region_name": am["name"],
                        "anchor_sigungu_code": am["sigungu_code"],
                        "anchor_sigungu_name": am["sigungu_name"],
                        "anchor_sido_code": am["sido_code"],
                        "anchor_sido_name": am["sido_name"],
                        "rank": rank,
                        "twin_region_code": twin_code,
                        "twin_region_name": tm["name"],
                        "twin_sigungu_code": tm["sigungu_code"],
                        "twin_sigungu_name": tm["sigungu_name"],
                        "twin_sido_code": tm["sido_code"],
                        "twin_sido_name": tm["sido_name"],
                        "similarity_score": result.twin_score,
                        "confidence_score": result.confidence,
                        "detail_scores": json.dumps(result.detail, ensure_ascii=False),
                        "explanation_ko": result.explanation_ko,
                    }
                )
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="Twin v8 — 충청권 빌더")
    p.add_argument("--as-of", default=None, help="YYYY-MM-DD (land_upper as_of_month)")
    p.add_argument("--window-years", type=int, default=5)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--min-land-tx", type=int, default=15, help="앵커 최소 토지 거래")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-ddl", action="store_true")
    p.add_argument("--batch-key", default=None)
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    batch_key = args.batch_key or f"twin_v8_{as_of.strftime('%Y%m')}_w{args.window_years}_{uuid.uuid4().hex[:8]}"

    land_eng = get_land_engine_for_region_copy()
    coll_eng = get_collective_engine()
    twin_eng = get_engine()

    ddl = REPO / "db" / "031_twin_neighbor_v8.sql"
    if not args.skip_ddl and ddl.is_file():
        execute_sql_file(twin_eng, str(ddl))
        log.info("DDL applied: %s", ddl.name)

    meta = load_region_meta(land_eng)
    pop_sg = load_population_sigungu(land_eng)
    pop_eup = load_population_eup(land_eng)
    pop_ri = load_population_beopjungri(land_eng)

    coll_sg = load_collective_apartment(
        coll_eng, region_level="sigungu", as_of_month=as_of, window_years=args.window_years
    )
    coll_eup = load_collective_apartment(
        coll_eng, region_level="eupmyeondong", as_of_month=as_of, window_years=args.window_years
    )

    all_rows: list[dict] = []

    for level, land_loader, pop, coll_level in (
        ("sigungu", lambda: load_land_cells_upper(land_eng, region_level="sigungu", as_of_month=as_of, window_years=args.window_years), pop_sg, "sigungu"),
        ("eupmyeondong", lambda: load_land_cells_upper(land_eng, region_level="eupmyeondong", as_of_month=as_of, window_years=args.window_years), pop_eup, "eupmyeondong"),
        ("beopjungri", lambda: load_land_cells_beopjungri(land_eng, as_of_month=as_of, window_years=args.window_years), pop_ri, "eupmyeondong"),
    ):
        land_pack = land_loader()
        coll = coll_sg if coll_level == "sigungu" else coll_eup
        profiles = build_profiles_for_level(
            region_level=level,
            land_pack=land_pack,
            coll_stats=coll if level != "beopjungri" else {},
            coll_eup_stats=coll_eup if level == "beopjungri" else None,
            population=pop,
            meta=meta,
        )
        n = len(profiles)
        level_rows = _pair_rows(
            profiles,
            meta,
            region_level=level,
            top_k=args.top_k,
            min_land_tx=args.min_land_tx,
        )
        log.info(
            "level=%s profiles=%s twin_rows=%s top_n=%s",
            level,
            n,
            len(level_rows),
            TOP_N_BY_LEVEL.get(level),
        )
        all_rows.extend(level_rows)

    log.info("batch=%s total_rows=%s dry_run=%s", batch_key, len(all_rows), args.dry_run)
    if args.dry_run or not all_rows:
        return

    payloads = [
        {
            **row,
            "batch_key": batch_key,
            "algorithm_version": ALGORITHM_VERSION,
            "scope_label": SCOPE_LABEL,
        }
        for row in all_rows
    ]
    with twin_eng.begin() as conn:
        for i in range(0, len(payloads), 500):
            conn.execute(INSERT_SQL, payloads[i : i + 500])
    log.info("inserted %s rows into twin_neighbor_v8", len(payloads))


if __name__ == "__main__":
    main()
