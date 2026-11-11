"""P-01 4-4 — 직거래 ≥20건 아파트 단지에서 직거래를 n건으로 줄여 직거래 더미 반복 추정.

설계: 상수 + log면적 + 층 그룹 + 동(미상 범주) + 반기 + 거래유형(기준 중개, 직거래·미상 더미). 연식은 단일 단지라 제외.
단지 표본 20곳(seed 고정), n ∈ {3,5,10,15,20}, 반복 200회. 5년 창은 거래유형 미상이 없어 미상 더미는 대개 생기지 않음.
출력: logs/collective_phase0/p01b_result.md
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from _db import OUT, engine, md_table, q
from _reg import design, load_tx

NS = (3, 5, 10, 15, 20)
REPS = 200


def ols(X, y):
    coef, *_ = np.linalg.lstsq(X.to_numpy(float), y.to_numpy(float), rcond=None)
    return pd.Series(coef, index=X.columns)


def main():
    rng = np.random.default_rng(20261111)
    with engine("collective").connect() as c:
        pool = [r[0] for r in q(c, """select building_key from collective_transactions
                                     where is_valid and asset_type='apartment' and unit_price>0
                                       and contract_date >= '2021-11-01' and contract_date < '2026-11-01'
                                     group by 1 having count(*) filter (where deal_type='직거래') >= 20
                                        and count(*) filter (where deal_type='중개거래') >= 60""")]
        keys = list(rng.choice(pool, size=min(20, len(pool)), replace=False))
        tx = load_tx(c, keys)
    rows = []
    for key, df in tx.groupby("building_key"):
        df = df.dropna(subset=["floor"]).reset_index(drop=True)
        X, y, _ = design(df, age=False, deal=True)
        full = ols(X, y)
        b_full = full.get("deal_direct", np.nan)
        fl_cols = [c for c in X.columns if c.startswith("fl_")]
        direct_idx = np.flatnonzero(df.deal_type.eq("직거래").to_numpy())
        other_idx = np.flatnonzero(~df.deal_type.eq("직거래").to_numpy())
        for n in NS:
            if n > len(direct_idx):
                continue
            est, area, flo = [], [], []
            for _ in range(REPS):
                keep = np.concatenate([other_idx, rng.choice(direct_idx, size=n, replace=False)])
                sub = df.iloc[keep]
                Xs, ys, _ = design(sub, age=False, deal=True)
                cf = ols(Xs, ys)
                est.append(cf.get("deal_direct", np.nan))
                area.append(cf.get("log_area", np.nan) - full.get("log_area", np.nan))
                flo.append(np.nanmean([abs(cf.get(c, np.nan) - full.get(c, np.nan)) for c in fl_cols]) if fl_cols else np.nan)
            est = np.array(est, float)
            rows.append(dict(key=key, n=n, n_direct_all=len(direct_idx), b_full=b_full,
                             width=float(np.nanpercentile(est, 95) - np.nanpercentile(est, 5)),
                             iqr=float(np.nanpercentile(est, 75) - np.nanpercentile(est, 25)),
                             flip=float(np.mean(np.sign(est) != np.sign(b_full))),
                             area_d=float(np.nanmean(np.abs(area))), floor_d=float(np.nanmean(flo))))
    rd = pd.DataFrame(rows)
    rd.to_csv(OUT / "p01b_detail.csv", index=False, encoding="utf-8-sig")
    g = rd.groupby("n").agg(단지=("key", "count"), 계수폭_p5_p95=("width", "median"), IQR=("iqr", "median"),
                           부호뒤집힘=("flip", "median"), 부호뒤집힘_최대=("flip", "max"),
                           면적계수_평균절대변화=("area_d", "median"), 층계수_평균절대변화=("floor_d", "median")).reset_index().round(4)
    md = [f"## P-01 4-4 직거래 더미 축소 반복 (단지 {rd.key.nunique()}곳, 반복 {REPS}회, 값은 단지 중앙값)",
          md_table(g.values.tolist(), list(g.columns)),
          f"전체 표본 직거래 계수(로그) 단지 분포: p10 {rd.drop_duplicates('key').b_full.quantile(.1):.3f} · p50 {rd.drop_duplicates('key').b_full.median():.3f} · p90 {rd.drop_duplicates('key').b_full.quantile(.9):.3f}"]
    (OUT / "p01b_result.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
