"""집합 1단계 Phase 2 — C-03 자동 제외를 제품 경로로 측정 (읽기 전용).

1) 0단계 식별 불가 51곳(logs/collective_phase0/c03_detail.csv): run_building_regression 기본 변수
   (면적·연식·층(상대)·동·반기, 선형) 5년 창. 자동 제외 끔/켬 비교: 식별 여부·제외 변수·R²·CV-MAPE.
2) 주거 코호트 10개(같은 읍면동 아파트 2~5곳): run_cohort_regression 기본 변수. 제외 변수 분포.
3) 비주거 cluster 10곳: 측정만(적용 안 함). 기본 변수로 _run_regression_core 적합 후 식별 불가 열.

출력: logs/collective_p1/c03_product_check.md, c03_product_sites.csv (단지 키만, 지번 없음)
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.collective.regression import engine as E  # noqa: E402
from app.collective.schemas import CollectiveRegressionRequest  # noqa: E402
from app.collective_commercial.regression import engine as CE  # noqa: E402
from app.collective_commercial.schemas import CommercialRegressionRequest  # noqa: E402
from app.config import settings  # noqa: E402
from app.regression_identifiability import nonidentifiable_columns  # noqa: E402

OUT = ROOT / "logs" / "collective_p1"
OUT.mkdir(parents=True, exist_ok=True)
W0, W1 = date(2021, 11, 1), date(2026, 10, 31)
SEED = 20261111

TX = text(
    """SELECT id AS transaction_id, building_key, price, unit_price, exclusive_area, building_age, floor, dong,
              housing_subtype, contract_year, contract_month
       FROM collective_transactions
       WHERE building_key IN :keys AND is_valid = true AND contract_date >= :d0 AND contract_date <= :d1"""
)


def eng():
    return create_engine(
        settings.collective_database_url,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=600000"},
    )


def load(conn, keys):
    from sqlalchemy import bindparam

    q = TX.bindparams(bindparam("keys", expanding=True))
    return pd.DataFrame(conn.execute(q, {"keys": list(keys), "d0": W0, "d1": W1}).mappings().all())


def req(model_type="linear"):
    return CollectiveRegressionRequest(asset_type="apartment", model_type=model_type, contract_date_from=W0, contract_date_to=W1)


def md_table(rows, headers):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def sites(conn):
    d = pd.read_csv(ROOT / "logs" / "collective_phase0" / "c03_detail.csv", encoding="utf-8-sig")
    keys = d.loc[d.cause != "식별 가능", "key"].tolist()
    rows = []
    for bk in keys:
        df = load(conn, [bk])
        with E.auto_exclusion_disabled():
            b = E.run_building_regression(df, bk, bk[:8], req())
        a = E.run_building_regression(df, bk, bk[:8], req())
        ident = a.identifiability
        rows.append(dict(
            key=bk, phase0_cause=d.loc[d.key == bk, "cause"].iloc[0], n=a.n,
            product_unidentified=ident is not None,
            identified_after=(ident is None) or (ident.rank_after == ident.cols_after),
            excluded="+".join(e.label if e.variable in ("building_age", "exclusive_area", "dong_unknown") else e.variable
                              for e in a.excluded_variables),
            r2_before=b.r_squared, r2_after=a.r_squared, cv_before=b.cv_mape, cv_after=a.cv_mape,
            ident_warn_before=any("모형 식별" in w for w in b.warnings), ident_warn_after=any("모형 식별" in w for w in a.warnings),
        ))
    return pd.DataFrame(rows)


def cohorts(conn, n=10):
    pool = pd.DataFrame(conn.execute(text(
        """select building_key k, addr1, addr2, addr3, coalesce(addr4,'') a4, count(*) n from collective_transactions
           where is_valid and asset_type='apartment' and contract_date >= :d0 and contract_date <= :d1
           group by 1,2,3,4,5 having count(*) >= 30"""), {"d0": W0, "d1": W1}).fetchall(), columns=["k", "a1", "a2", "a3", "a4", "n"])
    grp = pool.groupby(["a1", "a2", "a3", "a4"]).filter(lambda g: len(g) >= 2).groupby(["a1", "a2", "a3", "a4"])
    names = list(grp.groups)
    rng = np.random.default_rng(SEED)
    out = []
    for i in rng.permutation(len(names))[: n * 3]:
        if len(out) >= n:
            break
        g = grp.get_group(names[i]).sort_values("n", ascending=False).head(5)
        keys = g.k.tolist()
        df = load(conn, keys)
        r = E.run_cohort_regression(df, keys, "코호트", req())
        ident = r.identifiability
        out.append(dict(n_bld=len(keys), n=r.n, unidentified=ident is not None,
                        identified_after=(ident is None) or ident.rank_after == ident.cols_after,
                        excluded="+".join(sorted({e.variable for e in r.excluded_variables})) or "-",
                        building_fe=any(c.name.startswith("bld_") for c in r.coefficients),
                        n_build_year=int((pd.to_numeric(df["contract_year"], errors="coerce")
                                          - pd.to_numeric(df["building_age"], errors="coerce")).round().nunique())))
    return pd.DataFrame(out)


def commercial(conn, n=10):
    pool = conn.execute(text(
        """select cluster_key, asset_type, count(*) n from collective_commercial_transactions
           where is_valid and contract_date >= :d0 and contract_date <= :d1 group by 1,2 having count(*) >= 30"""),
        {"d0": W0, "d1": W1}).fetchall()
    rng = np.random.default_rng(SEED)
    picks = [pool[i] for i in rng.permutation(len(pool))[:n]]
    rows = []
    for ck, at, cnt in picks:
        df = pd.DataFrame(conn.execute(text(
            """SELECT id AS transaction_id, price, unit_price, gross_area, land_area, building_age, building_year, floor,
                      zone_type, building_use, road_width_label, road_code, addr4, contract_year, contract_month,
                      asset_type, building_key
               FROM collective_commercial_transactions
               WHERE cluster_key = :ck AND is_valid AND contract_date >= :d0 AND contract_date <= :d1 ORDER BY id"""),
            {"ck": ck, "d0": W0, "d1": W1}).mappings().all())
        body = CommercialRegressionRequest(contract_date_from=W0, contract_date_to=W1)
        model, _x, _m, resp = CE._run_regression_core(df, body, is_shop=(at == "collective_shop"))
        if model is None:
            rows.append(dict(asset=at, n=int(cnt), fit=False, cols=None, unidentified="-", note="; ".join(resp.warnings)[:80]))
            continue
        names = [str(c) for c in model.params.index]
        bad = [c for c in nonidentifiable_columns(model.model.exog, names) if c != "const"]
        fam = Counter(("building_age" if c == "building_age" else c.split("_")[0]) for c in bad)
        rows.append(dict(asset=at, n=int(model.nobs), fit=True, cols=len(names),
                         unidentified="+".join(f"{k}×{v}" for k, v in sorted(fam.items())) or "없음",
                         note="모형 식별 경고" if any("모형 식별" in w for w in resp.warnings) else ""))
    return pd.DataFrame(rows)


def main():
    with eng().connect() as c:
        s = sites(c)
        co = cohorts(c)
        cm = commercial(c)
    s.to_csv(OUT / "c03_product_sites.csv", index=False, encoding="utf-8-sig")
    md = ["# Phase 2 — C-03 제품 경로 측정"]
    md.append(f"## 0단계 식별 불가 51곳 (제품 기본 변수, 선형, 5년 창)\n\n표본 {len(s)}곳 · 제품 설계에서도 식별 불가 {int(s.product_unidentified.sum())}곳 · "
              f"제외 후 식별 가능 {int(s.identified_after.sum())}/{len(s)} · "
              f"R² 변화(>1e-6) {int(((s.r2_after - s.r2_before).abs() > 1e-6).sum())}곳 · "
              f"CV-MAPE 변화(>0.05%p) {int(((s.cv_after - s.cv_before).abs() > 0.05).sum())}곳 · "
              f"'모형 식별' 경고 {int(s.ident_warn_before.sum())} → {int(s.ident_warn_after.sum())}")
    md.append(md_table([(k, int(v)) for k, v in s.excluded.replace("", "(없음)").value_counts().items()], ["제외 변수", "단지"]))
    md.append(md_table([(k, int(v)) for k, v in pd.crosstab(s.phase0_cause, s.product_unidentified).stack().items()],
                       ["0단계 판정 × 제품 식별 불가", "단지"]))
    md.append(md_table([("R² 중앙값", f"{s.r2_before.median():.4f}", f"{s.r2_after.median():.4f}"),
                        ("CV-MAPE 중앙값(%)", f"{s.cv_before.median():.2f}", f"{s.cv_after.median():.2f}")],
                       ["지표", "제외 전", "제외 후"]))
    md.append("## 주거 코호트 10개\n\n" + md_table(co.values.tolist(), list(co.columns)))
    md.append("## 비주거 cluster 10곳 (측정만, 적용 안 함)\n\n" + md_table(cm.values.tolist(), list(cm.columns)))
    (OUT / "c03_product_check.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
