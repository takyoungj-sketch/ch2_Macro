"""지역프로필용 주거 전월세 달력 연간 집계. 환산 없음."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.rent.query import ASSET_TYPES

RENT_PROFILE_TYPES = (
    ("apartment", "아파트"),
    ("detached", "단독다가구"),
    ("officetel", "오피스텔"),
    ("rowhouse", "연립다세대"),
)

_LEVELS = frozenset({"sido", "sigungu", "eupmyeondong", "beopjungri", "city"})


def completed_calendar_years(as_of: date, window_years: int) -> list[int]:
    """as_of 직전 완료 달력 연도 window_years개. 2026-07-01 · 3 → 2023,2024,2025."""
    last = as_of.year - 1
    n = max(1, int(window_years))
    return list(range(last - n + 1, last + 1))


def _city_sigungu_codes(conn: Connection, city_code: str) -> list[str]:
    cc = (city_code or "").strip()
    if not cc.isdigit():
        return []
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT btrim(sigungu_code::text) AS sg
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND btrim(sigungu_code::text) ~ '^[0-9]{5}$'
              AND (CAST(btrim(sigungu_code::text) AS INTEGER) / 10 * 10) = CAST(:cc AS INTEGER)
            """
        ),
        {"cc": int(cc)},
    ).fetchall()
    return sorted({str(r.sg).strip() for r in rows if r.sg})


def _region_sql(level: str, code: str, conn: Connection) -> tuple[str, dict[str, Any], bool]:
    """Returns (predicate, params, expand_sigungu)."""
    lv = (level or "").strip()
    c = (code or "").strip()
    if lv not in _LEVELS or not c:
        raise ValueError("region_level / region_code 가 필요합니다.")
    if lv == "beopjungri":
        return "beopjungri_code = :rc", {"rc": c}, False
    if lv == "eupmyeondong":
        return "eupmyeondong_code = :rc", {"rc": c}, False
    if lv == "sigungu":
        return "sigungu_code = :rc", {"rc": c}, False
    if lv == "sido":
        return "sido_code = :rc", {"rc": c}, False
    sgs = _city_sigungu_codes(conn, c)
    if not sgs:
        return "FALSE", {}, False
    if len(sgs) == 1:
        return "sigungu_code = :rc", {"rc": sgs[0]}, False
    return "sigungu_code IN :sgs", {"sgs": sgs}, True


def fetch_profile_yearly(
    conn: Connection,
    *,
    region_level: str,
    region_code: str,
    years: list[int],
) -> list[dict[str, Any]]:
    ys = sorted({int(y) for y in years if 1990 <= int(y) <= 2100})
    if not ys:
        return []
    pred, params, expand_sg = _region_sql(region_level, region_code, conn)
    if pred == "FALSE":
        return []
    params["y0"] = ys[0]
    params["y1"] = ys[-1]
    stmt = text(
        f"""
        SELECT
            asset_type,
            contract_year,
            COUNT(*)::int AS n,
            COALESCE(SUM(deposit_manwon), 0)::float AS deposit_sum,
            COALESCE(SUM(monthly_rent_manwon), 0)::float AS monthly_sum
        FROM rent_transactions
        WHERE is_valid
          AND asset_type IN ('apartment', 'detached', 'officetel', 'rowhouse')
          AND contract_year >= :y0
          AND contract_year <= :y1
          AND {pred}
        GROUP BY asset_type, contract_year
        """
    )
    if expand_sg:
        stmt = stmt.bindparams(bindparam("sgs", expanding=True))
    return [dict(r) for r in conn.execute(stmt, params).mappings().all()]


def build_profile_yearly_payload(
    conn: Connection,
    *,
    region_level: str,
    region_code: str,
    years: list[int],
) -> dict[str, Any]:
    rows = fetch_profile_yearly(
        conn, region_level=region_level, region_code=region_code, years=years
    )
    by: dict[tuple[str, int], dict[str, Any]] = {}
    for r in rows:
        by[(str(r["asset_type"]), int(r["contract_year"]))] = r

    types_out: list[dict[str, Any]] = []
    for asset, label in RENT_PROFILE_TYPES:
        year_cells: dict[str, dict[str, float | int]] = {}
        tot_n = 0
        tot_dep = 0.0
        tot_mon = 0.0
        for y in years:
            cell = by.get((asset, y))
            n = int(cell["n"]) if cell else 0
            dep = float(cell["deposit_sum"]) if cell else 0.0
            mon = float(cell["monthly_sum"]) if cell else 0.0
            year_cells[str(y)] = {"count": n, "deposit_sum": dep, "monthly_sum": mon}
            tot_n += n
            tot_dep += dep
            tot_mon += mon
        types_out.append(
            {
                "asset_type": asset,
                "label": label,
                "years": year_cells,
                "total_count": tot_n,
                "total_deposit_sum": tot_dep,
                "total_monthly_sum": tot_mon,
            }
        )

    return {
        "region_level": region_level,
        "region_code": region_code,
        "years": years,
        "types": types_out,
        "unit_deposit": "만원",
        "unit_monthly": "만/월",
    }
