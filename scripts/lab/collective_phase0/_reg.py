"""조사용 단지 회귀 — 제품 helper(반기 더미·동 미상 범주·층 그룹)를 그대로 써서 설계행렬을 만든다.

제품 경로(run_building_regression)를 호출하지 않고, 같은 규칙의 최소 설계만 재현한다.
y = log(unit_price). 기본 변수: log 전용면적, 연식, 층 그룹, 동, 거래시점(반기).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from _db import q  # noqa: F401  (경로 설정)
from app.built.regression.engine import nonidentifiable_columns
from app.collective.regression.engine import (
    _add_contract_period_columns,
    _explicit_category_dummies,
    _floor_group_label,
)

W5_FROM, W5_TO = "2021-11-01", "2026-11-01"

TX_SQL = """
select building_key, asset_type, addr1, addr2, addr3, addr4, unit_price, exclusive_area, floor, dong,
       contract_year, contract_month, contract_date, building_age, building_year, deal_type
from collective_transactions
where is_valid and unit_price > 0 and exclusive_area > 0
  and contract_date >= :d0 and contract_date < :d1 and building_key = any(:keys)
"""


def load_tx(conn, keys, d0=W5_FROM, d1=W5_TO) -> pd.DataFrame:
    rows = q(conn, TX_SQL, keys=list(keys), d0=d0, d1=d1)
    cols = ["building_key", "asset_type", "addr1", "addr2", "addr3", "addr4", "unit_price", "exclusive_area", "floor", "dong",
            "contract_year", "contract_month", "contract_date", "building_age", "building_year", "deal_type"]
    df = pd.DataFrame(rows, columns=cols)
    for c in ("unit_price", "exclusive_area", "floor", "building_age"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df


def _most_freq_dummies(s: pd.Series, prefix: str):
    s = s.astype(str)
    vc = s.value_counts()
    if len(vc) < 2:
        return pd.DataFrame(index=s.index)
    ref = vc.idxmax()
    return pd.DataFrame({f"{prefix}_{v}": (s == v).astype(float) for v in vc.index if v != ref}, index=s.index)


def design(df: pd.DataFrame, *, area=True, age=True, floor=True, dong=True, period=True, deal=False, region_col=None,
           building_fe=False):
    """X(상수 포함), y, 열 그룹 dict."""
    work = df.reset_index(drop=True)
    y = np.log(work["unit_price"].astype(float))
    parts, groups = [], {}

    def add(frame: pd.DataFrame, g: str):
        if frame is None or frame.empty:
            return
        parts.append(frame)
        groups[g] = list(frame.columns)

    if area:
        add(pd.DataFrame({"log_area": np.log(work["exclusive_area"])}), "area")
    if age and work["building_age"].notna().all():
        add(pd.DataFrame({"age": work["building_age"]}), "age")
    if floor:
        add(_most_freq_dummies(work["floor"].fillna(0).map(_floor_group_label), "fl"), "floor")
    if dong and "dong" in work:
        fr, _levels, _ref = _explicit_category_dummies(work["dong"], "dong")
        add(fr, "dong")
    if period:
        fr, _labels, _ref = _add_contract_period_columns(work)
        add(fr, "period")
    if deal:
        dt = work["deal_type"].map({"중개거래": "broker", "직거래": "direct"}).fillna("unknown")
        fr = pd.DataFrame({f"deal_{v}": (dt == v).astype(float) for v in ("direct", "unknown") if (dt == v).any()}, index=work.index)
        add(fr, "deal")
    if region_col:
        add(_most_freq_dummies(work[region_col], "rg"), "region")
    if building_fe:
        add(_most_freq_dummies(work["building_key"].str[:10], "bk"), "building")
    X = pd.concat([pd.DataFrame({"const": np.ones(len(work))})] + parts, axis=1)
    return X, y, groups


def fit(X: pd.DataFrame, y: pd.Series):
    A = X.to_numpy(float)
    b = y.to_numpy(float)
    coef, *_ = np.linalg.lstsq(A, b, rcond=None)
    pred = A @ coef
    resid = b - pred
    ss_tot = float(((b - b.mean()) ** 2).sum())
    r2 = 1 - float((resid**2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    rank = int(np.linalg.matrix_rank(A / np.maximum(np.linalg.norm(A, axis=0), 1e-12)))
    return dict(coef=pd.Series(coef, index=X.columns), r2=r2, rank=rank, p=A.shape[1], n=A.shape[0], resid=resid)


def cv_mape(X: pd.DataFrame, y: pd.Series, k=5, seed=0):
    n = len(y)
    if n < 2 * k:
        return float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    A, b = X.to_numpy(float), y.to_numpy(float)
    errs = []
    for f in range(k):
        te = idx[f::k]
        tr = np.setdiff1d(idx, te)
        coef, *_ = np.linalg.lstsq(A[tr], b[tr], rcond=None)
        smear = float(np.mean(np.exp(b[tr] - A[tr] @ coef)))
        p = np.exp(A[te] @ coef) * smear
        errs.append(np.abs(p - np.exp(b[te])) / np.exp(b[te]))
    return float(np.mean(np.concatenate(errs)) * 100)


def nonident(X: pd.DataFrame) -> list[str]:
    return nonidentifiable_columns(X.to_numpy(float), list(X.columns))
