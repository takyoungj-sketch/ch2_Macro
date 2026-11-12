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
    join_on = " AND ".join(f"b.{c} IS NOT DISTINCT FROM r.{c}" for c in group_cols)
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
GROUP BY {", ".join("b." + c for c in group_cols)}, {grp_rep}
"""
