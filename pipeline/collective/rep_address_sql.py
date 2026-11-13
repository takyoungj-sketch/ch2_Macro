"""mart 대표 주소 규칙(집합 2단계 A-3).

이전: 주소 열마다 MAX() → 어느 거래에도 없는 합성 주소(우암동 + 내수읍 코드 등).
지금: 그룹(키·유형[·연도])별로 거래가 가장 많은 (addr3, addr4, addr5, beopjungri_code, lot_number, road_name)
      한 세트를 그대로 쓴다. 동률이면 최신 계약일, 그다음 코드·지번·도로명·addr4·addr5 오름차순(결정적).
집합 주거 building_stats(rolling·annual)·분양권 lifetime·임대 building_stats 가 같은 함수를 쓴다.
"""
from __future__ import annotations

REP_TUPLE: tuple[str, ...] = ("addr3", "addr4", "addr5", "beopjungri_code", "lot_number", "road_name")
# 동률 깨기 순서(앞이 우선)
_TIE_ORDER: tuple[str, ...] = ("beopjungri_code", "lot_number", "road_name", "addr4", "addr5", "addr3")


def rep_address_query(
    *,
    base_sql: str,
    group_cols: list[str],
    aggregates: str,
    rep_cols: tuple[str, ...] = REP_TUPLE,
    rep_extra_max: tuple[str, ...] = ("sigungu_code",),
) -> str:
    """base_sql 은 group_cols·rep_cols·rep_extra_max·contract_date 와 aggregates 가 쓰는 열을 내보내야 한다.

    aggregates 는 b.<열> 로 base 를 참조한다(예: "MAX(b.display_name) AS display_name").
    결과 열: group_cols, rep_cols, rep_extra_max, aggregates.
    """
    g = ", ".join(group_cols)
    rc = ", ".join(rep_cols)
    extra_sel = "".join(f", MAX({c}) AS {c}" for c in rep_extra_max)
    extra_cols = "".join(f", {c}" for c in rep_extra_max)
    tie = ", ".join(f"{c} NULLS LAST" for c in _TIE_ORDER if c in rep_cols)
    # `=` 조인(해시 조인). 옛 `IS NOT DISTINCT FROM` 은 해시·머지가 안 돼 중첩 루프(base 행 × 그룹 수)로
    # 경기 annual 한 쿼리가 10시간을 넘겼다. 그룹 열에 NULL 이 있으면 `=` 는 그 행을 조용히 빠뜨리므로
    # 조인 전에 NULL 행 수를 세서 0이 아니면 쿼리 자체를 오류로 끝낸다(_null_guard_sql).
    join_on = " AND ".join(f"b.{c} = r.{c}" for c in group_cols)
    out_rep = ", ".join(f"r.{c}" for c in (*rep_cols, *rep_extra_max))
    grp_rep = ", ".join(f"r.{c}" for c in (*rep_cols, *rep_extra_max))
    return f"""
WITH base AS (
{base_sql}
), rep_g AS (
    SELECT {g}, {rc}{extra_sel}, count(*) AS _n, max(contract_date) AS _d
    FROM base
    GROUP BY {g}, {rc}
), rep AS (
    SELECT DISTINCT ON ({g}) {g}, {rc}{extra_cols}
    FROM rep_g
    ORDER BY {g}, _n DESC, _d DESC NULLS LAST{", " + tie if tie else ""}
)
SELECT {", ".join("b." + c for c in group_cols)}, {out_rep},
       {aggregates}
FROM base b
JOIN rep r ON {join_on}
WHERE {_null_guard_sql(group_cols)} = 0
GROUP BY {", ".join("b." + c for c in group_cols)}, {grp_rep}
"""


NULL_GUARD_TAG = "rep_address_query: group_cols NULL"


def _null_guard_sql(group_cols: list[str]) -> str:
    """base 의 그룹 열 NULL 행 수. 0이면 0, 아니면 정수 변환 오류로 쿼리를 멈춘다.

    상관 없는 하위 쿼리라 PostgreSQL 이 실행 시작 때 한 번 평가한다(One-Time Filter) —
    조인 결과가 0행이어도(전부 NULL) 오류가 난다.
    """
    cond = " OR ".join(f"{c} IS NULL" for c in group_cols)
    cols = ", ".join(group_cols)
    return (
        f"(SELECT CASE WHEN count(*) = 0 THEN 0 "
        f"ELSE ('{NULL_GUARD_TAG} rows=' || count(*) || ' ({cols})')::int END "
        f"FROM base WHERE {cond})"
    )
