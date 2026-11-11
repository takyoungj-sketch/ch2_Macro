"""P-03 — 쌍둥이 확장 지역 더미 식별성 (읽기 전용).

제품 쌍둥이 목록(apt_twin_lab.rank_display_twins, 전국 후보)과 같은 프로필·적격 단지를 쓴다.
모형: 단지 단위 y=log(3년 창 중앙 단가), X=CORE 5변수 + 쌍둥이 지역 더미(기준=기준 지역).
기준 읍면동 50곳: 적격 단지 ≥3인 읍면동에서 시도 층화 무작위(seed 고정).
출력: logs/collective_phase0/p03_result.md
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from _db import OUT, engine, md_table, q
from app.collective.regional_regression.apt_twin_lab import CORE, _prepare_national, rank_display_twins


def main():
    rng = np.random.default_rng(20261111)
    with engine("collective").connect() as c:
        frame, meta, eligible, profiles = _prepare_national(c)
        five = pd.DataFrame(q(c, """select left(btrim(beopjungri_code),8) r, count(*) k, sum(count) n from collective_building_stats
                                   where as_of_month=(select max(as_of_month) from collective_building_stats) and window_years=5
                                     and asset_type='apartment' and beopjungri_code is not null group by 1"""), columns=["r", "k5", "n5"]).set_index("r")
    elig_by = eligible.groupby("region_id").size()
    all_by = frame.groupby("region_id").size()
    cand = profiles[profiles.n_complexes >= 3].copy()
    share = cand.addr1.value_counts(normalize=True)
    take = (share * 50).round().astype(int).clip(lower=1)
    anchors = []
    for a1, k in take.items():
        sub = cand[cand.addr1 == a1]
        anchors += list(sub.index[rng.choice(len(sub), size=min(k, len(sub)), replace=False)])
    anchors = anchors[:50]
    rows, regs = [], []
    for aid in anchors:
        twins = rank_display_twins(profiles, aid)
        a_rows = eligible[eligible.region_id == aid]
        parts = [a_rows.assign(_rg="anchor")]
        for rank, tid in enumerate(twins, start=1):
            t_rows = eligible[eligible.region_id == tid]
            parts.append(t_rows.assign(_rg=f"t{rank}"))
            regs.append(dict(anchor=aid, rank=rank, twin=tid, k_all=int(all_by.get(tid, 0)), k_elig=int(elig_by.get(tid, 0)),
                             k5=int(five.k5.get(tid, 0)) if tid in five.index else 0, n5=int(five.n5.get(tid, 0)) if tid in five.index else 0,
                             n3=int(t_rows.n_tx.sum())))
        df = pd.concat(parts, ignore_index=True)
        y = np.log(df["median"].to_numpy(float))
        X = [np.ones(len(df)), *[df[c].to_numpy(float) for c in CORE]]
        names = ["const", *CORE]
        for rank in range(1, len(twins) + 1):
            X.append((df._rg == f"t{rank}").to_numpy(float))
            names.append(f"t{rank}")
        A = np.column_stack(X)
        rank_ = int(np.linalg.matrix_rank(A / np.maximum(np.linalg.norm(A, axis=0), 1e-12)))
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        resid = y - A @ beta
        zero = []
        for r in range(1, len(twins) + 1):
            m = (df._rg == f"t{r}").to_numpy()
            zero.append(bool(m.any() and np.all(np.abs(resid[m]) < 1e-6)))
        rows.append(dict(anchor=aid, a1=profiles.loc[aid, "addr1"], k_anchor=len(a_rows), n_twins=len(twins), p=A.shape[1], rank=rank_,
                         n=len(df), zero_resid=sum(zero)))
    rd, rg = pd.DataFrame(rows), pd.DataFrame(regs)
    rg.to_csv(OUT / "p03_twins.csv", index=False, encoding="utf-8-sig")
    md = ["## P-03", f"기준 읍면동 {len(rd)}곳 · 쌍둥이 {len(rg)}개 (스냅샷 {meta.get('as_of_label')})"]
    g = rg.groupby("rank").agg(쌍둥이=("twin", "count"), 단지_전체_중앙=("k_all", "median"), 적격단지_중앙=("k_elig", "median"),
                               적격단지_최소=("k_elig", "min"), 단지5y_중앙=("k5", "median"), 거래5y_중앙=("n5", "median"),
                               거래3y_적격_중앙=("n3", "median")).reset_index()
    md += ["### 7-1 쌍둥이 순위별 규모", md_table(g.values.tolist(), list(g.columns))]
    md += ["### 7-2 지역 더미 투입 시",
           md_table([
               ("설계행렬 rank 부족 기준지역", f"{int((rd['rank'] < rd.p).sum())}/{len(rd)}"),
               ("기준 지역 적격 단지 ≤2", f"{int((rd.k_anchor <= 2).sum())}/{len(rd)}"),
               ("쌍둥이 적격 단지 ≤2 비율", f"{100 * (rg.k_elig <= 2).mean():.1f}%"),
               ("잔차가 전부 0인 쌍둥이 지역", f"{int(rd.zero_resid.sum())}/{len(rg)}"),
               ("쌍둥이 5개 미만 기준지역", f"{int((rd.n_twins < 5).sum())}/{len(rd)}"),
           ], ["지표", "값"])]
    rules = {
        "R1 적격 단지 ≥10": rg.k_elig >= 10,
        "R2 적격 단지 ≥10 · 3년 거래 ≥100": (rg.k_elig >= 10) & (rg.n3 >= 100),
        "R3 적격 단지 ≥20 · 5년 거래 ≥300 (제품 후보 풀 기준 유지 + 거래)": (rg.k_elig >= 20) & (rg.n5 >= 300),
    }
    md += ["### 7-3 자동 제외 조건 후보 (확정 아님)",
           md_table([(k, f"{100 * (~v).mean():.1f}%", int((~v).sum())) for k, v in rules.items()], ["조건", "제외되는 쌍둥이 비율", "개수"])]
    (OUT / "p03_result.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
