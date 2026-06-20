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
    profile_version: str = Query("v1.0-chungbuk"),
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
