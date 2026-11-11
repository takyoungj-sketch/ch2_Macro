"""C-04 3-4 — 동 결측률 구간별 표본 30단지: ① 현재(동 미상 범주) vs ② 동 결측 거래 제외.

동 효용지수 = exp(동 계수) (기준 동 대비). 시점 계수 = 반기 더미.
표본: 5년 창 아파트, 거래 ≥60·실제 동 ≥3, 결측률 구간(≤10, 10~20, 20~30, 30~50, >50%) 각 6곳, seed 고정.
출력: logs/collective_phase0/c04b_result.md
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from _db import OUT, engine, md_table, q
from _reg import design, fit, load_tx

BINS = [(-0.01, 0.10, "≤10%"), (0.10, 0.20, "10~20%"), (0.20, 0.30, "20~30%"), (0.30, 0.50, "30~50%"), (0.50, 0.95, "50~95%")]


def main():
    rng = np.random.default_rng(20261111)
    with engine("collective").connect() as c:
        pool = pd.DataFrame(q(c, """select building_key, count(*) n, count(*) filter (where coalesce(btrim(dong),'')='')::float/count(*) miss,
                                          count(distinct nullif(btrim(dong),'')) nd
                                   from collective_transactions where is_valid and asset_type='apartment' and unit_price>0
                                     and contract_date >= '2021-11-01' and contract_date < '2026-11-01'
                                   group by 1 having count(*) >= 60"""), columns=["key", "n", "miss", "nd"])
        pool = pool[pool.nd >= 3]
        keys = []
        for lo, hi, lab in BINS:
            sub = pool[(pool.miss > lo) & (pool.miss <= hi)]
            pick = sub.iloc[rng.choice(len(sub), size=min(6, len(sub)), replace=False)]
            keys += [(k, lab) for k in pick.key]
        tx = load_tx(c, [k for k, _ in keys])
    lab_of = dict(keys)
    rows = []
    for key, df in tx.groupby("building_key"):
        df = df.dropna(subset=["floor"])
        miss = (df.dong.fillna("").str.strip() == "")
        X1, y1, _ = design(df, age=False)
        f1 = fit(X1, y1)
        X2, y2, _ = design(df[~miss], age=False)
        f2 = fit(X2, y2)
        d1 = f1["coef"].filter(like="dong_")
        d2 = f2["coef"].filter(like="dong_")
        common = [c for c in d1.index if c in d2.index and not c.endswith("미상")]
        t1 = f1["coef"].filter(like="time_")
        t2 = f2["coef"].filter(like="time_")
        tc = [c for c in t1.index if c in t2.index]
        idx_d = (np.exp(d2[common]) - np.exp(d1[common])).abs() if common else pd.Series(dtype=float)
        recent = [c for c in tc if c >= "time_2026"]
        rows.append(dict(
            bin=lab_of[key], n=len(df), miss=float(miss.mean()), n_dong=len(common),
            dong_idx_mad=float(idx_d.mean()) if len(idx_d) else np.nan, dong_idx_max=float(idx_d.max()) if len(idx_d) else np.nan,
            time_mad=float((t2[tc] - t1[tc]).abs().mean()) if tc else np.nan,
            time_recent_mad=float((t2[recent] - t1[recent]).abs().mean()) if recent else np.nan,
            time_lost=len(t1) - len(tc), full1=f1["rank"] >= f1["p"], full2=f2["rank"] >= f2["p"],
            unk_coef=float(f1["coef"].filter(like="미상").iloc[0]) if len(f1["coef"].filter(like="미상")) else np.nan,
        ))
    rd = pd.DataFrame(rows)
    rd.to_csv(OUT / "c04b_detail.csv", index=False, encoding="utf-8-sig")
    order = [b[2] for b in BINS]
    g = rd.groupby("bin").agg(단지=("n", "count"), 거래중앙=("n", "median"), 결측률=("miss", "median"),
                             동지수_평균절대차=("dong_idx_mad", "median"), 동지수_최대차=("dong_idx_max", "median"),
                             시점계수_평균절대차=("time_mad", "median"), 최근반기_평균절대차=("time_recent_mad", "median"),
                             사라진_반기=("time_lost", "sum"), 미상계수=("unk_coef", "median"),
                             식별가능_현재=("full1", "sum"), 식별가능_결측제외=("full2", "sum")).reindex(order).reset_index()
    g = g.round(4)
    md = ["## C-04 3-4 동 결측 민감도 (표본 30단지, 연식 제외·기본 변수, 값은 구간 내 중앙값)",
          md_table(g.values.tolist(), list(g.columns))]
    (OUT / "c04b_result.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
