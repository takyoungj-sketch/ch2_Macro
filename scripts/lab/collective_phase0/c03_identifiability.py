"""C-03 — 단지 회귀 식별 불가 빈도 (읽기 전용).

대상: 5년 창 아파트 단지 중 거래 ≥30건, 시도 층화 무작위 200곳(seed 20261111).
기본 설계: 상수 + log 면적 + 연식 + 층 그룹 + 동(미상 범주) + 거래시점(반기).
제외 우선순위안(단일 단지): ① 연식 → ② 동 '미상' 열 → ③ 동 전체 → ④ 층 그룹 → ⑤ 남은 식별 불가 열.
코호트(같은 읍면동 아파트 최대 5곳, 단지 고정효과 없음): 준공연도가 2개 이상이면 연식 유지 시 rank 확인.
출력: logs/collective_phase0/c03_result.md
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from _db import OUT, engine, md_table, q
from _reg import cv_mape, design, fit, load_tx, nonident

SEED = 20261111


def sample(conn, n=200):
    rows = q(conn, """select building_key, addr1, addr2, addr3, addr4, count(*) n from collective_transactions
                      where is_valid and asset_type='apartment' and unit_price>0 and contract_date >= '2021-11-01' and contract_date < '2026-11-01'
                      group by 1,2,3,4,5 having count(*) >= 30""")
    df = pd.DataFrame(rows, columns=["key", "a1", "a2", "a3", "a4", "n"]).drop_duplicates("key")
    rng = np.random.default_rng(SEED)
    share = df.a1.value_counts(normalize=True)
    take = (share * n).round().astype(int).clip(lower=5)
    picks = []
    for a1, k in take.items():
        sub = df[df.a1 == a1]
        picks.append(sub.iloc[rng.choice(len(sub), size=min(k, len(sub)), replace=False)])
    out = pd.concat(picks)
    if len(out) > n:
        out = out.iloc[rng.choice(len(out), size=n, replace=False)]
    return out, df


PRIORITY = ("age", "dong_미상", "dong_", "fl_", "time_", "log_area")


def _group_of(col: str) -> str:
    for pre in PRIORITY:
        if col == pre or col.startswith(pre):
            return pre
    return "기타"


def cause_of(df):
    X, y, g = design(df)
    full = fit(X, y)
    if full["rank"] >= full["p"]:
        return "식별 가능", X, y, g, full, ""
    groups = sorted({_group_of(c) for c in nonident(X) if c != "const"})
    if df.exclusive_area.round(2).nunique() == 1 and "log_area" in groups:
        return "면적 단일", X, y, g, full, "+".join(groups)
    for label, kw in (("연식↔시점", dict(age=False)), ("동↔시점", dict(dong=False)), ("층 범주", dict(floor=False))):
        X2, y2, _ = design(df, **kw)
        f2 = fit(X2, y2)
        if f2["rank"] >= f2["p"]:
            return label, X, y, g, full, "+".join(groups)
    return "기타(복합)", X, y, g, full, "+".join(groups)


def apply_priority(df, X, y, g):
    """식별 불가 열만 하나씩 뺀다. 순서: 연식 → 동 미상 → 동 → 층 → 거래시점 → 면적."""
    dropped = []
    cur = X.copy()
    while True:
        f = fit(cur, y)
        if f["rank"] >= f["p"]:
            break
        bad = [c for c in nonident(cur) if c != "const"]
        if not bad:
            break
        bad.sort(key=lambda c: (PRIORITY.index(_group_of(c)) if _group_of(c) in PRIORITY else 99, c))
        cur = cur.drop(columns=[bad[0]])
        lab = {"age": "연식", "dong_미상": "동 미상", "dong_": "동 수준", "fl_": "층 수준", "time_": "반기", "log_area": "면적"}.get(_group_of(bad[0]), "기타")
        if not dropped or dropped[-1] != lab:
            dropped.append(lab)
    return cur, dropped


def main():
    with engine("collective").connect() as c:
        smp, pool = sample(c)
        tx = load_tx(c, smp.key.tolist())
        res = []
        for key, df in tx.groupby("building_key"):
            df = df.dropna(subset=["building_age", "floor"])
            if len(df) < 30:
                continue
            cause, X, y, g, full, groups = cause_of(df)
            row = dict(key=key, a1=df.addr1.iloc[0], n=len(df), p=full["p"], rank=full["rank"], cause=cause,
                       nonid_groups=groups, dong_missing=float((df.dong.fillna("").str.strip() == "").mean()), r2_0=full["r2"], cv_0=cv_mape(X, y))
            if cause != "식별 가능":
                X2, dropped = apply_priority(df, X, y, g)
                f2 = fit(X2, y)
                row.update(dropped="+".join(dropped), r2_1=f2["r2"], cv_1=cv_mape(X2, y), rank_1=f2["rank"], p_1=f2["p"],
                           area_0=float(full["coef"].get("log_area", np.nan)), area_1=float(f2["coef"].get("log_area", np.nan)),
                           age_0=float(full["coef"].get("age", np.nan)))
            res.append(row)
        rd = pd.DataFrame(res)
        # 코호트 테스트 — 표본 50곳의 같은 읍면동(구 포함) 아파트 최대 5곳
        coh = []
        for r in smp.head(60).itertuples():
            mates = pool[(pool.a1 == r.a1) & (pool.a2 == r.a2) & (pool.a3 == r.a3) & (pool.a4.fillna("") == (r.a4 or ""))]
            keys = mates.sort_values("n", ascending=False).key.head(5).tolist()
            if len(keys) < 2:
                continue
            d = load_tx(c, keys).dropna(subset=["building_age", "floor"])
            nby = d.building_year.nunique()
            X, y, g = design(d, dong=False)
            f = fit(X, y)
            coh.append(dict(n_bld=len(keys), n_by=nby, full=f["rank"] >= f["p"], nonid="+".join(sorted({c.split("_")[0] for c in nonident(X)}))))
        cd = pd.DataFrame(coh)
    rd.to_csv(OUT / "c03_detail.csv", index=False, encoding="utf-8-sig")
    md = ["## C-03", f"표본 {len(rd)}곳 (요청 200, 거래 ≥30·연식/층 결측 제외 후)"]
    vc = rd.cause.value_counts()
    md.append(md_table([(k, int(v), f"{100 * v / len(rd):.1f}%") for k, v in vc.items()], ["판정", "단지", "비율"]))
    md.append("식별 불가 열 그룹 조합: " + ", ".join(f"{k} {v}" for k, v in rd[rd.cause != "식별 가능"].nonid_groups.value_counts().items()))
    bins = pd.cut(rd.dong_missing, [-0.01, 0.1, 0.3, 1.0], labels=["동 결측 ≤10%", "10~30%", ">30%"])
    t = rd.assign(b=bins, bad=rd.cause != "식별 가능").groupby("b", observed=False).agg(n=("key", "count"), bad=("bad", "sum")).reset_index()
    md.append(md_table(t.values.tolist(), ["동 결측률", "단지", "식별 불가"]))
    md.append("### 시도별 식별 불가 비율")
    s = rd.assign(bad=rd.cause != "식별 가능").groupby("a1").agg(n=("key", "count"), bad=("bad", "sum")).reset_index()
    md.append(md_table(s.values.tolist(), ["시도", "단지", "식별 불가"]))
    bad = rd[rd.cause != "식별 가능"]
    if len(bad):
        md.append("### 제외 우선순위 적용 결과")
        dv = bad.dropped.value_counts()
        md.append(md_table([(k, int(v)) for k, v in dv.items()], ["제외 열", "단지"]))
        md.append(md_table([
            ("R² 중앙값", f"{bad.r2_0.median():.3f}", f"{bad.r2_1.median():.3f}"),
            ("CV-MAPE 중앙값(%)", f"{bad.cv_0.median():.2f}", f"{bad.cv_1.median():.2f}"),
            ("log면적 계수 중앙값", f"{bad.area_0.median():.3f}", f"{bad.area_1.median():.3f}"),
            ("log면적 계수 |Δ| 최대", "", f"{(bad.area_1 - bad.area_0).abs().max():.4f}"),
            ("제외 후 식별 가능", "", f"{int((bad.rank_1 >= bad.p_1).sum())}/{len(bad)}"),
        ], ["지표", "제외 전(최소노름 해)", "제외 후"]))
        md.append(f"연식 계수(제외 전 최소노름 해) 분포: p10 {bad.age_0.quantile(.1):.4f} · p50 {bad.age_0.median():.4f} · p90 {bad.age_0.quantile(.9):.4f} — 값 자체가 임의(식별 불가)")
    if len(cd):
        md.append("### 코호트(같은 읍면동 아파트 2~5곳, 단지 고정효과 없음·동 제외, 연식 유지)")
        g2 = cd.assign(multi_by=cd.n_by >= 2).groupby("multi_by").agg(n=("full", "count"), ok=("full", "sum")).reset_index()
        md.append(md_table(g2.values.tolist(), ["준공연도 2개 이상", "코호트", "식별 가능"]))
        md.append("식별 불가 코호트의 열 종류: " + ", ".join(f"{k or '-'} {v}" for k, v in Counter(cd[~cd.full].nonid).items()))
    (OUT / "c03_result.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
