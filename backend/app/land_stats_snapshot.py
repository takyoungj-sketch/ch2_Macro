from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.v2_stats_windows import default_as_of_month_for_service


def latest_land_stats_publication(
    db: Session, *, as_of_month: date | None = None,
) -> tuple[date, datetime] | None:
    """월간 검증을 통과한 기준월과 그 달의 갱신 버전. 기존 DB에는 테이블이 없을 수 있다."""
    if db.execute(text("SELECT to_regclass('public.land_stats_v2_publications')")).scalar() is None:
        return None
    row = db.execute(text("""
        SELECT as_of_month, published_at
        FROM land_stats_v2_publications
        WHERE (:as_of IS NULL OR as_of_month = :as_of)
        ORDER BY as_of_month DESC
        LIMIT 1
    """), {"as_of": as_of_month}).fetchone()
    return (row.as_of_month, row.published_at) if row else None


def preferred_land_stats_month(db: Session, explicit: date | None) -> date | None:
    if explicit is not None:
        return explicit
    if settings.stats_v2_default_as_of_month is not None:
        return settings.stats_v2_default_as_of_month
    if settings.stats_v2_assumed_today is not None:
        return default_as_of_month_for_service(settings.stats_v2_assumed_today)
    publication = latest_land_stats_publication(db)
    return publication[0] if publication else None
