"""임대 화면은 개별공시지가를 보여 주지 않는다. 회귀도 집합 마트를 읽지 않는다."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.danji_attributes import LAND_PRICE_TABLE
from app.collective.db import get_collective_engine
from app.collective.schemas import CollectiveRegressionRequest

LINKED_ASSETS = frozenset({"apartment", "rowhouse", "officetel"})

NOT_APPLICABLE_NOTE = (
    "단독·다가구는 지번이 가려져 있고 연면적이 없어 필지를 연결하지 않습니다. "
    "공시지가를 만들지 않습니다."
)
MISSING_NOTE = "집합 대표필지 공시지가가 없습니다. 금액을 만들지 않습니다."
LINKED_NOTE = (
    "이 단지의 최신 대표필지 개별공시지가(원/㎡)입니다. 거래마다의 과거 금액이 아닙니다."
)
DETACHED_REGRESSION_NOTE = "단독·다가구는 개별공시지가를 쓰지 않습니다."


def describe_rent_land_price(
    asset_type: str | None,
    price: float | None,
    year: int | None,
) -> dict[str, Any]:
    if asset_type not in LINKED_ASSETS:
        return {
            "status": "not_applicable",
            "assessed_land_price": None,
            "assessed_land_price_year": None,
            "note": NOT_APPLICABLE_NOTE,
        }
    if price is None or price <= 0:
        return {
            "status": "missing",
            "assessed_land_price": None,
            "assessed_land_price_year": None,
            "note": MISSING_NOTE,
        }
    return {
        "status": "linked",
        "assessed_land_price": float(price),
        "assessed_land_price_year": int(year) if year is not None else None,
        "note": LINKED_NOTE,
    }


def lookup_assessed_land_prices(
    asset_type: str | None,
    building_keys: list[str],
    db: Session | None = None,
) -> dict[str, tuple[float, int | None]]:
    """집합 마트의 최신 대표필지 금액. 키별 하나. 없으면 그 키는 결과에 없다."""
    if asset_type not in LINKED_ASSETS:
        return {}
    keys = sorted({str(key).strip() for key in building_keys if str(key).strip()})
    if not keys:
        return {}
    engine = None if db is not None else get_collective_engine()
    if db is None and engine is None:
        return {}
    statement = text(
        f"""
        SELECT btrim(building_key::text) AS building_key,
               assessed_land_price,
               assessed_land_price_year
        FROM {LAND_PRICE_TABLE}
        WHERE asset_type = :asset_type
          AND btrim(building_key::text) = ANY(:keys)
          AND assessed_land_price > 0
        """
    )
    params = {"asset_type": asset_type, "keys": keys}
    if db is not None:
        rows = db.execute(statement, params).mappings().all()
    else:
        assert engine is not None
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            rows = conn.execute(statement, params).mappings().all()
    out: dict[str, tuple[float, int | None]] = {}
    for row in rows:
        key = str(row["building_key"]).strip()
        year = row["assessed_land_price_year"]
        out[key] = (float(row["assessed_land_price"]), int(year) if year is not None else None)
    return out


def attach_assessed_land_price(
    df: pd.DataFrame,
    asset_type: str | None,
    prices: dict[str, tuple[float, int | None]],
) -> pd.DataFrame:
    out = df.copy()
    if asset_type not in LINKED_ASSETS or "building_key" not in out.columns:
        return out
    out["assessed_land_price"] = out["building_key"].map(
        lambda key: prices.get(str(key).strip(), (None, None))[0]
    )
    return out


def prepare_rent_regression(
    df: pd.DataFrame,
    body: CollectiveRegressionRequest,
    asset_type: str | None,
    prices: dict[str, tuple[float, int | None]] | None = None,
) -> tuple[pd.DataFrame, CollectiveRegressionRequest, list[str]]:
    """임대 회귀는 개별공시지가를 쓰지 않는다. 집합 마트를 조회하지 않는다."""
    del asset_type, prices
    cleared = body.model_copy(
        update={"variables": body.variables.model_copy(update={"assessed_land_price": False})}
    )
    return df, cleared, []
