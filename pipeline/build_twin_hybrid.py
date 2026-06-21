#!/usr/bin/env python3
"""
Hybrid Twin (D-023) — 토지 legacy 50% + 집합 market 30% + Profile meta 20%.

입력:
  - land_transactions (zone×지목 share, median price)
  - regional_profile (collective + population/land meta, composition 제외)

출력: twin_eupmyeondong_neighbor_mvp (algorithm_version=6)

예:
  cd pipeline
  python build_twin_hybrid.py --profile-version v1.1-national --window-years 5
  python build_twin_hybrid.py --dry-run --sido-code 43
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from build_twin_eupmyeondong_mvp import (  # noqa: E402
    _cosine_dense,
    _load_cell_counts,
    _load_eup_meta,
    _load_median_prices,
    _load_pop_by_eup,
    _normalize_share_wide,
    _pass_pop,
    _price_sim,
)
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from sido_adjacency import allowed_twin_sidoes  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ALGORITHM_VERSION = 6
SIDO_SCOPE_LABEL = "HYBRID_NAT_ADJ"

W_LAND_DEFAULT = 0.50
W_COLL_DEFAULT = 0.30
W_PROF_DEFAULT = 0.20

LAND_W_STRUCT = 0.72
LAND_W_PRICE = 0.28

COLLECTIVE_KEYS = (
    "apartment_mean",
    "apartment_count",
    "apartment_volatility",
    "rowhouse_mean",
    "rowhouse_count",
    "rowhouse_volatility",
    "officetel_mean",
    "officetel_count",
    "officetel_volatility",
)

PROFILE_META_KEYS = (
    "population",
    "population_density",
    "land_residential_mean",
    "land_commercial_mean",
    "land_industrial_mean",
)

ACTIVITY_KEYS = ("land_residential_count", "apartment_count")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _zscore_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        s = out[col]
        if s.notna().sum() > 1:
            mu, sd = float(s.mean()), float(s.std(ddof=0))
            out[col] = (s - mu) / sd if sd > 1e-12 else s * 0.0
        else:
            out[col] = s.fillna(0.0)
    return out.fillna(0.0)


def _load_profiles(
    conn,
    *,
    profile_version: str,
    as_of,
    window_years: int,
    sido_code: str | None,
) -> pd.DataFrame:
    params: dict = {
        "pv": profile_version,
        "as_of": as_of,
        "wy": window_years,
    }
    sido_clause = ""
    if sido_code:
        sido_clause = " AND region_code LIKE :sido_prefix "
        params["sido_prefix"] = f"{sido_code}%"

    q = text(
        f"""
        SELECT region_code, features
        FROM regional_profile
        WHERE profile_version = :pv
          AND as_of_month = :as_of
          AND window_years = :wy
          AND region_level = 'eupmyeondong'
          {sido_clause}
        """
    )
    rows = conn.execute(q, params).mappings().all()
    records = []
    for r in rows:
        code = str(r["region_code"]).strip()
        feats = r["features"] or {}
        if not isinstance(feats, dict):
            continue
        row: dict = {"eupmyeondong_code": code}
        for k in (*COLLECTIVE_KEYS, *PROFILE_META_KEYS, *ACTIVITY_KEYS):
            v = feats.get(k)
            if v is not None and isinstance(v, (int, float)):
                row[k] = float(v)
        records.append(row)
    return pd.DataFrame(records)


def _land_score(
    share: pd.DataFrame,
    median_price: pd.Series,
    anchor: str,
    twin: str,
) -> tuple[float, dict]:
    if anchor not in share.index or twin not in share.index:
        return 0.0, {}
    va = share.loc[anchor].to_numpy(dtype=np.float64, copy=False)
    vb = share.loc[twin].to_numpy(dtype=np.float64, copy=False)
    cos = _cosine_dense(va, vb)
    med_pa = median_price.get(anchor)
    med_pb = median_price.get(twin)
    log1pa = float(np.log1p(med_pa)) if med_pa is not None and not pd.isna(med_pa) else None
    log1pb = float(np.log1p(med_pb)) if med_pb is not None and not pd.isna(med_pb) else None
    p_sim = _price_sim(log1pa, log1pb)
    s_land = LAND_W_STRUCT * cos + LAND_W_PRICE * p_sim
    return float(s_land), {
        "cosine_structure": round(cos, 6),
        "price_similarity": round(p_sim, 6),
    }


def _build_twin_rows(
    *,
    share: pd.DataFrame,
    land_totals: dict[str, int],
    median_price: pd.Series,
    profile_df: pd.DataFrame,
    coll_z: pd.DataFrame,
    prof_z: pd.DataFrame,
    activity: pd.Series,
    population: pd.Series,
    meta: pd.DataFrame,
    min_tx: int,
    min_activity: float,
    top_k: int,
    pop_tol: float,
    w_land: float,
    w_coll: float,
    w_prof: float,
    profile_version: str,
    as_of,
    window_years: int,
) -> list[dict]:
    meta_idx = meta.set_index("eupmyeondong_code")
    codes = [str(c).strip() for c in profile_df["eupmyeondong_code"].tolist()]
    code_to_i = {c: i for i, c in enumerate(codes)}

    coll_np = coll_z.to_numpy()
    prof_np = prof_z.to_numpy()

    eligible = [
        c
        for c in codes
        if land_totals.get(c, 0) >= min_tx
        and activity.get(c, 0) >= min_activity
        and c in meta_idx.index
        and c in share.index
    ]
    log.info("hybrid twin eligible=%s / profile=%s", len(eligible), len(codes))

    rows: list[dict] = []
    for anchor in eligible:
        ai = code_to_i[anchor]
        anchor_meta = meta_idx.loc[anchor]
        anchor_sido = str(anchor_meta["sido_code"]).strip()[:2]
        allowed = allowed_twin_sidoes(anchor_sido)
        pop_a = float(population.get(anchor)) if pd.notna(population.get(anchor)) else None

        scores: list[tuple[str, float, dict]] = []
        for cand in eligible:
            if cand == anchor:
                continue
            cand_meta = meta_idx.loc[cand]
            cand_sido = str(cand_meta["sido_code"]).strip()[:2]
            if cand_sido not in allowed:
                continue
            pop_b = float(population.get(cand)) if pd.notna(population.get(cand)) else None
            if pop_a and pop_b and not _pass_pop(pop_a, pop_b, pop_tol):
                continue

            ci = code_to_i[cand]
            s_land, land_detail = _land_score(share, median_price, anchor, cand)
            s_coll = _cosine(coll_np[ai], coll_np[ci])
            s_prof = _cosine(prof_np[ai], prof_np[ci])
            final = w_land * s_land + w_coll * s_coll + w_prof * s_prof
            if final <= 0:
                continue

            detail = {
                "algorithm": "hybrid_v1",
                "profile_version": profile_version,
                "as_of_month": str(as_of),
                "window_years": window_years,
                "s_land": round(s_land, 6),
                "s_collective": round(s_coll, 6),
                "s_profile": round(s_prof, 6),
                "similarity_final": round(final, 6),
                "weights": {"land": w_land, "collective": w_coll, "profile": w_prof},
                **land_detail,
            }
            scores.append((cand, final, detail))

        scores.sort(key=lambda x: x[1], reverse=True)
        for rank, (twin_code, score, detail) in enumerate(scores[:top_k], start=1):
            tm = meta_idx.loc[twin_code]
            rows.append(
                {
                    "anchor_eupmyeondong_code": anchor,
                    "anchor_eupmyeondong_name": str(anchor_meta["eupmyeondong_name"]),
                    "anchor_sigungu_code": str(anchor_meta["sigungu_code"]),
                    "anchor_sigungu_name": str(anchor_meta["sigungu_name"]),
                    "anchor_sido_code": str(anchor_meta["sido_code"]),
                    "anchor_sido_name": str(anchor_meta["sido_name"]),
                    "rank": rank,
                    "twin_eupmyeondong_code": twin_code,
                    "twin_eupmyeondong_name": str(tm["eupmyeondong_name"]),
                    "twin_sigungu_code": str(tm["sigungu_code"]),
                    "twin_sigungu_name": str(tm["sigungu_name"]),
                    "twin_sido_code": str(tm["sido_code"]),
                    "twin_sido_name": str(tm["sido_name"]),
                    "similarity_score": round(score, 10),
                    "detail_scores": json.dumps(detail, ensure_ascii=False),
                }
            )
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="Hybrid Twin — land 50% + collective 30% + profile 20%")
    p.add_argument("--profile-version", type=str, default="v1.1-national")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--window-years", type=int, default=5)
    p.add_argument("--sido-code", type=str, default=None, help="스모크: 시도 한정")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--min-tx", type=int, default=20, help="토지 legacy 최소 거래")
    p.add_argument("--min-activity", type=float, default=15.0)
    p.add_argument("--pop-tolerance-rel", type=float, default=0.4)
    p.add_argument("--w-land", type=float, default=W_LAND_DEFAULT)
    p.add_argument("--w-coll", type=float, default=W_COLL_DEFAULT)
    p.add_argument("--w-prof", type=float, default=W_PROF_DEFAULT)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    w_sum = args.w_land + args.w_coll + args.w_prof
    w_land = args.w_land / w_sum
    w_coll = args.w_coll / w_sum
    w_prof = args.w_prof / w_sum

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    year_from = as_of.year - int(args.window_years) + 1
    batch_key = f"hybrid_{args.profile_version}_{as_of:%Y%m}_w{args.window_years}_{uuid.uuid4().hex[:8]}"

    coll = get_collective_engine()
    land = get_land_engine_for_region_copy()

    with coll.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('public.regional_profile') IS NOT NULL")).scalar():
            raise SystemExit("regional_profile 없음")
        profile_df = _load_profiles(
            conn,
            profile_version=args.profile_version,
            as_of=as_of,
            window_years=args.window_years,
            sido_code=args.sido_code,
        )

    if profile_df.empty:
        raise SystemExit(
            f"Profile 행 없음: {args.profile_version} as_of={as_of} window={args.window_years}"
        )

    with land.connect() as lconn:
        meta = _load_eup_meta(lconn)
        cells = _load_cell_counts(lconn, year_from)
        med = _load_median_prices(lconn, year_from)
        pop_df = _load_pop_by_eup(lconn)

    if cells.empty:
        raise SystemExit("land_transactions 읍면동 셀 집계 결과가 비었습니다.")

    share, land_totals = _normalize_share_wide(cells)
    median_series = (
        med.set_index("eupmyeondong_code")["median_up"] if not med.empty else pd.Series(dtype=float)
    )
    pop_from_land = (
        pop_df.set_index("eupmyeondong_code")["population"] if not pop_df.empty else pd.Series(dtype=float)
    )

    profile_df = profile_df.merge(meta, on="eupmyeondong_code", how="inner")

    coll_cols = [k for k in COLLECTIVE_KEYS if k in profile_df.columns]
    prof_cols = [k for k in PROFILE_META_KEYS if k in profile_df.columns]
    if not coll_cols:
        raise SystemExit("collective feature 없음 — regional_profile rebuild 필요")
    if not prof_cols:
        raise SystemExit("profile meta feature 없음 — regional_profile rebuild 필요")

    coll_z = _zscore_frame(profile_df[coll_cols].astype(float))
    prof_z = _zscore_frame(profile_df[prof_cols].astype(float))
    activity = profile_df[[c for c in ACTIVITY_KEYS if c in profile_df.columns]].fillna(0).sum(axis=1)
    activity.index = profile_df["eupmyeondong_code"].values

    if "population" in profile_df.columns:
        population = profile_df.set_index("eupmyeondong_code")["population"].astype(float)
    else:
        population = pop_from_land

    twin_rows = _build_twin_rows(
        share=share,
        land_totals=land_totals,
        median_price=median_series,
        profile_df=profile_df,
        coll_z=coll_z,
        prof_z=prof_z,
        activity=activity,
        population=population,
        meta=meta,
        min_tx=args.min_tx,
        min_activity=args.min_activity,
        top_k=args.top_k,
        pop_tol=args.pop_tolerance_rel,
        w_land=w_land,
        w_coll=w_coll,
        w_prof=w_prof,
        profile_version=args.profile_version,
        as_of=as_of,
        window_years=args.window_years,
    )

    log.info(
        "batch=%s hybrid profile=%s twin_rows=%s dry_run=%s",
        batch_key,
        args.profile_version,
        len(twin_rows),
        args.dry_run,
    )

    if args.dry_run or not twin_rows:
        return

    ins = text(
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

    payload = [
        {
            **r,
            "batch_key": batch_key,
            "algorithm_version": ALGORITHM_VERSION,
            "sido_scope_codes": SIDO_SCOPE_LABEL,
        }
        for r in twin_rows
    ]

    with coll.begin() as conn:
        for chunk_start in range(0, len(payload), 500):
            chunk = payload[chunk_start : chunk_start + 500]
            for row in chunk:
                conn.execute(ins, row)

    log.info("twin_eupmyeondong_neighbor_mvp hybrid inserted %s rows batch_key=%s", len(payload), batch_key)


if __name__ == "__main__":
    main()
