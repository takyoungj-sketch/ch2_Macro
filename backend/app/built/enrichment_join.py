"""거래 목록·회귀 표본에 표제부 enrichment 를 붙인다."""

from __future__ import annotations

# 국토계획법 대분류. 세부가 있으면 용도지역 값이 아니다 (D-047).
# 원장(상업·공장) 표기는 접미사 '지역' 없음 — 제2종일반주거.
ZONE_COARSE_LABELS = frozenset(
    {
        "도시지역",
        "도시지역기타",
        "도시지역미지정",
        "도시지역미분류",
        "비도시지역",
        "관리지역",
        "관리지역미분류",
        "공업지역",
        "도시관리계획 입안중",
    }
)

_COARSE_SQL = ", ".join("'" + x.replace("'", "''") + "'" for x in sorted(ZONE_COARSE_LABELS))

# 결합 키는 '법정동코드|지번'. 호버에는 지번만.
RECOVERED_LOT_SQL = """
CASE
  WHEN e.recovered_lot IS NULL THEN NULL
  WHEN position('|' in e.recovered_lot) > 0 THEN NULLIF(split_part(e.recovered_lot, '|', 2), '')
  ELSE e.recovered_lot
END
"""

# 원장 한 칸. 대분류면 버리고, 끝의 '지역'만 뗀다 (개발제한구역은 그대로).
_LEDGER_CANON_SQL = f"""
(
  SELECT CASE
           WHEN z IS NULL OR z = '' OR lower(z) = 'nan' OR z IN ({_COARSE_SQL}) THEN NULL
           WHEN z ~ '지역$' THEN NULLIF(regexp_replace(z, '지역$', ''), '')
           ELSE z
         END
  FROM (SELECT btrim(s.zone_type::text) AS z) q
)
"""

# 세부를 고르고, 상업·공장 원장과 같이 끝의 '지역'만 뗀다. 목록·회귀가 같은 문자열.
ZONE_CANON_SQL = f"""
(
  SELECT CASE
           WHEN lab ~ '지역$' THEN regexp_replace(lab, '지역$', '')
           ELSE lab
         END
  FROM (
    SELECT btrim(p.part) AS lab
    FROM unnest(COALESCE(e.zone_labels, ARRAY[]::text[])) WITH ORDINALITY AS t(x, ord)
    CROSS JOIN LATERAL unnest(string_to_array(COALESCE(x::text, ''), ','))
      WITH ORDINALITY AS p(part, pord)
    WHERE btrim(COALESCE(p.part, '')) <> ''
      AND lower(btrim(p.part)) <> 'nan'
      AND btrim(p.part) NOT IN ({_COARSE_SQL})
    ORDER BY t.ord, p.pord
    LIMIT 1
  ) picked
)
"""

ZONE_DISPLAY_SQL = f"""
COALESCE(
  {_LEDGER_CANON_SQL},
  {ZONE_CANON_SQL}
)
"""

ZONE_FIRST_SQL = ZONE_DISPLAY_SQL


def canonical_zone_label(labels: list[str] | None) -> str | None:
    """세부 용도지역 하나. 도시지역 등 대분류는 버리고 원장 표기(지역 접미사 없음)로 맞춘다."""
    picked: str | None = None
    for raw in labels or []:
        for part in str(raw).split(","):
            t = part.strip()
            if not t or t.lower() == "nan" or t in ZONE_COARSE_LABELS:
                continue
            picked = t
            break
        if picked:
            break
    if not picked:
        return None
    if picked.endswith("지역"):
        picked = picked[:-2]
    return picked or None


def display_recovered_lot(raw: str | None) -> str | None:
    """결합 키에서 지번만. 칸 값이 아니라 호버용."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if "|" in s:
        s = s.split("|", 1)[1].strip()
    return s or None


def wrap_tx_enrichment(
    inner_sql: str,
    *,
    extra_outer: str = "",
    enrich: bool = False,
    zone_types: list[str] | None = None,
) -> str:
    """inner_sql 은 transaction_hash 와 zone_type 을 포함해야 한다.

    enrich=False(기본): 원장만. 조인하지 않는다 (D-051).
    enrich=True: LEFT JOIN. zone_types 가 있으면 표시 용도지역(c.canon)으로 거른다.
    """
    if not enrich:
        return inner_sql
    extra = f",\n          {extra_outer.strip().rstrip(',')}" if extra_outer.strip() else ""
    zone_where = ""
    if zone_types:
        zone_where = "\n        WHERE c.canon = ANY(:zone_types)"
    return f"""
        SELECT s.*,
               c.canon AS zone_type_filled,
               c.canon AS zone_type_first,
               e.structure_group,
               {RECOVERED_LOT_SQL} AS recovered_lot,
               e.match_tier AS match_tier,
               e.match_rule AS match_rule
               {extra}
        FROM ({inner_sql}) s
        LEFT JOIN built_transaction_enrichment e
          ON e.transaction_hash = s.transaction_hash
        CROSS JOIN LATERAL (
          SELECT {ZONE_DISPLAY_SQL} AS canon
        ) c{zone_where}
    """


def apply_wrapped_zone_columns(df):
    """enrich 조인 결과의 표시 용도지역을 zone_type 칸에 옮긴다."""
    import pandas as pd

    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    if "zone_type_first" in df.columns:
        df = df.copy()
        df["zone_type"] = df["zone_type_first"]
        df = df.drop(columns=["zone_type_filled", "zone_type_first"], errors="ignore")
    return df.drop(columns=["transaction_hash", "recovered_lot"], errors="ignore")
