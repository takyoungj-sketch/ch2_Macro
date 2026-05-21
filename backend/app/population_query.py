"""연도별 통계와 법정동 연말 인구(population_stats) 병합."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import RegionLevel, YearlyTradeStat


def _sigungu_codes_for_city_bucket(db: Session, city_code: str) -> list[str]:
    """시군구코드 floor/10*10 버킷에 속하는 sigungu (upper_stats.city 와 동일 규칙)."""
    cc = (city_code or "").strip()
    if not cc.isdigit():
        return []
    rows = db.execute(
        text(
            """
            SELECT DISTINCT btrim(sigungu_code::text) AS sg
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND btrim(sigungu_code::text) ~ '^[0-9]{5}$'
              AND (CAST(btrim(sigungu_code::text) AS INTEGER) / 10 * 10)
                  = CAST(:cc AS INTEGER)
            """
        ),
        {"cc": int(cc)},
    ).fetchall()
    return sorted({str(r.sg).strip() for r in rows if r.sg})


def list_beopjungri_codes_under_population_scope(
    db: Session,
    *,
    level: RegionLevel,
    code: str,
) -> list[str]:
    """
    연말 인구 합산에 쓸 하위 법정동·리 코드 목록(region_codes 기준).

    sido / sigungu / eupmyeondong / city(자치구 묶음) 상위 코드를 펼친다.
    """
    c = (code or "").strip()
    if not c:
        return []

    if level == "sido":
        q = text(
            """
            SELECT DISTINCT btrim(beopjungri_code::text) AS bc
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND btrim(beopjungri_code::text) <> ''
              AND btrim(sido_code::text) = :c
            """
        )
        params = {"c": c}
    elif level == "sigungu":
        q = text(
            """
            SELECT DISTINCT btrim(beopjungri_code::text) AS bc
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND btrim(beopjungri_code::text) <> ''
              AND btrim(sigungu_code::text) = :c
            """
        )
        params = {"c": c}
    elif level == "eupmyeondong":
        q = text(
            """
            SELECT DISTINCT btrim(beopjungri_code::text) AS bc
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND btrim(beopjungri_code::text) <> ''
              AND btrim(eupmyeondong_code::text) = :c
            """
        )
        params = {"c": c}
    elif level == "city":
        sgs = _sigungu_codes_for_city_bucket(db, c)
        if not sgs:
            return []
        q = text(
            """
            SELECT DISTINCT btrim(beopjungri_code::text) AS bc
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND btrim(beopjungri_code::text) <> ''
              AND btrim(sigungu_code::text) = ANY(:sgs)
            """
        )
        params = {"sgs": sgs}
    else:
        return []

    rows = db.execute(q, params).fetchall()
    out = sorted({str(r.bc).strip() for r in rows if r.bc})
    return out


def attach_population_year_end(
    db: Session,
    *,
    region_codes: list[str],
    items: list[YearlyTradeStat],
) -> list[YearlyTradeStat]:
    """
    선택 법정동·리 코드 집합에 대해 stats_month=12(또는 NULL을 연말로 간주) 인구 합계를
    연도별로 조회해 YearlyTradeStat.population_year_end 에 채운다.
    DB에 해당 연도·코드 데이터가 없으면 None.
    """
    if not items:
        return items
    codes_norm = [str(c).strip() for c in region_codes if str(c).strip()]
    if not codes_norm:
        return items

    years = sorted({int(it.year) for it in items})
    stmt = text(
        """
        WITH latest AS (
            SELECT DISTINCT ON (stats_year, btrim(cast(admin_code AS text)))
                stats_year,
                btrim(cast(admin_code AS text)) AS ac,
                total_population
            FROM population_stats
            WHERE admin_level = 'beopjungri'
              AND btrim(cast(admin_code AS text)) = ANY(:codes)
              AND stats_year = ANY(:years)
            ORDER BY stats_year, btrim(cast(admin_code AS text)),
                     stats_month DESC NULLS LAST
        )
        SELECT stats_year::int AS y,
               SUM(total_population)::bigint AS pop
        FROM latest
        GROUP BY stats_year
        """
    )
    rows = db.execute(stmt, {"codes": codes_norm, "years": years}).fetchall()
    pop_by_year = {int(r.y): int(r.pop) for r in rows if r.pop is not None}

    out: list[YearlyTradeStat] = []
    for it in items:
        y = int(it.year)
        pop = pop_by_year.get(y)
        out.append(it.model_copy(update={"population_year_end": pop}))
    return out


def attach_population_year_end_for_upper_level(
    db: Session,
    *,
    level: RegionLevel,
    upper_code: str,
    items: list[YearlyTradeStat],
) -> list[YearlyTradeStat]:
    """상위 행정(시도·시군구·읍면동·city) 단건 화면용 — 산하 법정단위 연말 인구 합산."""
    codes = list_beopjungri_codes_under_population_scope(
        db, level=level, code=upper_code
    )
    return attach_population_year_end(db, region_codes=codes, items=items)
