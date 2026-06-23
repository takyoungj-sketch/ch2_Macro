"""Twin v8 API — 충청권 쌍둥이 (algorithm_version=8, Hybrid V2와 병행)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(prefix="/twin-v8", tags=["쌍둥이 v8"])


class TwinV8NeighborItem(BaseModel):
    rank: int
    twin_region_code: str
    twin_region_name: str
    twin_sigungu_code: str | None = None
    twin_sigungu_name: str | None = None
    twin_sido_code: str
    twin_sido_name: str
    similarity_score: float = Field(..., description="0~100 Twin Score")
    confidence_score: float = Field(..., description="0~100 Confidence")
    explanation_ko: str | None = None
    detail_scores: dict = Field(default_factory=dict)


class TwinV8NeighborsResponse(BaseModel):
    batch_key: str
    scope_label: str
    region_level: str
    anchor_region_code: str
    anchor_region_name: str
    algorithm_version: int = 8
    neighbors: list[TwinV8NeighborItem]


class TwinV8LatestBatch(BaseModel):
    batch_key: str
    computed_at: str | None = None
    scope_label: str | None = None
    twin_row_count: int = 0


def _ensure_table(db: Session) -> None:
    reg = db.execute(text("SELECT to_regclass('public.twin_neighbor_v8')::text")).scalar()
    if reg is None or str(reg).strip() == "":
        raise HTTPException(
            503,
            detail="twin_neighbor_v8 없음 — db/031_twin_neighbor_v8.sql + build_twin_v8.py 실행",
        )


def _latest_batch(db: Session) -> str | None:
    row = db.execute(
        text(
            """
            SELECT batch_key
            FROM twin_neighbor_v8
            GROUP BY batch_key
            ORDER BY MAX(computed_at) DESC NULLS LAST
            LIMIT 1
            """
        )
    ).fetchone()
    return str(row.batch_key) if row and row.batch_key else None


@router.get("/latest-batch", response_model=TwinV8LatestBatch)
def latest_batch(db: Session = Depends(get_db)) -> TwinV8LatestBatch:
    _ensure_table(db)
    row = db.execute(
        text(
            """
            SELECT batch_key,
                   MAX(computed_at) AS computed_at,
                   MAX(scope_label) AS scope_label,
                   COUNT(*)::int AS n
            FROM twin_neighbor_v8
            GROUP BY batch_key
            ORDER BY MAX(computed_at) DESC NULLS LAST
            LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        raise HTTPException(404, detail="twin_neighbor_v8 비어 있음")
    return TwinV8LatestBatch(
        batch_key=str(row["batch_key"]),
        computed_at=row["computed_at"].isoformat() if row["computed_at"] else None,
        scope_label=str(row["scope_label"]) if row["scope_label"] else None,
        twin_row_count=int(row["n"] or 0),
    )


@router.get("/neighbors/{region_level}/{region_code}", response_model=TwinV8NeighborsResponse)
def list_neighbors(
    region_level: str,
    region_code: str,
    db: Session = Depends(get_db),
    batch_key: Optional[str] = Query(None),
    top_k: int = Query(10, ge=1, le=50),
) -> TwinV8NeighborsResponse:
    _ensure_table(db)
    level = region_level.strip().lower()
    if level not in ("sigungu", "eupmyeondong", "beopjungri"):
        raise HTTPException(422, detail="region_level: sigungu | eupmyeondong | beopjungri")
    code = region_code.strip()
    bk = batch_key or _latest_batch(db)
    if not bk:
        raise HTTPException(404, detail="배치 없음")

    anchor = db.execute(
        text(
            """
            SELECT anchor_region_name, anchor_sigungu_name, anchor_sido_name, scope_label
            FROM twin_neighbor_v8
            WHERE batch_key = :bk AND region_level = :lv AND anchor_region_code = :ac
            LIMIT 1
            """
        ),
        {"bk": bk, "lv": level, "ac": code},
    ).mappings().first()
    if not anchor:
        raise HTTPException(404, detail=f"앵커 {level}/{code} 에 대한 v8 결과 없음")

    rows = db.execute(
        text(
            """
            SELECT rank, twin_region_code, twin_region_name,
                   twin_sigungu_code, twin_sigungu_name,
                   twin_sido_code, twin_sido_name,
                   similarity_score, confidence_score,
                   explanation_ko, detail_scores
            FROM twin_neighbor_v8
            WHERE batch_key = :bk AND region_level = :lv AND anchor_region_code = :ac
            ORDER BY rank
            LIMIT :lim
            """
        ),
        {"bk": bk, "lv": level, "ac": code, "lim": top_k},
    ).mappings().all()

    neighbors = [
        TwinV8NeighborItem(
            rank=int(r["rank"]),
            twin_region_code=str(r["twin_region_code"]).strip(),
            twin_region_name=str(r["twin_region_name"]),
            twin_sigungu_code=str(r["twin_sigungu_code"]).strip() if r["twin_sigungu_code"] else None,
            twin_sigungu_name=str(r["twin_sigungu_name"]) if r["twin_sigungu_name"] else None,
            twin_sido_code=str(r["twin_sido_code"]).strip(),
            twin_sido_name=str(r["twin_sido_name"]),
            similarity_score=float(r["similarity_score"]),
            confidence_score=float(r["confidence_score"]),
            explanation_ko=r["explanation_ko"],
            detail_scores=dict(r["detail_scores"] or {}),
        )
        for r in rows
    ]
    return TwinV8NeighborsResponse(
        batch_key=bk,
        scope_label=str(anchor["scope_label"] or "충청권"),
        region_level=level,
        anchor_region_code=code,
        anchor_region_name=str(anchor["anchor_region_name"]),
        neighbors=neighbors,
    )
