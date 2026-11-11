"""F-1: 회귀 연식 보강 — 대장 정보 동의(enrich) 시에만.

순서는 간이 토지 배분단가(`frontend-built/src/utils/allocationCost.ts::allocationAge`)와 같다.
실거래 건축연도(원장 `building_age`)가 있으면 그대로, 없을 때만 대장 사용승인연도로
`계약연도 − 사용승인연도`(0 미만은 0)를 쓴다. 원장은 UPDATE하지 않는다 (D-051).
D-051 「표시=필터」에 맞춰 연식 범위 필터는 보강한 값에 건다.
"""

from __future__ import annotations

import pandas as pd

LEDGER_AGE_FLAG = "building_age_from_ledger"
APPROVE_YEAR_MIN = 1900
APPROVE_YEAR_MAX = 2100


def backfill_age_from_ledger(df: pd.DataFrame) -> pd.DataFrame:
    """building_age 결측 행만 대장 사용승인연도로 채우고 보강 여부 열을 붙인다."""
    if not isinstance(df, pd.DataFrame) or df.empty or "approve_year" not in df.columns:
        return df
    out = df.copy()
    age = pd.to_numeric(out.get("building_age"), errors="coerce")
    approve = pd.to_numeric(out["approve_year"], errors="coerce")
    contract = pd.to_numeric(out.get("contract_year"), errors="coerce")
    fill = (
        age.isna()
        & approve.between(APPROVE_YEAR_MIN, APPROVE_YEAR_MAX)
        & contract.notna()
    )
    out["building_age"] = age.where(~fill, (contract - approve).clip(lower=0))
    out[LEDGER_AGE_FLAG] = fill
    return out


def apply_age_range(df: pd.DataFrame, lo: float | None, hi: float | None) -> pd.DataFrame:
    """SQL 대신 보강 후 연식에 범위 필터를 건다 (결측은 범위 밖과 같이 제외 — SQL과 동일)."""
    if df.empty or (lo is None and hi is None) or "building_age" not in df.columns:
        return df
    age = pd.to_numeric(df["building_age"], errors="coerce")
    keep = age.notna()
    if lo is not None:
        keep &= age >= float(lo)
    if hi is not None:
        keep &= age <= float(hi)
    return df.loc[keep]


def ledger_backfill_count(df: pd.DataFrame, index) -> int:
    if LEDGER_AGE_FLAG not in getattr(df, "columns", ()):
        return 0
    return int(df.loc[df.index.intersection(index), LEDGER_AGE_FLAG].fillna(False).astype(bool).sum())
