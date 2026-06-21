#!/usr/bin/env python3
"""
Hybrid Twin v2 (D-023) — 토지 50% + 집합 30% + Profile(지역특성) 20%.

설계 (역할 분리):
  - 토지 블록 : zone×지목 구조 cosine + 단가 pairwise log-유사도 (legacy 검증값 유지)
  - 집합 블록 : 아파트/연립/오피스텔 거래 구성비 cosine + 아파트 가격 pairwise log-유사도
  - Profile  : 인구·밀도 등 지역 메타만 (가격 변수 제거 → 가격 중복 counting 회피)

원칙:
  - 모든 블록 점수 ∈ [0, 1]
  - "시장 없음" = 거래 구성비 0 (평균 대체 금지) + 집합 신뢰도로 가중치 동적 조정
  - pairwise log-유사도(전역 min/max 비의존)로 아웃라이어에 강건
  - detail_scores 에 sub-signal + reason_codes 저장 → UI 추천 이유 자동 생성

출력: twin_eupmyeondong_neighbor_mvp (algorithm_version=6, detail.algorithm=hybrid_v2)

예:
  cd pipeline
  python build_twin_hybrid.py --profile-version v1.1-national --window-years 5
  python build_twin_hybrid.py --dry-run --sido-code 43
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from build_twin_eupmyeondong_mvp import (  # noqa: E402
    _load_cell_counts,
    _load_eup_meta,
    _load_median_prices,
    _load_pop_by_eup,
    _normalize_share_wide,
    _pass_pop,
)
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from region_scope import (  # noqa: E402
    DEFAULT_SCOPE,
    SCOPES,
    candidate_scope_sidoes,
    region_name_of,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ALGORITHM_VERSION = 6
ALGORITHM_LABEL = "hybrid_v2"
SIDO_SCOPE_LABEL = "HYBRID_NAT_ADJ"

W_LAND_DEFAULT = 0.50
W_COLL_DEFAULT = 0.30
W_PROF_DEFAULT = 0.20

LAND_W_STRUCT = 0.72
LAND_W_PRICE = 0.28

COLL_W_PATTERN_DEFAULT = 0.70
COLL_W_PRICE_DEFAULT = 0.30
COLL_CONF_N0_DEFAULT = 20.0

LAND_PRICE_LOG_DENOM = 2.5
COLL_PRICE_LOG_DENOM = 2.5
PROFILE_LOG_DENOM = 2.5

COLL_COUNT_KEYS = ("apartment_count", "rowhouse_count", "officetel_count")
COLL_PRICE_KEY = "apartment_mean"
PROFILE_META_KEYS = ("population", "population_density")
ACTIVITY_KEYS = ("land_residential_count", "apartment_count")

LOAD_KEYS = (
    *COLL_COUNT_KEYS,
    COLL_PRICE_KEY,
    *PROFILE_META_KEYS,
    *ACTIVITY_KEYS,
    "population",
)


def _log_sim(a: float, b: float, denom: float) -> float | None:
    """양수 두 값의 pairwise 로그차 유사도 ∈ [0,1]. 결측/비양수 → None."""
    if a is None or b is None:
        return None
    if not np.isfinite(a) or not np.isfinite(b) or a <= 0 or b <= 0:
        return None
    d = abs(math.log1p(a) - math.log1p(b))
    return float(max(0.0, 1.0 - min(1.0, d / denom)))


def _l2_normalize_rows(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    safe = np.where(norms < 1e-12, 1.0, norms)
    out = m / safe
    out[(norms < 1e-12)[:, 0]] = 0.0
    return out


def _stars(x: float | None) -> int:
    if x is None or x <= 0:
        return 0
    return int(max(1, min(5, round(x * 5))))


def _reason_codes(
    *,
    land_struct: float,
    land_price: float | None,
    coll_pattern: float | None,
    coll_price: float | None,
    pop_sim: float | None,
    density_sim: float | None,
) -> list[str]:
    codes: list[str] = []

    def add(prefix: str, v: float | None, strong: float = 0.8, mild: float = 0.6) -> None:
        if v is None:
            return
        if v >= strong:
            codes.append(f"{prefix}_STRONG")
        elif v >= mild:
            codes.append(f"{prefix}_SIMILAR")

    add("LAND_STRUCT", land_struct)
    add("LAND_PRICE", land_price)
    add("COLL_PATTERN", coll_pattern)
    add("COLL_PRICE", coll_price)
    add("POP", pop_sim, strong=0.8, mild=0.65)
    add("DENSITY", density_sim, strong=0.8, mild=0.65)
    return codes


def _load_profiles(
    conn,
    *,
    profile_version: str,
    as_of,
    window_years: int,
    sido_prefixes: list[str] | None,
) -> pd.DataFrame:
    params: dict = {
        "pv": profile_version,
        "as_of": as_of,
        "wy": window_years,
    }
    sido_clause = ""
    if sido_prefixes:
        ors = []
        for i, pref in enumerate(sido_prefixes):
            key = f"sp{i}"
            ors.append(f"region_code LIKE :{key}")
            params[key] = f"{pref}%"
        sido_clause = " AND (" + " OR ".join(ors) + ") "

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
        for k in LOAD_KEYS:
            v = feats.get(k)
            if v is not None and isinstance(v, (int, float)):
                row[k] = float(v)
        records.append(row)
    return pd.DataFrame(records)


def _build_twin_rows(
    *,
    profile_df: pd.DataFrame,
    share: pd.DataFrame,
    land_totals: dict[str, int],
    median_price: pd.Series,
    meta: pd.DataFrame,
    anchor_sido_code: str | None,
    scope: str,
    min_tx: int,
    min_activity: float,
    top_k: int,
    pop_tol: float,
    w_land: float,
    w_coll: float,
    w_prof: float,
    coll_w_pattern: float,
    coll_w_price: float,
    coll_conf_n0: float,
    adaptive: bool,
    profile_version: str,
    as_of,
    window_years: int,
) -> list[dict]:
    meta_idx = meta.set_index("eupmyeondong_code")
    pdf = profile_df.set_index("eupmyeondong_code")

    share_index = set(share.index.astype(str))
    activity_series = (
        profile_df[[c for c in ACTIVITY_KEYS if c in profile_df.columns]].fillna(0).sum(axis=1)
    )
    activity_series.index = profile_df["eupmyeondong_code"].values

    eligible = [
        str(c).strip()
        for c in profile_df["eupmyeondong_code"].tolist()
        if land_totals.get(str(c).strip(), 0) >= min_tx
        and float(activity_series.get(str(c).strip(), 0)) >= min_activity
        and str(c).strip() in meta_idx.index
        and str(c).strip() in share_index
    ]
    if not eligible:
        log.warning("eligible 읍면동 없음")
        return []
    log.info("hybrid twin eligible=%s / profile=%s", len(eligible), len(profile_df))

    n = len(eligible)
    idx_of = {c: i for i, c in enumerate(eligible)}

    # --- 위치 정렬 numpy 배열 (성능: 내부 루프에서 pandas .loc 제거) ---
    land_norm = _l2_normalize_rows(
        share.reindex(eligible).fillna(0.0).to_numpy(dtype=np.float64)
    )
    land_log = np.log1p(
        median_price.reindex(eligible).to_numpy(dtype=np.float64)
    )  # 결측 → nan

    coll_counts = pdf.reindex(eligible)[list(COLL_COUNT_KEYS)].fillna(0.0).to_numpy(dtype=np.float64)
    coll_norm = _l2_normalize_rows(coll_counts)
    coll_total = coll_counts.sum(axis=1)
    apt_log = np.log1p(pdf.reindex(eligible).get(COLL_PRICE_KEY, pd.Series(np.nan, index=eligible)).to_numpy(dtype=np.float64))

    pop_arr = pdf.reindex(eligible).get("population", pd.Series(np.nan, index=eligible)).to_numpy(dtype=np.float64)
    den_arr = pdf.reindex(eligible).get("population_density", pd.Series(np.nan, index=eligible)).to_numpy(dtype=np.float64)

    if adaptive:
        conf = np.minimum(1.0, coll_total / max(coll_conf_n0, 1e-9))
    else:
        conf = np.ones(n, dtype=np.float64)

    sido_arr = np.array(
        [str(meta_idx.loc[c]["sido_code"]).strip()[:2] for c in eligible]
    )

    # 시도별 후보 인덱스 그룹
    sido_to_idx: dict[str, list[int]] = {}
    for i, sd in enumerate(sido_arr):
        sido_to_idx.setdefault(sd, []).append(i)

    anchor_indices = [
        i for i in range(n) if anchor_sido_code is None or sido_arr[i] == anchor_sido_code
    ]

    rows: list[dict] = []
    for ai in anchor_indices:
        anchor = eligible[ai]
        anchor_meta = meta_idx.loc[anchor]
        anchor_region = region_name_of(sido_arr[ai])
        allowed = candidate_scope_sidoes(sido_arr[ai], scope)
        pop_a = float(pop_arr[ai]) if np.isfinite(pop_arr[ai]) else None

        if allowed is None:  # national: 후보 제한 없음
            cand_idx: list[int] = list(range(n))
        else:
            cand_idx = []
            for sd in allowed:
                cand_idx.extend(sido_to_idx.get(sd, []))

        scored: list[tuple[float, str, dict]] = []
        for ci in cand_idx:
            if ci == ai:
                continue
            pop_b = float(pop_arr[ci]) if np.isfinite(pop_arr[ci]) else None
            if pop_a and pop_b and not _pass_pop(pop_a, pop_b, pop_tol):
                continue

            # 토지 블록
            land_struct = float(np.dot(land_norm[ai], land_norm[ci]))
            la, lb = land_log[ai], land_log[ci]
            land_price = (
                None
                if (math.isnan(la) or math.isnan(lb))
                else float(max(0.0, 1.0 - min(1.0, abs(la - lb) / LAND_PRICE_LOG_DENOM)))
            )
            s_land = LAND_W_STRUCT * land_struct + LAND_W_PRICE * (land_price or 0.0)

            # 집합 블록 (구성비 cosine + 아파트 가격수준)
            coll_pattern = float(np.dot(coll_norm[ai], coll_norm[ci]))
            aa, ab = apt_log[ai], apt_log[ci]
            coll_price = (
                None
                if (math.isnan(aa) or math.isnan(ab))
                else float(max(0.0, 1.0 - min(1.0, abs(aa - ab) / COLL_PRICE_LOG_DENOM)))
            )
            if coll_price is None:
                s_coll = coll_pattern
            else:
                s_coll = coll_w_pattern * coll_pattern + coll_w_price * coll_price

            # Profile 블록 (인구·밀도, 가격 없음)
            pop_sim = _log_sim(pop_a, pop_b, PROFILE_LOG_DENOM)
            density_sim = _log_sim(
                float(den_arr[ai]) if np.isfinite(den_arr[ai]) else None,
                float(den_arr[ci]) if np.isfinite(den_arr[ci]) else None,
                PROFILE_LOG_DENOM,
            )
            prof_vals = [v for v in (pop_sim, density_sim) if v is not None]
            s_prof = float(np.mean(prof_vals)) if prof_vals else 0.0

            # 적응형 가중치: 집합 신뢰도(앵커·후보 min) → 남는 비중은 토지·Profile로 재분배
            c_conf = float(min(conf[ai], conf[ci]))
            wl = w_land
            wc = w_coll * c_conf
            wp = w_prof
            wsum = wl + wc + wp
            if wsum <= 1e-12:
                continue
            wl, wc, wp = wl / wsum, wc / wsum, wp / wsum
            final = wl * s_land + wc * s_coll + wp * s_prof
            if final <= 0:
                continue

            twin_region = region_name_of(sido_arr[ci])
            detail = {
                "algorithm": ALGORITHM_LABEL,
                "profile_version": profile_version,
                "as_of_month": str(as_of),
                "window_years": window_years,
                "scope": scope,
                "anchor_region": anchor_region,
                "twin_region": twin_region,
                "in_region": bool(anchor_region is not None and anchor_region == twin_region),
                "s_land": round(s_land, 6),
                "s_collective": round(s_coll, 6),
                "s_profile": round(s_prof, 6),
                "similarity_final": round(final, 6),
                "land_struct_sim": round(land_struct, 6),
                "land_price_sim": None if land_price is None else round(land_price, 6),
                "coll_pattern_sim": round(coll_pattern, 6),
                "coll_price_sim": None if coll_price is None else round(coll_price, 6),
                "pop_sim": None if pop_sim is None else round(pop_sim, 6),
                "density_sim": None if density_sim is None else round(density_sim, 6),
                "collective_confidence": round(c_conf, 4),
                "weights_effective": {
                    "land": round(wl, 4),
                    "collective": round(wc, 4),
                    "profile": round(wp, 4),
                },
                "stars": {
                    "land_struct": _stars(land_struct),
                    "land_price": _stars(land_price),
                    "coll_pattern": _stars(coll_pattern),
                    "coll_price": _stars(coll_price),
                    "population": _stars(pop_sim),
                    "density": _stars(density_sim),
                },
                "reason_codes": _reason_codes(
                    land_struct=land_struct,
                    land_price=land_price,
                    coll_pattern=coll_pattern,
                    coll_price=coll_price,
                    pop_sim=pop_sim,
                    density_sim=density_sim,
                ),
            }
            scored.append((final, eligible[ci], detail))

        # 동점 결정성: 점수 내림차순, 코드 오름차순
        scored.sort(key=lambda x: (-x[0], x[1]))
        for rank, (score, twin_code, detail) in enumerate(scored[:top_k], start=1):
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
    p = argparse.ArgumentParser(description="Hybrid Twin v2 — land 50% + collective 30% + profile 20%")
    p.add_argument("--profile-version", type=str, default="v1.1-national")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--window-years", type=int, default=5)
    p.add_argument("--sido-code", type=str, default=None, help="스모크: anchor 시도 한정 (후보풀은 scope 기준)")
    p.add_argument("--scope", choices=SCOPES, default=DEFAULT_SCOPE,
                   help="후보군 범위: adjacent(육상 인접) / region(권역, 기본) / national(전국)")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--min-tx", type=int, default=20, help="토지 legacy 최소 거래")
    p.add_argument("--min-activity", type=float, default=15.0)
    p.add_argument("--pop-tolerance-rel", type=float, default=0.4)
    p.add_argument("--w-land", type=float, default=W_LAND_DEFAULT)
    p.add_argument("--w-coll", type=float, default=W_COLL_DEFAULT)
    p.add_argument("--w-prof", type=float, default=W_PROF_DEFAULT)
    p.add_argument("--coll-w-pattern", type=float, default=COLL_W_PATTERN_DEFAULT)
    p.add_argument("--coll-w-price", type=float, default=COLL_W_PRICE_DEFAULT)
    p.add_argument("--coll-conf-n0", type=float, default=COLL_CONF_N0_DEFAULT,
                   help="집합 신뢰도=min(1, 집합거래수/N0)")
    p.add_argument("--no-adaptive", action="store_true", help="적응형 집합 가중치 비활성")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    w_sum = args.w_land + args.w_coll + args.w_prof
    w_land = args.w_land / w_sum
    w_coll = args.w_coll / w_sum
    w_prof = args.w_prof / w_sum

    cw_sum = args.coll_w_pattern + args.coll_w_price
    coll_w_pattern = args.coll_w_pattern / cw_sum
    coll_w_price = args.coll_w_price / cw_sum

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    year_from = as_of.year - int(args.window_years) + 1
    batch_key = (
        f"hybrid2_{args.scope}_{args.profile_version}_{as_of:%Y%m}_w{args.window_years}_{uuid.uuid4().hex[:8]}"
    )

    # 스모크: anchor 시도만 한정하되, 후보풀·기준선은 scope 기준 시도로 로드
    anchor_sido_code = None
    sido_prefixes: list[str] | None = None
    if args.sido_code:
        anchor_sido_code = args.sido_code.strip()[:2]
        pool = candidate_scope_sidoes(anchor_sido_code, args.scope)
        if pool is None:
            sido_prefixes = None  # national: 전국 로드
        else:
            sido_prefixes = sorted(set(pool) | {anchor_sido_code})
        log.info("smoke: scope=%s anchor 시도=%s, 후보풀 시도=%s",
                 args.scope, anchor_sido_code, sido_prefixes or "전국")

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
            sido_prefixes=sido_prefixes,
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

    profile_df = profile_df.merge(meta, on="eupmyeondong_code", how="inner")

    # Profile 에 population 결측 시 land 인구로 보완
    if "population" not in profile_df.columns and not pop_df.empty:
        profile_df = profile_df.merge(
            pop_df[["eupmyeondong_code", "population"]], on="eupmyeondong_code", how="left"
        )

    twin_rows = _build_twin_rows(
        profile_df=profile_df,
        share=share,
        land_totals=land_totals,
        median_price=median_series,
        meta=meta,
        anchor_sido_code=anchor_sido_code,
        scope=args.scope,
        min_tx=args.min_tx,
        min_activity=args.min_activity,
        top_k=args.top_k,
        pop_tol=args.pop_tolerance_rel,
        w_land=w_land,
        w_coll=w_coll,
        w_prof=w_prof,
        coll_w_pattern=coll_w_pattern,
        coll_w_price=coll_w_price,
        coll_conf_n0=args.coll_conf_n0,
        adaptive=not args.no_adaptive,
        profile_version=args.profile_version,
        as_of=as_of,
        window_years=args.window_years,
    )

    log.info(
        "batch=%s hybrid_v2 scope=%s profile=%s twin_rows=%s dry_run=%s",
        batch_key,
        args.scope,
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

    log.info(
        "twin_eupmyeondong_neighbor_mvp hybrid_v2 inserted %s rows batch_key=%s",
        len(payload),
        batch_key,
    )


if __name__ == "__main__":
    main()
