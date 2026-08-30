"""코호트 통합회귀용 단지 속성(세대수·주차·공시지가·구조) 부착.

단지마다 상수인 값이다. 단지 FE와 같이 넣으면 완전공선이므로, 엔진에서
속성이 설계행렬에 들어가면 FE를 생략한다. match_rule=kapt_same_pnu 는
세대수·주차가 단지 전체 재고라 이 유형 값이 아니므로 결측 처리한다.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.danji_attributes import ATTRIBUTES_TABLE, LAND_PRICE_TABLE
from app.collective.schemas import CollectiveRegressionSpec

KAPT_SAME_PNU = "kapt_same_pnu"


def spec_wants_building_attrs(v: CollectiveRegressionSpec) -> bool:
    return bool(
        v.households
        or v.parking
        or v.assessed_land_price
        or v.structure
        or v.asset_type_dummy
    )


def _flags(raw: Any) -> set[str]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return set()
    return {p.strip() for p in str(raw).split(",") if p.strip()}


def apply_building_attr_quality(df: pd.DataFrame) -> pd.DataFrame:
    """품질 플래그·kapt_same_pnu 규칙을 세대수·주차에 적용한다."""
    out = df.copy()
    if out.empty:
        return out
    for col in ("households", "parking_per_household", "assessed_land_price"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "attr_quality_flags" in out.columns:
        flags = out["attr_quality_flags"].map(_flags)
        if "households" in out.columns:
            out.loc[flags.map(lambda s: "hh_zero" in s or "scale_inconsistent" in s), "households"] = np.nan
        if "parking_per_household" in out.columns:
            out.loc[flags.map(lambda s: "parking_implausible" in s), "parking_per_household"] = np.nan
    if "households" in out.columns:
        out.loc[out["households"] <= 0, "households"] = np.nan
    if "parking_per_household" in out.columns:
        out.loc[out["parking_per_household"] < 0, "parking_per_household"] = np.nan
    if "match_rule" in out.columns:
        copied = out["match_rule"].astype(str) == KAPT_SAME_PNU
        if "households" in out.columns:
            out.loc[copied, "households"] = np.nan
        if "parking_per_household" in out.columns:
            out.loc[copied, "parking_per_household"] = np.nan
    return out


def attach_cohort_building_attrs(db: Session, df: pd.DataFrame) -> pd.DataFrame:
    """거래 행에 최신 스냅샷 단지 속성·개별공시지가를 붙인다."""
    if df.empty or "building_key" not in df.columns:
        return df
    keys = df["building_key"].dropna().astype(str).unique().tolist()
    if not keys:
        return df
    snap = db.execute(text(f"SELECT MAX(snapshot_ym) FROM {ATTRIBUTES_TABLE}")).scalar()
    if not snap:
        return df

    land_exists = db.execute(
        text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{LAND_PRICE_TABLE}"},
    ).scalar()
    if land_exists:
        land_select = "lp.assessed_land_price"
        land_join = f"""
            LEFT JOIN {LAND_PRICE_TABLE} lp
              ON lp.building_key = a.building_key
             AND lp.asset_type = a.asset_type
        """
    else:
        land_select = "NULL::numeric AS assessed_land_price"
        land_join = ""

    rows = db.execute(
        text(
            f"""
            SELECT a.building_key, a.asset_type, a.match_rule,
                   a.households, a.parking_per_household, a.structure_group,
                   a.attr_quality_flags, {land_select}
            FROM {ATTRIBUTES_TABLE} a
            {land_join}
            WHERE a.snapshot_ym = :snap
              AND a.building_key = ANY(:keys)
            """
        ),
        {"snap": str(snap).strip(), "keys": keys},
    ).mappings().all()
    if not rows:
        return df

    attr = apply_building_attr_quality(pd.DataFrame(rows))
    merge_on = ["building_key"]
    if "asset_type" in df.columns and "asset_type" in attr.columns:
        merge_on.append("asset_type")
    drop_cols = [
        c
        for c in (
            "households",
            "parking_per_household",
            "structure_group",
            "assessed_land_price",
            "match_rule",
            "attr_quality_flags",
        )
        if c in df.columns
    ]
    left = df.drop(columns=drop_cols)
    return left.merge(attr, on=merge_on, how="left")
