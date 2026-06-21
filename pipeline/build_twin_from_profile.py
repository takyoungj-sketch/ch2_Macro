#!/usr/bin/env python3
"""
Regional Profile → Twin (읍면동) — Profile 소비, Feature 재생성 금지 (D-017).

입력: regional_profile (eupmyeondong grain, profile_version·as_of·window 고정)
출력: twin_eupmyeondong_neighbor_mvp (algorithm_version=5)

예:
  cd pipeline
  python build_twin_from_profile.py --profile-version v1.1-national --window-years 5
  python build_twin_from_profile.py --dry-run --sido-code 43
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
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from sido_adjacency import allowed_twin_sidoes  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ALGORITHM_VERSION = 5
SIDO_SCOPE_LABEL = "PROFILE_NAT_ADJ"

STRUCT_KEYS = (
    "ratio_residential_zone",
    "ratio_commercial_zone",
    "ratio_agri_zone",
    "ratio_land_danji",
    "ratio_land_rice",
    "ratio_land_forest",
)

PRICE_KEYS = (
    "land_residential_mean",
    "land_commercial_mean",
    "land_industrial_mean",
    "apartment_mean",
)

ACTIVITY_KEYS = (
    "land_residential_count",
    "apartment_count",
)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _price_sim(log_a: float | None, log_b: float | None, denom: float = 2.5) -> float:
    if log_a is None or log_b is None:
        return 0.0
    d = abs(log_a - log_b)
    return float(max(0.0, 1.0 - min(1.0, d / denom)))


def _pass_pop(pa: float | None, pb: float | None, tol_rel: float) -> bool:
    if pa is None or pb is None or pa <= 0 or pb <= 0:
        return False
    lo, hi = 1.0 - tol_rel, 1.0 + tol_rel
    r = pb / pa
    if lo <= r <= hi:
        return True
    r2 = pa / pb
    return lo <= r2 <= hi


def _load_eup_meta(conn) -> pd.DataFrame:
    q = text(
        """
        SELECT DISTINCT ON (eupmyeondong_code)
            btrim(eupmyeondong_code::text) AS eupmyeondong_code,
            eupmyeondong_name,
            btrim(sigungu_code::text) AS sigungu_code,
            sigungu_name,
            btrim(sido_code::text) AS sido_code,
            sido_name
        FROM region_codes
        WHERE is_active
        ORDER BY eupmyeondong_code, beopjungri_code
        """
    )
    return pd.read_sql(q, conn)


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
        row = {"eupmyeondong_code": code}
        for k in (*STRUCT_KEYS, *PRICE_KEYS, *ACTIVITY_KEYS, "population"):
            v = feats.get(k)
            if v is not None and isinstance(v, (int, float)):
                row[k] = float(v)
        records.append(row)
    return pd.DataFrame(records)


def _build_vectors(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """struct matrix (raw), log-price z-scores, activity totals."""
    struct = df[list(STRUCT_KEYS)].fillna(0.0).astype(np.float64)

    price_logs = {}
    for k in PRICE_KEYS:
        if k not in df.columns:
            price_logs[k] = pd.Series(np.nan, index=df.index)
            continue
        vals = df[k].astype(float)
        price_logs[k] = np.log(vals.where(vals > 0))

    price_df = pd.DataFrame(price_logs)
    price_z = price_df.apply(lambda col: (col - col.mean()) / col.std(ddof=0) if col.notna().sum() > 1 else col * 0, axis=0)
    price_z = price_z.fillna(0.0)

    activity = df[[c for c in ACTIVITY_KEYS if c in df.columns]].fillna(0).sum(axis=1)
    population = df["population"] if "population" in df.columns else pd.Series(np.nan, index=df.index)

    return struct, price_z, activity.astype(float), population.astype(float)


def _build_twin_rows(
    df: pd.DataFrame,
    meta: pd.DataFrame,
    struct: pd.DataFrame,
    price_z: pd.DataFrame,
    activity: pd.Series,
    population: pd.Series,
    *,
    min_activity: float,
    top_k: int,
    pop_tol: float,
    w_struct: float,
    w_price: float,
    profile_version: str,
    as_of,
    window_years: int,
) -> list[dict]:
    meta_idx = meta.set_index("eupmyeondong_code")
    codes = [str(c).strip() for c in df["eupmyeondong_code"].tolist()]
    code_to_i = {c: i for i, c in enumerate(codes)}

    struct_np = struct.to_numpy()
    price_np = price_z.to_numpy()
    log_prices = {}
    for k in PRICE_KEYS:
        if k in df.columns:
            log_prices[k] = np.log(df[k].astype(float).where(df[k] > 0))

    eligible = [c for c in codes if activity.get(c, 0) >= min_activity and c in meta_idx.index]
    log.info("twin anchors/candidates eligible=%s / %s", len(eligible), len(codes))

    rows: list[dict] = []
    for anchor in eligible:
        ai = code_to_i[anchor]
        anchor_meta = meta_idx.loc[anchor]
        anchor_sido = str(anchor_meta["sido_code"]).strip()[:2]
        allowed_sidoes = allowed_twin_sidoes(anchor_sido)
        pop_a = float(population.get(anchor)) if pd.notna(population.get(anchor)) else None

        scores: list[tuple[str, float, dict]] = []
        for cand in eligible:
            if cand == anchor:
                continue
            ci = code_to_i[cand]
            cand_meta = meta_idx.loc[cand]
            cand_sido = str(cand_meta["sido_code"]).strip()[:2]
            if cand_sido not in allowed_sidoes:
                continue
            pop_b = float(population.get(cand)) if pd.notna(population.get(cand)) else None
            if pop_a and pop_b and not _pass_pop(pop_a, pop_b, pop_tol):
                continue

            s_struct = _cosine(struct_np[ai], struct_np[ci])
            log_a = float(np.nanmean([log_prices[k].iloc[ai] for k in PRICE_KEYS if k in log_prices and pd.notna(log_prices[k].iloc[ai])])) if PRICE_KEYS else None
            log_b = float(np.nanmean([log_prices[k].iloc[ci] for k in PRICE_KEYS if k in log_prices and pd.notna(log_prices[k].iloc[ci])])) if PRICE_KEYS else None
            s_price = _price_sim(log_a, log_b)
            score = w_struct * s_struct + w_price * s_price
            if score <= 0:
                continue
            scores.append(
                (
                    cand,
                    score,
                    {
                        "struct_sim": round(s_struct, 6),
                        "price_sim": round(s_price, 6),
                        "profile_version": profile_version,
                        "as_of_month": str(as_of),
                        "window_years": window_years,
                        "source": "regional_profile",
                    },
                )
            )

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
    p = argparse.ArgumentParser(description="regional_profile → twin (Profile 소비)")
    p.add_argument("--profile-version", type=str, default="v1.1-national")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--window-years", type=int, default=5)
    p.add_argument("--sido-code", type=str, default=None, help="스모크: 시도 한정")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--min-activity", type=float, default=15.0, help="land_residential+apartment count 합")
    p.add_argument("--pop-tolerance-rel", type=float, default=0.5)
    p.add_argument("--struct-weight", type=float, default=0.65)
    p.add_argument("--price-weight", type=float, default=0.35)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    w_sum = args.struct_weight + args.price_weight
    w_struct = args.struct_weight / w_sum
    w_price = args.price_weight / w_sum

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    batch_key = f"profile_{args.profile_version}_{as_of:%Y%m}_w{args.window_years}_{uuid.uuid4().hex[:8]}"

    coll = get_collective_engine()
    land = get_land_engine_for_region_copy()

    with coll.connect() as conn:
        if not conn.execute(text("SELECT to_regclass('public.regional_profile') IS NOT NULL")).scalar():
            raise SystemExit("regional_profile 없음")
        df = _load_profiles(
            conn,
            profile_version=args.profile_version,
            as_of=as_of,
            window_years=args.window_years,
            sido_code=args.sido_code,
        )

    if df.empty:
        raise SystemExit(
            f"Profile 행 없음: {args.profile_version} as_of={as_of} window={args.window_years}"
        )

    with land.connect() as lconn:
        meta = _load_eup_meta(lconn)

    df = df.merge(meta, on="eupmyeondong_code", how="inner")
    struct, price_z, activity, population = _build_vectors(df)
    activity.index = df["eupmyeondong_code"].values
    population.index = df["eupmyeondong_code"].values

    twin_rows = _build_twin_rows(
        df,
        meta,
        struct,
        price_z,
        activity,
        population,
        min_activity=args.min_activity,
        top_k=args.top_k,
        pop_tol=args.pop_tolerance_rel,
        w_struct=w_struct,
        w_price=w_price,
        profile_version=args.profile_version,
        as_of=as_of,
        window_years=args.window_years,
    )

    log.info(
        "batch=%s profile=%s eup=%s twin_rows=%s dry_run=%s",
        batch_key,
        args.profile_version,
        len(df),
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

    computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
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

    log.info("twin_eupmyeondong_neighbor_mvp inserted %s rows batch_key=%s", len(payload), batch_key)


if __name__ == "__main__":
    main()
