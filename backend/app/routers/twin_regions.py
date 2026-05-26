"""
쌍둥이 지역(Twin Region) MVP — 시군구(`twin_region_neighbor_mvp`)·읍면동(`twin_eupmyeondong_neighbor_mvp`).

선행: db/012, db/013 + 각각 pipeline 빌드 스크립트.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    TwinEupmyeondongNeighborItem,
    TwinNeighborItem,
    TwinNeighborsForEupmyeondongResponse,
    TwinNeighborsForSigunguResponse,
    TwinRegionLatestBatch,
)

router = APIRouter(prefix="/twin-regions", tags=["쌍둥이 지역 (MVP)"])


def _ensure_twin_table(db: Session) -> None:
    reg = db.execute(text("SELECT to_regclass('public.twin_region_neighbor_mvp')::text")).scalar()
    if reg is None or str(reg).strip() == "":
        raise HTTPException(
            status_code=503,
            detail=(
                "twin_region_neighbor_mvp 테이블이 없습니다. "
                "db/012_twin_region_neighbor_mvp.sql 적용 후 "
                "pipeline/build_twin_regions_mvp.py 로 데이터를 적재하세요."
            ),
        )


def _validate_sigungu(code: str) -> str:
    s = (code or "").strip()
    if not s.isdigit() or len(s) != 5:
        raise HTTPException(status_code=422, detail="sigungu_code 는 5자리 숫자여야 합니다.")
    return s


@router.get("/latest-batch", response_model=TwinRegionLatestBatch)
def get_latest_twin_batch(db: Session = Depends(get_db)) -> TwinRegionLatestBatch:
    _ensure_twin_table(db)
    row = db.execute(
        text(
            """
            SELECT
                batch_key,
                MAX(computed_at) AS computed_at,
                MAX(algorithm_version) AS algorithm_version,
                MAX(sido_scope_codes) AS sido_scope_codes,
                COUNT(*)::int AS twin_row_count
            FROM twin_region_neighbor_mvp
            GROUP BY batch_key
            ORDER BY MAX(computed_at) DESC NULLS LAST
            LIMIT 1
            """
        )
    ).fetchone()
    if row is None or row.batch_key is None:
        raise HTTPException(
            status_code=404,
            detail="twin_region_neighbor_mvp 가 비어 있습니다. 배치 스크립트를 먼저 실행하세요.",
        )
    return TwinRegionLatestBatch(
        batch_key=str(row.batch_key),
        computed_at=row.computed_at,
        algorithm_version=int(row.algorithm_version or 1),
        sido_scope_codes=str(row.sido_scope_codes or ""),
        twin_row_count=int(row.twin_row_count or 0),
    )


@router.get(
    "/neighbors/{sigungu_code}",
    response_model=TwinNeighborsForSigunguResponse,
)
def get_twin_neighbors_for_sigungu(
    sigungu_code: str,
    batch_key: Optional[str] = Query(
        None,
        description="미지정 시 최신 배치 기준",
    ),
    db: Session = Depends(get_db),
) -> TwinNeighborsForSigunguResponse:
    _ensure_twin_table(db)
    code = _validate_sigungu(sigungu_code)

    bk = (batch_key or "").strip()
    if not bk:
        latest = get_latest_twin_batch(db)
        bk = latest.batch_key

    rows = db.execute(
        text(
            """
            SELECT
                m.batch_key,
                m.computed_at,
                m.algorithm_version,
                m.sido_scope_codes,
                m.anchor_sigungu_code,
                m.anchor_sigungu_name,
                m.anchor_sido_code,
                m.anchor_sido_name,
                m.rank,
                m.twin_sigungu_code,
                m.twin_sigungu_name,
                m.twin_sido_code,
                m.twin_sido_name,
                m.similarity_score,
                m.detail_scores
            FROM twin_region_neighbor_mvp m
            WHERE m.batch_key = :batch_key
              AND btrim(m.anchor_sigungu_code::text) = :sigungu
            ORDER BY m.rank ASC
            """
        ),
        {"batch_key": bk, "sigungu": code},
    ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"배치 {bk!r} 에서 앵커 시군구 {code} 에 대한 쌍둥이 후보가 없습니다. "
                "(인구·거래 필터로 제외됐거나 미적재일 수 있습니다.)"
            ),
        )

    r0 = rows[0]
    neighbors = [
        TwinNeighborItem(
            rank=int(r.rank),
            twin_sigungu_code=str(r.twin_sigungu_code).strip(),
            twin_sigungu_name=str(r.twin_sigungu_name),
            twin_sido_code=str(r.twin_sido_code).strip(),
            twin_sido_name=str(r.twin_sido_name),
            similarity_score=float(r.similarity_score),
            detail_scores=dict(r.detail_scores) if r.detail_scores is not None else {},
        )
        for r in rows
    ]

    return TwinNeighborsForSigunguResponse(
        batch_key=str(r0.batch_key),
        computed_at=r0.computed_at,
        algorithm_version=int(r0.algorithm_version or 1),
        sido_scope_codes=str(r0.sido_scope_codes or ""),
        anchor_sigungu_code=str(r0.anchor_sigungu_code).strip(),
        anchor_sigungu_name=str(r0.anchor_sigungu_name),
        anchor_sido_code=str(r0.anchor_sido_code).strip(),
        anchor_sido_name=str(r0.anchor_sido_name),
        neighbors=neighbors,
    )


def _ensure_twin_eup_table(db: Session) -> None:
    reg = db.execute(text("SELECT to_regclass('public.twin_eupmyeondong_neighbor_mvp')::text")).scalar()
    if reg is None or str(reg).strip() == "":
        raise HTTPException(
            status_code=503,
            detail=(
                "twin_eupmyeondong_neighbor_mvp 테이블이 없습니다. "
                "db/013_twin_eupmyeondong_neighbor_mvp.sql 적용 후 "
                "pipeline/build_twin_eupmyeondong_mvp.py 로 데이터를 적재하세요."
            ),
        )


def _validate_eupmyeondong(code: str) -> str:
    s = (code or "").strip()
    if not s.isdigit() or len(s) != 8:
        raise HTTPException(status_code=422, detail="eupmyeondong_code 는 8자리 숫자여야 합니다.")
    return s


@router.get("/eupmyeondong/latest-batch", response_model=TwinRegionLatestBatch)
def get_latest_twin_eupmyeondong_batch(db: Session = Depends(get_db)) -> TwinRegionLatestBatch:
    _ensure_twin_eup_table(db)
    row = db.execute(
        text(
            """
            SELECT
                batch_key,
                MAX(computed_at) AS computed_at,
                MAX(algorithm_version) AS algorithm_version,
                MAX(sido_scope_codes) AS sido_scope_codes,
                COUNT(*)::int AS twin_row_count
            FROM twin_eupmyeondong_neighbor_mvp
            GROUP BY batch_key
            ORDER BY MAX(computed_at) DESC NULLS LAST
            LIMIT 1
            """
        )
    ).fetchone()
    if row is None or row.batch_key is None:
        raise HTTPException(status_code=404, detail="twin_eupmyeondong_neighbor_mvp 가 비어 있습니다.")
    return TwinRegionLatestBatch(
        batch_key=str(row.batch_key),
        computed_at=row.computed_at,
        algorithm_version=int(row.algorithm_version or 4),
        sido_scope_codes=str(row.sido_scope_codes or ""),
        twin_row_count=int(row.twin_row_count or 0),
    )


@router.get(
    "/eupmyeondong/neighbors/{eupmyeondong_code}",
    response_model=TwinNeighborsForEupmyeondongResponse,
)
def get_twin_neighbors_for_eupmyeondong(
    eupmyeondong_code: str,
    batch_key: Optional[str] = Query(
        None,
        description="미지정 시 최신 배치 기준",
    ),
    db: Session = Depends(get_db),
) -> TwinNeighborsForEupmyeondongResponse:
    _ensure_twin_eup_table(db)
    code = _validate_eupmyeondong(eupmyeondong_code)

    bk = (batch_key or "").strip()
    if not bk:
        latest = get_latest_twin_eupmyeondong_batch(db)
        bk = latest.batch_key

    rows = db.execute(
        text(
            """
            SELECT
                m.batch_key,
                m.computed_at,
                m.algorithm_version,
                m.sido_scope_codes,
                m.anchor_eupmyeondong_code,
                m.anchor_eupmyeondong_name,
                m.anchor_sigungu_code,
                m.anchor_sigungu_name,
                m.anchor_sido_code,
                m.anchor_sido_name,
                m.rank,
                m.twin_eupmyeondong_code,
                m.twin_eupmyeondong_name,
                m.twin_sigungu_code,
                m.twin_sigungu_name,
                m.twin_sido_code,
                m.twin_sido_name,
                m.similarity_score,
                m.detail_scores
            FROM twin_eupmyeondong_neighbor_mvp m
            WHERE m.batch_key = :batch_key
              AND btrim(m.anchor_eupmyeondong_code::text) = :eup
            ORDER BY m.rank ASC
            """
        ),
        {"batch_key": bk, "eup": code},
    ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"배치 {bk!r} 에서 앵커 읍면동 {code} 에 대한 쌍둥이 후보가 없습니다.",
        )

    r0 = rows[0]
    neighbors = [
        TwinEupmyeondongNeighborItem(
            rank=int(r.rank),
            twin_eupmyeondong_code=str(r.twin_eupmyeondong_code).strip(),
            twin_eupmyeondong_name=str(r.twin_eupmyeondong_name),
            twin_sigungu_code=str(r.twin_sigungu_code).strip(),
            twin_sigungu_name=str(r.twin_sigungu_name),
            twin_sido_code=str(r.twin_sido_code).strip(),
            twin_sido_name=str(r.twin_sido_name),
            similarity_score=float(r.similarity_score),
            detail_scores=dict(r.detail_scores) if r.detail_scores is not None else {},
        )
        for r in rows
    ]

    return TwinNeighborsForEupmyeondongResponse(
        batch_key=str(r0.batch_key),
        computed_at=r0.computed_at,
            algorithm_version=int(r0.algorithm_version or 4),
        sido_scope_codes=str(r0.sido_scope_codes or ""),
        anchor_eupmyeondong_code=str(r0.anchor_eupmyeondong_code).strip(),
        anchor_eupmyeondong_name=str(r0.anchor_eupmyeondong_name),
        anchor_sigungu_code=str(r0.anchor_sigungu_code).strip(),
        anchor_sigungu_name=str(r0.anchor_sigungu_name),
        anchor_sido_code=str(r0.anchor_sido_code).strip(),
        anchor_sido_name=str(r0.anchor_sido_name),
        neighbors=neighbors,
    )
