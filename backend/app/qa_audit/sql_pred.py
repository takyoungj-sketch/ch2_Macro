"""원장 지역 조건 — ``=`` / expanding ``IN``. ``ANY`` 금지."""

from __future__ import annotations

from typing import Any


def code_eq_or_in(
    codes: list[str],
    *,
    column: str,
    eq_key: str,
    in_key: str,
) -> tuple[str, dict[str, Any]]:
    cleaned = [str(c).strip() for c in codes if c is not None and str(c).strip()]
    if not cleaned:
        raise ValueError("region codes must be non-empty")
    if len(cleaned) == 1:
        return f"{column} = :{eq_key}", {eq_key: cleaned[0]}
    return f"{column} IN :{in_key}", {in_key: cleaned, "_expand_keys": [in_key]}


def ledger_admin_predicate(
    codes: list[str],
    *,
    region_level: str,
) -> tuple[str, dict[str, Any]]:
    """L1/L2 원장 필터. 코드 컬럼 또는 법정동 prefix.

    eup: ``eupmyeondong_code`` OR ``LEFT(beopjungri_code, 8)``
    sigungu: ``sigungu_code`` OR ``LEFT(beopjungri_code, 5)``
    sido: ``sido_code`` OR ``LEFT(beopjungri_code, 2)``
    """
    cleaned = [str(c).strip() for c in codes if c is not None and str(c).strip()]
    if not cleaned:
        raise ValueError("region codes must be non-empty")

    level = region_level.strip()
    if level == "eupmyeondong":
        col, prefix_n, eq_key, in_key = "eupmyeondong_code", 8, "eup_code", "eup_codes"
    elif level == "sigungu":
        col, prefix_n, eq_key, in_key = "sigungu_code", 5, "sg_code", "sg_codes"
    elif level == "sido":
        col, prefix_n, eq_key, in_key = "sido_code", 2, "sido_code", "sido_codes"
    else:
        raise ValueError(f"unsupported region_level: {region_level}")

    left_expr = f"LEFT(btrim(COALESCE(beopjungri_code::text, '')), {prefix_n})"
    if len(cleaned) == 1:
        return (
            f"({col} = :{eq_key} OR {left_expr} = :{eq_key})",
            {eq_key: cleaned[0]},
        )
    return (
        f"({col} IN :{in_key} OR {left_expr} IN :{in_key})",
        {in_key: cleaned, "_expand_keys": [in_key]},
    )


def execute_sql(conn, sql: str, params: dict[str, Any] | None = None):
    from sqlalchemy import bindparam, text

    p = dict(params or {})
    expand_keys = list(p.pop("_expand_keys", []) or [])
    stmt = text(sql)
    if expand_keys:
        stmt = stmt.bindparams(*[bindparam(k, expanding=True) for k in expand_keys])
    return conn.execute(stmt, p)
