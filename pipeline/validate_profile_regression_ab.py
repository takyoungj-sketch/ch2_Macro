#!/usr/bin/env python3
"""
Built 지역결합 회귀 A/B — Profile feature on/off 비교 (Phase D 스모크).

예:
  cd pipeline
  python validate_profile_regression_ab.py --region-code 4311210100 --asset-type apartment
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import create_engine, text

REPO = Path(__file__).resolve().parents[1]
SNAP = REPO / "pipeline" / "clean_snapshots" / "collective_phase_d"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _engine(url: str):
    return create_engine(url, pool_pre_ping=True)


def _load_profile(conn, code: str, as_of: str | None) -> dict:
    q = """
        SELECT features FROM regional_profile
        WHERE region_code = :code
        ORDER BY as_of_month DESC LIMIT 1
    """
    params = {"code": code}
    if as_of:
        q = """
            SELECT features FROM regional_profile
            WHERE region_code = :code AND as_of_month = :as_of
            LIMIT 1
        """
        params["as_of"] = as_of
    row = conn.execute(text(q), params).mappings().first()
    if not row:
        return {}
    feats = row["features"]
    return dict(feats) if isinstance(feats, dict) else {}


def _load_built_tx(conn, code: str, asset_type: str) -> pd.DataFrame:
    rows = conn.execute(
        text(
            """
            SELECT price, unit_price, exclusive_area, building_age, contract_year
            FROM built_transactions
            WHERE is_valid = true
              AND asset_type = :at
              AND beopjungri_code LIKE :pfx
            """
        ),
        {"at": asset_type, "pfx": f"{code[:8]}%"},
    ).mappings().all()
    return pd.DataFrame(rows)


def _run_ols(df: pd.DataFrame, extra: pd.DataFrame | None) -> dict:
    if df.empty or len(df) < 20:
        return {"n": len(df), "error": "insufficient n"}
    y = df["price"].astype(float)
    parts = [df[["exclusive_area", "building_age"]].astype(float)]
    if extra is not None and not extra.empty:
        parts.append(extra)
    X = sm.add_constant(pd.concat(parts, axis=1), has_constant="add")
    model = sm.OLS(y, X, missing="drop").fit()
    pred = model.predict(X)
    mape = float(np.mean(np.abs((y - pred) / y.replace(0, np.nan)).dropna()) * 100)
    return {
        "n": int(model.nobs),
        "r_squared": float(model.rsquared),
        "adj_r_squared": float(model.rsquared_adj),
        "mape_pct": round(mape, 2),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--collective-url", default="postgresql+psycopg2://postgres:8972@localhost:5432/collective_stats")
    p.add_argument("--built-url", default="postgresql+psycopg2://postgres:8972@localhost:5432/collective_stats")
    p.add_argument("--region-code", required=True, help="eupmyeondong 8자리")
    p.add_argument("--asset-type", default="apartment")
    args = p.parse_args()

    coll = _engine(args.collective_url)
    built = _engine(args.built_url)

    with coll.connect() as c:
        profile = _load_profile(c, args.region_code, None)
    with built.connect() as c:
        df = _load_built_tx(c, args.region_code, args.asset_type)

    profile_cols = {
        k: v
        for k, v in profile.items()
        if k.startswith(("apartment_", "land_", "population"))
        and isinstance(v, (int, float))
    }
    extra = pd.DataFrame([profile_cols] * len(df)).reset_index(drop=True) if profile_cols and len(df) else None

    baseline = _run_ols(df, None)
    with_profile = _run_ols(df, extra)

    report = {
        "region_code": args.region_code,
        "asset_type": args.asset_type,
        "profile_features_used": list(profile_cols.keys()),
        "baseline": baseline,
        "with_profile": with_profile,
        "generated_at": datetime.now().isoformat(),
    }
    SNAP.mkdir(parents=True, exist_ok=True)
    out = SNAP / f"ab_{args.region_code}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("report: %s", out)
    log.info("baseline adj_r2=%s mape=%s", baseline.get("adj_r_squared"), baseline.get("mape_pct"))
    log.info("profile  adj_r2=%s mape=%s", with_profile.get("adj_r_squared"), with_profile.get("mape_pct"))


if __name__ == "__main__":
    main()
