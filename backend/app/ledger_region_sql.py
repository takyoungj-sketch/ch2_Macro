"""토지 원장 핫패스 — 지역 코드 SQL 조건 규칙.

사고(2026-08): `beopjungri_code = ANY(:list)` 가 Parallel Seq Scan 을 자주 유발해
기본통계 ~20s · 모달(matrix-yearly 롤링) ~45s 까지 늘었다.
단건 `=` / 복수 expanding `IN` 으로 Index Scan(~ms) 을 유도한다.

규칙 SSOT: docs/LAND_LEDGER_QUERY_PERF.md
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Result
from sqlalchemy.orm import Session


# params 에 이 키가 True 이면 execute 시 expanding bind 적용
EXPAND_REGION_CODES_FLAG = "_expand_region_codes"
EXPAND_FILTER_YEARS_FLAG = "_expand_filter_years"


def beopjungri_eq_or_in(
    codes: list[str],
    *,
    column: str = "beopjungri_code",
    eq_key: str = "region_code",
    in_key: str = "region_codes",
    expand_flag: str = EXPAND_REGION_CODES_FLAG,
) -> tuple[str, dict[str, Any]]:
    """선택적 법정동 조회용 `=` / expanding `IN` 조각.

    Returns:
        (sql_predicate, params) — params 에 expand_flag 가 있으면 execute_expanding 필수.
    """
    cleaned = [str(c).strip() for c in codes if c is not None and str(c).strip()]
    if not cleaned:
        raise ValueError("beopjungri codes must be non-empty")
    if len(cleaned) == 1:
        return f"{column} = :{eq_key}", {eq_key: cleaned[0]}
    return (
        f"{column} IN :{in_key}",
        {in_key: cleaned, expand_flag: True},
    )


def execute_expanding(db: Session, sql: str, params: dict[str, Any]) -> Result:
    """region_codes / filter_years expanding IN 을 지원하는 execute.

    params 에서 ``_expand_*`` 플래그를 pop 한 뒤 bindparams 적용.
    """
    stmt = text(sql)
    binds = []
    p = dict(params)
    if p.pop(EXPAND_REGION_CODES_FLAG, False):
        binds.append(bindparam("region_codes", expanding=True))
    if p.pop(EXPAND_FILTER_YEARS_FLAG, False):
        binds.append(bindparam("filter_years", expanding=True))
    # free_v2 등 별도 키명
    if p.pop("_expand_codes", False):
        binds.append(bindparam("codes", expanding=True))
    if binds:
        stmt = stmt.bindparams(*binds)
    return db.execute(stmt, p)
