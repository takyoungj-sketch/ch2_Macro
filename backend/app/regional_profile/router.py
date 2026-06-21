"""Regional Profile API — collective_stats.regional_profile 조회."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.db import get_collective_db

router = APIRouter(prefix="/regional-profile", tags=["regional-profile"])


class RegionalProfileMeta(BaseModel):
    profile_version: str
    as_of_month: date
    window_years: int
    region_level: str
    region_code: str
    feature_count: Optional[int] = None
    builder_version: Optional[str] = None
    validation_status: str = "PENDING"
    computed_at: Optional[str] = None


class RegionalProfileResponse(BaseModel):
    meta: RegionalProfileMeta
    features: dict[str, Any] = Field(default_factory=dict)


class RegionalProfileVersionsResponse(BaseModel):
    profile_versions: list[str]
    latest_as_of_month: Optional[date] = None


class ProfileTwinNeighborItem(BaseModel):
    rank: int
    twin_eupmyeondong_code: str
    twin_eupmyeondong_name: str
    twin_sigungu_name: str
    twin_sido_name: str
    similarity_score: float
    detail_scores: dict[str, Any] = Field(default_factory=dict)


class ProfileTwinNeighborsResponse(BaseModel):
    profile_version: str
    window_years: int
    algorithm_version: int = 6
    as_of_month: Optional[date] = None
    batch_key: Optional[str] = None
    anchor_eupmyeondong_code: str
    neighbors: list[ProfileTwinNeighborItem] = Field(default_factory=list)


def _table_exists(db: Session, name: str) -> bool:
    row = db.execute(
        text("SELECT to_regclass(:n)::text IS NOT NULL AS ok"),
        {"n": f"public.{name}"},
    ).mappings().first()
    return bool(row and row["ok"])


@router.get("/versions", response_model=RegionalProfileVersionsResponse)
def list_profile_versions(db: Session = Depends(get_collective_db)):
    if db is None:
        raise HTTPException(503, "collective_stats DB 미연결")
    if not _table_exists(db, "regional_profile"):
        return RegionalProfileVersionsResponse(profile_versions=[], latest_as_of_month=None)

    versions = [
        str(r[0])
        for r in db.execute(
            text(
                """
                SELECT DISTINCT profile_version
                FROM regional_profile
                ORDER BY profile_version
                """
            )
        ).fetchall()
    ]
    latest = db.execute(text("SELECT MAX(as_of_month) FROM regional_profile")).scalar()
    return RegionalProfileVersionsResponse(
        profile_versions=versions,
        latest_as_of_month=latest,
    )


@router.get("", response_model=RegionalProfileResponse)
def get_regional_profile(
    region_level: str = Query(..., pattern="^(sido|sigungu|eupmyeondong|city)$"),
    region_code: str = Query(..., min_length=2, max_length=10),
    profile_version: str = Query("v1.1-national"),
    window_years: int = Query(5, ge=1, le=5),
    as_of_month: Optional[date] = Query(None),
    db: Session = Depends(get_collective_db),
):
    if db is None:
        raise HTTPException(503, "collective_stats DB 미연결")
    if not _table_exists(db, "regional_profile"):
        raise HTTPException(404, "regional_profile 테이블 없음 — pipeline rebuild 먼저")

    code = region_code.strip()
    params: dict[str, Any] = {
        "pv": profile_version,
        "level": region_level,
        "code": code,
        "wy": window_years,
    }

    if as_of_month is not None:
        params["as_of"] = as_of_month
        row = db.execute(
            text(
                """
                SELECT profile_version, region_level, region_code, as_of_month, window_years,
                       features, feature_count, builder_version, validation_status,
                       computed_at::text AS computed_at
                FROM regional_profile
                WHERE profile_version = :pv
                  AND region_level = :level
                  AND region_code = :code
                  AND window_years = :wy
                  AND as_of_month = :as_of
                LIMIT 1
                """
            ),
            params,
        ).mappings().first()
    else:
        row = db.execute(
            text(
                """
                SELECT profile_version, region_level, region_code, as_of_month, window_years,
                       features, feature_count, builder_version, validation_status,
                       computed_at::text AS computed_at
                FROM regional_profile
                WHERE profile_version = :pv
                  AND region_level = :level
                  AND region_code = :code
                  AND window_years = :wy
                ORDER BY as_of_month DESC
                LIMIT 1
                """
            ),
            params,
        ).mappings().first()

    if not row:
        raise HTTPException(
            404,
            detail=(
                f"Profile 없음: {profile_version} {region_level}/{code} "
                f"window={window_years}y"
            ),
        )

    meta = RegionalProfileMeta(
        profile_version=row["profile_version"],
        as_of_month=row["as_of_month"],
        window_years=row["window_years"],
        region_level=row["region_level"],
        region_code=row["region_code"],
        feature_count=row.get("feature_count"),
        builder_version=row.get("builder_version"),
        validation_status=row.get("validation_status") or "PENDING",
        computed_at=row.get("computed_at"),
    )
    feats = row.get("features") or {}
    if not isinstance(feats, dict):
        feats = dict(feats)
    return RegionalProfileResponse(meta=meta, features=feats)


@router.get("/twins/{eupmyeondong_code}", response_model=ProfileTwinNeighborsResponse)
def get_profile_twin_neighbors(
    eupmyeondong_code: str,
    profile_version: str = Query("v1.1-national"),
    window_years: int = Query(5, ge=1, le=5),
    top_k: int = Query(3, ge=1, le=10),
    algorithm_version: int = Query(6, ge=5, le=6, description="6=hybrid, 5=profile-only"),
    db: Session = Depends(get_collective_db),
):
    """쌍둥이 읍면동 Top-k — hybrid(v6) 기본, profile-only(v5) fallback."""
    if db is None:
        raise HTTPException(503, "collective_stats DB 미연결")
    if not _table_exists(db, "twin_eupmyeondong_neighbor_mvp"):
        raise HTTPException(404, "twin 테이블 없음 — build_twin_hybrid.py 또는 build_twin_from_profile.py 실행")

    anchor = eupmyeondong_code.strip()[:8]
    if len(anchor) < 8:
        raise HTTPException(400, "eupmyeondong_code 8자리 필요")

    window_candidates = [window_years]
    for alt in (5, 3):
        if alt not in window_candidates:
            window_candidates.append(alt)

    algo_candidates = [algorithm_version]
    if algorithm_version == 6 and 5 not in algo_candidates:
        algo_candidates.append(5)

    batch_row = None
    resolved_window = window_years
    resolved_algo = algorithm_version
    for wy in window_candidates:
        for av in algo_candidates:
            batch_row = db.execute(
                text(
                    """
                    SELECT batch_key, MAX(computed_at) AS computed_at
                    FROM twin_eupmyeondong_neighbor_mvp
                    WHERE algorithm_version = :av
                      AND detail_scores->>'profile_version' = :pv
                      AND (detail_scores->>'window_years')::int = :wy
                    GROUP BY batch_key
                    ORDER BY computed_at DESC
                    LIMIT 1
                    """
                ),
                {"pv": profile_version, "wy": wy, "av": av},
            ).mappings().first()
            if batch_row:
                resolved_window = wy
                resolved_algo = av
                break
        if batch_row:
            break

    if not batch_row:
        return ProfileTwinNeighborsResponse(
            profile_version=profile_version,
            window_years=window_years,
            algorithm_version=algorithm_version,
            anchor_eupmyeondong_code=anchor,
            neighbors=[],
        )

    batch_key = batch_row["batch_key"]
    rows = db.execute(
        text(
            """
            SELECT rank,
                   twin_eupmyeondong_code,
                   twin_eupmyeondong_name,
                   twin_sigungu_name,
                   twin_sido_name,
                   similarity_score,
                   detail_scores
            FROM twin_eupmyeondong_neighbor_mvp
            WHERE batch_key = :bk
              AND anchor_eupmyeondong_code = :anchor
            ORDER BY rank
            LIMIT :top_k
            """
        ),
        {"bk": batch_key, "anchor": anchor, "top_k": top_k},
    ).mappings().all()

    as_of = None
    neighbors: list[ProfileTwinNeighborItem] = []
    for r in rows:
        detail = r.get("detail_scores") or {}
        if not isinstance(detail, dict):
            detail = dict(detail)
        if as_of is None and detail.get("as_of_month"):
            try:
                as_of = date.fromisoformat(str(detail["as_of_month"])[:10])
            except ValueError:
                pass
        neighbors.append(
            ProfileTwinNeighborItem(
                rank=int(r["rank"]),
                twin_eupmyeondong_code=str(r["twin_eupmyeondong_code"]).strip(),
                twin_eupmyeondong_name=str(r["twin_eupmyeondong_name"]),
                twin_sigungu_name=str(r["twin_sigungu_name"]),
                twin_sido_name=str(r["twin_sido_name"]),
                similarity_score=float(r["similarity_score"]),
                detail_scores=detail,
            )
        )

    return ProfileTwinNeighborsResponse(
        profile_version=profile_version,
        window_years=resolved_window,
        algorithm_version=resolved_algo,
        as_of_month=as_of,
        batch_key=batch_key,
        anchor_eupmyeondong_code=anchor,
        neighbors=neighbors,
    )
