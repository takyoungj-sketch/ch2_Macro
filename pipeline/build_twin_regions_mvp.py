"""
Twin Region 배치 스크립트 — 전국 시군구 간 유사도 상위 순위 적재.

docs/TWIN_REGION_SIMILARITY_ENGINE.md 설계에 맞춰:
  - 거래건수 비중(용도지역×지목) 코사인 유사도(메인)
  - 시군구별 중앙값 단가의 log1p 차이 기반 보조 유사도(가중)
  - 인구 허들: 앵커·트윈 인구 비가 (1 − tol)~(1 + tol) (기본 tol=0.4 → ±40%)

사전:
    db/012_twin_region_neighbor_mvp.sql 적용 후 실행.

예:
    cd pipeline && python build_twin_regions_mvp.py
    python build_twin_regions_mvp.py --dry-run --min-tx 10 --year-from 2019
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from db_utils import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# sido_scope_codes 컬럼용 레이블
SIDO_SCOPE_LABEL = "NATIONAL"

POP_TOLERANCE_REL_DEFAULT = 0.4  # ±40%
MIN_TX_DEFAULT = 30
TOP_K_DEFAULT = 5
STRUCT_WEIGHT_DEFAULT = 0.72
PRICE_WEIGHT_DEFAULT = 0.28
ALGORITHM_VERSION = 3


def _cosine_dense(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _jaccard_nonzero_masks(va: np.ndarray, vb: np.ndarray) -> float:
    sa_s = set(np.where(va > 1e-14)[0].flat)
    sb_s = set(np.where(vb > 1e-14)[0].flat)
    if not sa_s and not sb_s:
        return 1.0
    if not sa_s or not sb_s:
        return 0.0
    inter = len(sa_s & sb_s)
    union = len(sa_s | sb_s)
    return float(inter / union) if union else 0.0


def _price_sim(log1pa: float | None, log1pb: float | None) -> float:
    if log1pa is None or log1pb is None:
        return 0.0
    denom = float(os.environ.get("TWIN_PRICE_LOG_DENOM", "2.5"))
    d = abs(log1pa - log1pb)
    return float(max(0.0, 1.0 - min(1.0, d / denom)))


def _pass_pop(pa: float | None, pb: float | None, tol_rel: float) -> bool:
    if pa is None or pb is None or pa <= 0 or pb <= 0:
        return False
    lo = 1.0 - tol_rel
    hi = 1.0 + tol_rel
    r = pb / pa
    if lo <= r <= hi:
        return True
    r2 = pa / pb
    return lo <= r2 <= hi


def _load_sigungu_meta(conn: Any) -> pd.DataFrame:
    qry = text(
        """
            SELECT DISTINCT ON (sigungu_code)
                btrim(sigungu_code::text) AS sigungu_code,
                sigungu_name,
                btrim(sido_code::text) AS sido_code,
                sido_name
            FROM region_codes
            WHERE is_active
            ORDER BY sigungu_code, beopjungri_code
            """
    )
    return pd.read_sql(qry, conn)


def _load_cell_counts(conn: Any, year_from: int | None) -> pd.DataFrame:
    year_clause = ""
    params: dict[str, Any] = {}
    if year_from is not None:
        year_clause = " AND lt.contract_year >= :year_from "
        params["year_from"] = int(year_from)

    qry = text(
        f"""
        SELECT
            btrim(lt.sigungu_code::text) AS sigungu_code,
            COALESCE(NULLIF(btrim(lt.zone_type::text), ''), '__EMPTY_Z__')
                || '|' ||
            COALESCE(NULLIF(btrim(lt.land_category::text), ''), '__EMPTY_L__')
                AS cell_key,
            COUNT(*)::bigint AS cnt
        FROM land_transactions lt
        WHERE lt.is_valid IS TRUE
          AND lt.is_cancelled IS FALSE
          {year_clause}
        GROUP BY 1, 2
        """
    )
    return pd.read_sql(qry, conn, params=params or None)


def _load_median_prices(conn: Any, year_from: int | None) -> pd.DataFrame:
    year_clause = ""
    params: dict[str, Any] = {}
    if year_from is not None:
        year_clause = " AND lt.contract_year >= :year_from "
        params["year_from"] = int(year_from)

    qry = text(
        f"""
        SELECT sub.sigungu_code,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY sub.up) AS median_up
        FROM (
            SELECT
                btrim(lt.sigungu_code::text) AS sigungu_code,
                lt.unit_price_per_sqm::double precision AS up
            FROM land_transactions lt
            WHERE lt.is_valid IS TRUE
              AND lt.is_cancelled IS FALSE
              AND lt.unit_price_per_sqm IS NOT NULL
              AND lt.unit_price_per_sqm > 0
              AND lt.area_sqm IS NOT NULL
              AND lt.area_sqm > 0
              {year_clause}
        ) sub
        GROUP BY sub.sigungu_code
        """
    )
    return pd.read_sql(qry, conn, params=params or None)


def _load_pop_by_sigungu(conn: Any) -> pd.DataFrame:
    """법정동 최신 행합 → 시군구 합산 인구."""
    qry = text(
        """
        WITH lp0 AS (
            SELECT
                btrim(admin_code::text) AS beopjungri_code,
                total_population::bigint AS pop,
                stats_year,
                loaded_at
            FROM population_stats
            WHERE admin_level = 'beopjungri'
              AND total_population IS NOT NULL
              AND total_population > 0
        ),
        latest_pop AS (
            SELECT DISTINCT ON (beopjungri_code)
                beopjungri_code,
                pop,
                stats_year
            FROM lp0
            ORDER BY beopjungri_code, stats_year DESC, loaded_at DESC NULLS LAST
        ),
        joined AS (
            SELECT
                btrim(rc.sigungu_code::text) AS sigungu_code,
                SUM(lp.pop)::bigint AS population
            FROM latest_pop lp
            INNER JOIN region_codes rc
                ON btrim(rc.beopjungri_code::text) = lp.beopjungri_code
            WHERE rc.is_active IS TRUE
            GROUP BY rc.sigungu_code
        )
        SELECT * FROM joined
        """
    )
    return pd.read_sql(qry, conn)


def _normalize_share_wide(df_cnt: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """sigungu_code × cell_key 건수 → 행 단위 비중."""
    wide = df_cnt.pivot_table(
        index="sigungu_code", columns="cell_key", values="cnt", aggfunc="sum", fill_value=0
    )
    row_sums = wide.sum(axis=1)
    eligible = row_sums[row_sums >= 1].index.astype(str).tolist()
    wide = wide.loc[eligible]
    row_sums = row_sums.loc[eligible].replace(0, np.nan)
    share = wide.div(row_sums, axis=0).replace([np.inf, -np.inf], 0).fillna(0)
    totals = row_sums.fillna(0).astype(int).to_dict()
    return share.astype(np.float64), totals


def _build_rows_for_batch(
    share: pd.DataFrame,
    totals: dict[str, int],
    median_price: pd.Series,
    population: pd.Series,
    meta: pd.DataFrame,
    min_tx: int,
    top_k: int,
    tol_rel: float,
    w_struct: float,
    w_price: float,
) -> list[dict[str, Any]]:
    codes = [c for c in share.index.astype(str) if totals.get(c, 0) >= min_tx]
    codes.sort()

    meta_i = meta.set_index("sigungu_code")

    twin_rows_out: list[dict[str, Any]] = []

    for anchor in codes:
        try:
            a_row_meta = meta_i.loc[anchor]
        except KeyError:
            log.warning("region_codes 에 시군구 없음 스킵: %s", anchor)
            continue
        va = share.loc[anchor].to_numpy(dtype=np.float64, copy=False)
        pop_a = float(population.get(anchor)) if anchor in population.index else np.nan

        cand_scores: list[tuple[float, str, dict[str, Any]]] = []
        med_pa = median_price.get(anchor) if hasattr(median_price, "get") else None
        log1pa = float(np.log1p(med_pa)) if med_pa is not None and not pd.isna(med_pa) else None

        for twin in codes:
            if twin == anchor:
                continue
            pop_b = float(population.get(twin)) if twin in population.index else np.nan
            if not _pass_pop(pop_a, pop_b, tol_rel):
                continue
            vb = share.loc[twin].to_numpy(dtype=np.float64, copy=False)
            cos = _cosine_dense(va, vb)
            jac = _jaccard_nonzero_masks(va, vb)
            med_pb = median_price.get(twin) if hasattr(median_price, "get") else None
            log1pb = float(np.log1p(med_pb)) if med_pb is not None and not pd.isna(med_pb) else None
            p_sim = _price_sim(log1pa, log1pb)
            combined = w_struct * cos + w_price * p_sim
            detail = {
                "aggregation_scope": "national_sigungu",
                "cosine_structure": round(cos, 6),
                "jaccard_nonzero_cells": round(jac, 6),
                "price_similarity": round(p_sim, 6),
                "weights": {"structure": w_struct, "price": w_price},
                "anchor_population": int(pop_a) if pop_a == pop_a else None,
                "twin_population": int(pop_b) if pop_b == pop_b else None,
                "pop_tolerance_rel": tol_rel,
                "anchor_median_unit_price": float(med_pa) if med_pa is not None and not pd.isna(med_pa) else None,
                "twin_median_unit_price": float(med_pb) if med_pb is not None and not pd.isna(med_pb) else None,
            }
            cand_scores.append((combined, twin, detail))

        cand_scores.sort(key=lambda x: -x[0])
        for rank, (score, twin, detail) in enumerate(cand_scores[:top_k], start=1):
            try:
                t_row = meta_i.loc[twin]
            except KeyError:
                continue
            twin_rows_out.append(
                {
                    "anchor_sigungu_code": anchor,
                    "anchor_sigungu_name": str(a_row_meta["sigungu_name"]),
                    "anchor_sido_code": str(a_row_meta["sido_code"]),
                    "anchor_sido_name": str(a_row_meta["sido_name"]),
                    "rank": rank,
                    "twin_sigungu_code": twin,
                    "twin_sigungu_name": str(t_row["sigungu_name"]),
                    "twin_sido_code": str(t_row["sido_code"]),
                    "twin_sido_name": str(t_row["sido_name"]),
                    "similarity_score": float(round(score, 10)),
                    "detail_scores": detail,
                }
            )
    return twin_rows_out


def main() -> None:
    p = argparse.ArgumentParser(description="Twin Region — 전국 시군구 유사 이웃 적재")
    p.add_argument("--dry-run", action="store_true", help="DB INSERT 생략")
    p.add_argument("--min-tx", type=int, default=MIN_TX_DEFAULT, help="시군구 최소 유효 거래 건수")
    p.add_argument("--top-k", type=int, default=TOP_K_DEFAULT, help="앵커당 상위 k")
    p.add_argument("--pop-tolerance-rel", type=float, default=POP_TOLERANCE_REL_DEFAULT, help="인구 상대 허들")
    p.add_argument("--year-from", type=int, default=None, help="contract_year 하한 (미지정=전체)")
    p.add_argument(
        "--w-struct",
        type=float,
        default=STRUCT_WEIGHT_DEFAULT,
        help="구조(코사인) 가중",
    )
    p.add_argument(
        "--w-price",
        type=float,
        default=PRICE_WEIGHT_DEFAULT,
        help="가격 보조 가중",
    )
    p.add_argument(
        "--batch-key",
        default=None,
        help="배치 키 (미지정 시 자동 UUID)",
    )
    args = p.parse_args()

    w_s, w_p = float(args.w_struct), float(args.w_price)
    if w_s < 0 or w_p < 0 or abs(w_s + w_p - 1.0) > 1e-6:
        raise SystemExit("w_struct + w_price 는 1.0 이어야 합니다.")

    batch_key = (args.batch_key or "").strip() or f"mvp-sgg-{uuid.uuid4().hex[:12]}"
    engine = get_engine()

    with engine.connect() as conn:
        meta = _load_sigungu_meta(conn)
        cells = _load_cell_counts(conn, args.year_from)
        med = _load_median_prices(conn, args.year_from)
        pop_df = _load_pop_by_sigungu(conn)

    if cells.empty:
        raise SystemExit("land_transactions 시군구 셀 집계 결과가 비었습니다.")

    share, totals = _normalize_share_wide(cells)
    median_series = med.set_index("sigungu_code")["median_up"] if not med.empty else pd.Series(dtype=float)
    population = pop_df.set_index("sigungu_code")["population"] if not pop_df.empty else pd.Series(dtype=int)

    rows = _build_rows_for_batch(
        share=share,
        totals=totals,
        median_price=median_series,
        population=population,
        meta=meta,
        min_tx=int(args.min_tx),
        top_k=int(args.top_k),
        tol_rel=float(args.pop_tolerance_rel),
        w_struct=w_s,
        w_price=w_p,
    )

    log.info(
        "배치 %s: 대상 시군구(거래≥%s) %d개, 적재 행 %d (dry_run=%s)",
        batch_key,
        args.min_tx,
        len([c for c in share.index if totals.get(str(c), 0) >= args.min_tx]),
        len(rows),
        args.dry_run,
    )

    if args.dry_run:
        return

    ins = text(
        """
        INSERT INTO twin_region_neighbor_mvp (
            batch_key,
            algorithm_version,
            sido_scope_codes,
            anchor_sigungu_code,
            anchor_sigungu_name,
            anchor_sido_code,
            anchor_sido_name,
            rank,
            twin_sigungu_code,
            twin_sigungu_name,
            twin_sido_code,
            twin_sido_name,
            similarity_score,
            detail_scores
        ) VALUES (
            :batch_key,
            :algorithm_version,
            :sido_scope_codes,
            :anchor_sigungu_code,
            :anchor_sigungu_name,
            :anchor_sido_code,
            :anchor_sido_name,
            :rank,
            :twin_sigungu_code,
            :twin_sigungu_name,
            :twin_sido_code,
            :twin_sido_name,
            :similarity_score,
            CAST(:detail_scores AS jsonb)
        )
        """
    )

    now_utc = datetime.now(timezone.utc)
    payload = []
    for r in rows:
        payload.append(
            {
                "batch_key": batch_key,
                "algorithm_version": ALGORITHM_VERSION,
                "sido_scope_codes": SIDO_SCOPE_LABEL,
                "anchor_sigungu_code": r["anchor_sigungu_code"],
                "anchor_sigungu_name": r["anchor_sigungu_name"],
                "anchor_sido_code": r["anchor_sido_code"],
                "anchor_sido_name": r["anchor_sido_name"],
                "rank": r["rank"],
                "twin_sigungu_code": r["twin_sigungu_code"],
                "twin_sigungu_name": r["twin_sigungu_name"],
                "twin_sido_code": r["twin_sido_code"],
                "twin_sido_name": r["twin_sido_name"],
                "similarity_score": r["similarity_score"],
                "detail_scores": json.dumps(r["detail_scores"], ensure_ascii=False),
            }
        )

    with engine.begin() as conn:
        for chunk in payload:
            conn.execute(ins, chunk)

    log.info(
        "적재 완료 batch_key=%s rows=%d algorithm_version=%s computed_at~(UTC)%s",
        batch_key,
        len(payload),
        ALGORITHM_VERSION,
        now_utc.isoformat(timespec="seconds"),
    )


if __name__ == "__main__":
    main()
