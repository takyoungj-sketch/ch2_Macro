"""비주거 집합 회귀는 이 붙이기를 호출하지 않는다.

대표필지 공시지가 행이 없어 화면 옵션을 뺐다. 함수는 키·자산유형이
같을 때의 조회 방식만 남겨 둔다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.danji_attributes import LAND_PRICE_TABLE


def attach_commercial_assessed_land_price(db: Session, df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty or "building_key" not in out.columns or "asset_type" not in out.columns:
        out["assessed_land_price"] = np.nan
        return out

    exists = db.execute(
        text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{LAND_PRICE_TABLE}"},
    ).scalar()
    keys = out["building_key"].dropna().astype(str).str.strip().unique().tolist()
    keys = [k for k in keys if k]
    if not exists or not keys:
        out["assessed_land_price"] = np.nan
        return out

    rows = db.execute(
        text(
            f"""
            SELECT building_key, asset_type, assessed_land_price
            FROM {LAND_PRICE_TABLE}
            WHERE building_key = ANY(:keys)
            """
        ),
        {"keys": keys},
    ).mappings().all()
    if not rows:
        out["assessed_land_price"] = np.nan
        return out

    price = pd.DataFrame(rows)
    price["building_key"] = price["building_key"].astype(str).str.strip()
    price["asset_type"] = price["asset_type"].astype(str)
    out["building_key"] = out["building_key"].astype(str).str.strip()
    out["asset_type"] = out["asset_type"].astype(str)
    if "assessed_land_price" in out.columns:
        out = out.drop(columns=["assessed_land_price"])
    return out.merge(
        price[["building_key", "asset_type", "assessed_land_price"]],
        on=["building_key", "asset_type"],
        how="left",
    )
