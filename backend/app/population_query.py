"""연도별 통계와 법정동 연말 인구(population_stats) 병합."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import YearlyTradeStat


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
