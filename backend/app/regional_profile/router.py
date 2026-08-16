"""Regional Profile API — collective_stats.regional_profile 조회."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.db import get_collective_db
from app.db import get_db
from app.region_canonical import resolve_to_canonical

router = APIRouter(prefix="/regional-profile", tags=["regional-profile"])


def _canonical_profile_code(land_db, *, region_level: str, region_code: str) -> str:
    """D-028: profile grain keys must be canonical (not historical eup/beop)."""
    code = region_code.strip()
    lv = region_level.strip().lower()
    probe = code[:8] if lv == "eupmyeondong" and len(code) >= 8 else code
    resolved = resolve_to_canonical(land_db, [probe])
    out = resolved[0] if resolved else probe
    if lv == "eupmyeondong":
        return out[:8]
    return out


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
    twin_eupmyeondong_code: str | None = None
    twin_eupmyeondong_name: str | None = None
    twin_beopjungri_code: str | None = None
    twin_beopjungri_name: str | None = None
    twin_sigungu_code: str | None = None
    twin_sigungu_name: str
    twin_sido_name: str
    similarity_score: float
    detail_scores: dict[str, Any] = Field(default_factory=dict)


class ProfileTwinNeighborsResponse(BaseModel):
    profile_version: str
    window_years: int
    algorithm_version: int = 21
    scope: Optional[str] = None
    as_of_month: Optional[date] = None
    batch_key: Optional[str] = None
    anchor_eupmyeondong_code: str | None = None
    anchor_beopjungri_code: str | None = None
    neighbors: list[ProfileTwinNeighborItem] = Field(default_factory=list)


class ProfileSigunguTwinItem(BaseModel):
    rank: int
    twin_sigungu_code: str
    twin_sigungu_name: str
    twin_sido_name: str
    similarity_score: float
    detail_scores: dict[str, Any] = Field(default_factory=dict)


class ProfileSigunguTwinsResponse(BaseModel):
    profile_version: str
    window_years: int
    scope: Optional[str] = None
    batch_key: Optional[str] = None
    anchor_sigungu_code: str
    neighbors: list[ProfileSigunguTwinItem] = Field(default_factory=list)


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
    region_level: str = Query(..., pattern="^(sido|sigungu|eupmyeondong|beopjungri|city)$"),
    region_code: str = Query(..., min_length=2, max_length=10),
    profile_version: str = Query("v2.1-national"),
    window_years: int = Query(3, ge=1, le=5),
    as_of_month: Optional[date] = Query(None),
    db: Session = Depends(get_collective_db),
    land_db: Session = Depends(get_db),
):
    if db is None:
        raise HTTPException(503, "collective_stats DB 미연결")
    if not _table_exists(db, "regional_profile"):
        raise HTTPException(404, "regional_profile 테이블 없음 — pipeline rebuild 먼저")

    code = _canonical_profile_code(
        land_db, region_level=region_level, region_code=region_code
    )
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


PROFILE_TWIN_ALGORITHM = 21


def _resolve_twin_batch(
    db: Session,
    *,
    table: str,
    profile_version: str,
    window_years: int,
    scope: str | None,
    twin_profile: str = "general",
) -> tuple[dict | None, int]:
    """최신 batch_key 조회 (algo 21 only). (batch_row, resolved_window)."""
    window_candidates = [window_years]
    if 3 not in window_candidates:
        window_candidates.append(3)

    for wy in window_candidates:
        scope_clause = ""
        params: dict[str, Any] = {
            "pv": profile_version,
            "wy": wy,
            "av": PROFILE_TWIN_ALGORITHM,
            "tp": twin_profile or "general",
        }
        if scope:
            scope_clause = " AND detail_scores->>'scope' = :scope "
            params["scope"] = scope
        batch_row = db.execute(
            text(
                f"""
                SELECT batch_key, MAX(computed_at) AS computed_at
                FROM {table}
                WHERE algorithm_version = :av
                  AND detail_scores->>'profile_version' = :pv
                  AND (detail_scores->>'window_years')::int = :wy
                  AND COALESCE(detail_scores->>'twin_profile', 'general') = :tp
                  {scope_clause}
                GROUP BY batch_key
                ORDER BY computed_at DESC
                LIMIT 1
                """
            ),
            params,
        ).mappings().first()
        if batch_row:
            return batch_row, wy
    return None, window_years


def _resolve_beop_twin_batch(
    db: Session,
    *,
    profile_version: str,
    window_years: int,
    twin_profile: str = "general",
) -> tuple[dict | None, int]:
    """beop Twin 배치 — Profile-native(algo 21). 저장 테이블명은 twin_neighbor_v8 유지."""
    scope = "same_sigungu"
    window_candidates = [window_years]
    if 3 not in window_candidates:
        window_candidates.append(3)

    for wy in window_candidates:
        batch_row = db.execute(
            text(
                """
                SELECT batch_key, MAX(computed_at) AS computed_at
                FROM twin_neighbor_v8
                WHERE algorithm_version = :av
                  AND region_level = 'beopjungri'
                  AND detail_scores->>'profile_version' = :pv
                  AND (detail_scores->>'window_years')::int = :wy
                  AND detail_scores->>'scope' = :scope
                  AND COALESCE(detail_scores->>'twin_profile', 'general') = :tp
                GROUP BY batch_key
                ORDER BY computed_at DESC
                LIMIT 1
                """
            ),
            {
                "pv": profile_version,
                "wy": wy,
                "av": PROFILE_TWIN_ALGORITHM,
                "scope": scope,
                "tp": twin_profile or "general",
            },
        ).mappings().first()
        if batch_row:
            return batch_row, wy
    return None, window_years


@router.get("/twins/{eupmyeondong_code}", response_model=ProfileTwinNeighborsResponse)
def get_profile_twin_neighbors(
    eupmyeondong_code: str,
    profile_version: str = Query("v2.1-national"),
    window_years: int = Query(3, ge=1, le=5),
    top_k: int = Query(3, ge=1, le=20),
    scope: str = Query("region", pattern="^(adjacent|region|national)$"),
    twin_profile: str = Query("general", pattern="^(general|built_commercial)$"),
    db: Session = Depends(get_collective_db),
    land_db: Session = Depends(get_db),
):
    """쌍둥이 읍면동 Top-k — Regional Profile 기반 Twin (algo 21)만.

    scope: region(권역, 기본) / national(전국) / adjacent.
    """
    if db is None:
        raise HTTPException(503, "collective_stats DB 미연결")
    if not _table_exists(db, "twin_eupmyeondong_neighbor_mvp"):
        raise HTTPException(404, "twin 테이블 없음 — build_twin_profile.py 실행")

    anchor = _canonical_profile_code(
        land_db, region_level="eupmyeondong", region_code=eupmyeondong_code
    )
    if len(anchor) < 8:
        raise HTTPException(400, "eupmyeondong_code 8자리 필요")

    batch_row, resolved_window = _resolve_twin_batch(
        db,
        table="twin_eupmyeondong_neighbor_mvp",
        profile_version=profile_version,
        window_years=window_years,
        scope=scope,
        twin_profile=twin_profile,
    )

    if not batch_row:
        return ProfileTwinNeighborsResponse(
            profile_version=profile_version,
            window_years=window_years,
            algorithm_version=PROFILE_TWIN_ALGORITHM,
            scope=scope,
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
        algorithm_version=PROFILE_TWIN_ALGORITHM,
        scope=scope,
        as_of_month=as_of,
        batch_key=batch_key,
        anchor_eupmyeondong_code=anchor,
        neighbors=neighbors,
    )


@router.get("/twins-sigungu/{sigungu_code}", response_model=ProfileSigunguTwinsResponse)
def get_profile_twin_sigungu(
    sigungu_code: str,
    profile_version: str = Query("v2.1-national"),
    window_years: int = Query(3, ge=1, le=5),
    top_k: int = Query(5, ge=1, le=20),
    scope: str = Query("national", pattern="^(adjacent|region|national)$"),
    twin_profile: str = Query("general", pattern="^(general|built_commercial)$"),
    db: Session = Depends(get_collective_db),
):
    """쌍둥이 시군구 Top-k — Regional Profile 기반 Twin (algo 21)만."""
    if db is None:
        raise HTTPException(503, "collective_stats DB 미연결")
    if not _table_exists(db, "twin_region_neighbor_mvp"):
        raise HTTPException(404, "twin_region 테이블 없음 — build_twin_profile.py 실행")

    anchor = sigungu_code.strip()[:5]
    if len(anchor) < 5:
        raise HTTPException(400, "sigungu_code 5자리 필요")

    batch_row, resolved_window = _resolve_twin_batch(
        db,
        table="twin_region_neighbor_mvp",
        profile_version=profile_version,
        window_years=window_years,
        scope=scope,
        twin_profile=twin_profile,
    )

    if not batch_row:
        return ProfileSigunguTwinsResponse(
            profile_version=profile_version,
            window_years=window_years,
            scope=scope,
            anchor_sigungu_code=anchor,
            neighbors=[],
        )

    batch_key = batch_row["batch_key"]
    rows = db.execute(
        text(
            """
            SELECT rank, twin_sigungu_code, twin_sigungu_name, twin_sido_name,
                   similarity_score, detail_scores
            FROM twin_region_neighbor_mvp
            WHERE batch_key = :bk AND anchor_sigungu_code = :anchor
            ORDER BY rank
            LIMIT :top_k
            """
        ),
        {"bk": batch_key, "anchor": anchor, "top_k": top_k},
    ).mappings().all()

    neighbors: list[ProfileSigunguTwinItem] = []
    for r in rows:
        detail = r.get("detail_scores") or {}
        if not isinstance(detail, dict):
            detail = dict(detail)
        neighbors.append(
            ProfileSigunguTwinItem(
                rank=int(r["rank"]),
                twin_sigungu_code=str(r["twin_sigungu_code"]).strip(),
                twin_sigungu_name=str(r["twin_sigungu_name"]),
                twin_sido_name=str(r["twin_sido_name"]),
                similarity_score=float(r["similarity_score"]),
                detail_scores=detail,
            )
        )

    return ProfileSigunguTwinsResponse(
        profile_version=profile_version,
        window_years=resolved_window,
        scope=scope,
        batch_key=batch_key,
        anchor_sigungu_code=anchor,
        neighbors=neighbors,
    )


@router.get("/twins-beop/{beopjungri_code}", response_model=ProfileTwinNeighborsResponse)
def get_profile_twin_beop(
    beopjungri_code: str,
    profile_version: str = Query("v2.1-national"),
    window_years: int = Query(3, ge=1, le=5),
    top_k: int = Query(3, ge=1, le=20),
    twin_profile: str = Query("general", pattern="^(general|built_commercial)$"),
    db: Session = Depends(get_db),
    land_db: Session = Depends(get_db),
):
    """쌍둥이 법정리 Top-k — Regional Profile 기반 Twin (algo 21), 동일 시군구만."""
    if not _table_exists(db, "twin_neighbor_v8"):
        raise HTTPException(
            404,
            "twin_neighbor_v8 없음 — build_twin_profile.py --region-level beopjungri 실행",
        )

    anchor = _canonical_profile_code(
        land_db, region_level="beopjungri", region_code=beopjungri_code
    )
    if len(anchor) < 10:
        raise HTTPException(400, "beopjungri_code 10자리 필요")

    batch_row, resolved_window = _resolve_beop_twin_batch(
        db,
        profile_version=profile_version,
        window_years=window_years,
        twin_profile=twin_profile,
    )

    if not batch_row:
        return ProfileTwinNeighborsResponse(
            profile_version=profile_version,
            window_years=window_years,
            algorithm_version=PROFILE_TWIN_ALGORITHM,
            scope="same_sigungu",
            anchor_beopjungri_code=anchor,
            neighbors=[],
        )

    batch_key = batch_row["batch_key"]
    rows = db.execute(
        text(
            """
            SELECT rank,
                   twin_region_code,
                   twin_region_name,
                   twin_sigungu_name,
                   twin_sido_name,
                   similarity_score,
                   detail_scores
            FROM twin_neighbor_v8
            WHERE batch_key = :bk
              AND region_level = 'beopjungri'
              AND anchor_region_code = :anchor
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
                twin_beopjungri_code=str(r["twin_region_code"]).strip(),
                twin_beopjungri_name=str(r["twin_region_name"]),
                twin_sigungu_name=str(r["twin_sigungu_name"]),
                twin_sido_name=str(r["twin_sido_name"]),
                similarity_score=float(r["similarity_score"]),
                detail_scores=detail,
            )
        )

    return ProfileTwinNeighborsResponse(
        profile_version=profile_version,
        window_years=resolved_window,
        algorithm_version=PROFILE_TWIN_ALGORITHM,
        scope="same_sigungu",
        as_of_month=as_of,
        batch_key=batch_key,
        anchor_beopjungri_code=anchor,
        neighbors=neighbors,
    )


class TwinV2NeighborItem(BaseModel):
    rank: int
    region_code: str
    region_name: str = ""
    sigungu_name: str = ""
    sido_name: str = ""
    twin_score: float
    confidence: float
    structure_score: float | None = None
    market_score: float | None = None
    used_blocks: list[str] = Field(default_factory=list)
    dropped_blocks: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)
    v1_similarity: float | None = None


class TwinV2Response(BaseModel):
    engine: str = "v2"
    weight_version: str
    role: str
    region_level: str
    profile_version: str
    window_years: int
    as_of_month: str | None = None
    anchor: dict[str, Any] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)
    universe: dict[str, Any] = Field(default_factory=dict)
    neighbors: list[TwinV2NeighborItem] = Field(default_factory=list)


@router.get("/twins-v2", response_model=TwinV2Response)
def get_twins_v2(
    region_level: str = Query(..., pattern="^(sigungu|eupmyeondong|beopjungri)$"),
    region_code: str = Query(..., min_length=5, max_length=10),
    role: str = Query("compare", pattern="^(compare|pool)$"),
    top_k: int = Query(8, ge=1, le=30),
    n_hop: int | None = Query(None, ge=0, le=5),
    profile_version: str = Query("v2.1-national"),
    window_years: int = Query(3, ge=1, le=5),
    include_v1: bool = Query(True),
    db: Session = Depends(get_collective_db),
    land_db: Session = Depends(get_db),
):
    """랩 전용 Twin Engine V2. 제품 프로필 Twin 카드(algo 21)를 바꾸지 않는다."""
    if db is None:
        raise HTTPException(503, "collective_stats DB 미연결")
    if not _table_exists(db, "regional_profile"):
        raise HTTPException(404, "regional_profile 테이블 없음")

    from app.regional_profile.twin_v2 import rank_twins_v2

    try:
        payload = rank_twins_v2(
            db,
            land_db,
            region_level=region_level,
            region_code=region_code,
            role=role,
            top_k=top_k,
            n_hop=n_hop,
            profile_version=profile_version,
            window_years=window_years,
            include_v1=include_v1,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc

    return TwinV2Response(**payload)
