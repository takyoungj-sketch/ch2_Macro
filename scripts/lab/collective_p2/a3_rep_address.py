"""Phase A-3 — mart 대표 주소 규칙 측정 (읽기 전용).

현행: 주소 열마다 MAX() → 어느 거래에도 없는 합성 주소.
새 규칙: 키(창)별 거래가 가장 많은 (addr3, addr4, addr5, beopjungri_code, lot_number, road_name) 한 세트.
        동률이면 최신 계약일, 그다음 결정적 순서(코드·지번·도로명 오름차순).

측정(최신 as_of, 3/5/7년):
  1) 합성 주소 행: mart 주소 세트가 그 창의 어떤 거래 세트와도 같지 않은 행
  2) 0단계 분류(c01 classify)로 (a)·(d, 세종 제외) 행 수 — 현행 mart vs 새 규칙
  3) 내수읍 반대 방향 혼입: 내수읍 코드 mart 행 중 leaf ≠ 내수읍 (현행 / 새 규칙 / 새 규칙 + A-1 분할)
  4) 임대 mart(rent_building_stats) 같은 측정(적용 여부는 T 결정)
"""
from __future__ import annotations

import sys
import time

import pandas as pd

from _db import OUT, ROOT, engine, md_table, q

sys.path.insert(0, str(ROOT / "scripts" / "lab" / "collective_phase0"))
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("c01", ROOT / "scripts" / "lab" / "collective_phase0" / "c01_region_mismatch.py")
c01 = importlib.util.module_from_spec(spec)
_saved = sys.modules.get("_db")
spec.loader.exec_module(c01)

t0 = time.time()
COLS = ["addr3", "addr4", "addr5", "beopjungri_code", "lot_number", "road_name"]


def log(*a):
    print(f"[{time.time()-t0:7.1f}s]", *a, flush=True)


def rep_sql(tx_table: str, key_expr: str, extra_where: str) -> str:
    cols = ", ".join(COLS)
    return f"""
    WITH g AS (
      SELECT {key_expr} AS building_key, asset_type, {cols}, count(*) n, max(contract_date) d
      FROM {tx_table}
      WHERE is_valid = true AND contract_date IS NOT NULL
        AND contract_date >= :ps AND contract_date <= :pe {extra_where}
      GROUP BY 1,2,{",".join(str(i) for i in range(3, 3 + len(COLS)))}
    ), r AS (
      SELECT g.*, count(*) OVER (PARTITION BY building_key, asset_type) AS n_sets,
             row_number() OVER (PARTITION BY building_key, asset_type
               ORDER BY n DESC, d DESC, beopjungri_code NULLS LAST, lot_number NULLS LAST, road_name NULLS LAST,
                        addr4 NULLS LAST, addr5 NULLS LAST) AS rk
      FROM g
    )
    SELECT building_key, asset_type, {cols}, n_sets, n AS rep_n,
           (SELECT 1) AS dummy
    FROM r WHERE rk = 1
    """


def sets_sql(tx_table: str, key_expr: str, extra_where: str) -> str:
    cols = ", ".join(COLS)
    return f"""SELECT DISTINCT {key_expr} AS building_key, asset_type, {cols} FROM {tx_table}
               WHERE is_valid = true AND contract_date IS NOT NULL AND contract_date >= :ps AND contract_date <= :pe {extra_where}"""


def norm(df: pd.DataFrame) -> pd.Series:
    cols = ["building_key", "asset_type"] + COLS
    s = df[cols[0]].fillna("").astype(object).map(str)
    for col in cols[1:]:
        s = s + "|" + df[col].astype(object).where(df[col].notna(), "").map(str)
    return s


def classify_df(df, names_all, names_act, sgg_act) -> pd.Series:
    leaf = [c01.leaf_of(a, b) for a, b in zip(df["addr3"], df["addr4"])]
    return pd.Series([c01.classify(l, a5, str(cd or ""), names_all, names_act, sgg_act)
                      for l, a5, cd in zip(leaf, df["addr5"], df["beopjungri_code"])], index=df.index)


def measure(db: str, mart: str, tx: str, key_expr: str, mart_where: str, tx_where: str, label: str, names):
    names_all, names_act, sgg_act = names
    out = []
    with engine(db).connect() as c:
        asof = q(c, f"select max(as_of_month) from {mart}")[0][0]
        wins = q(c, f"""select window_years, min(period_start), max(period_end), count(*) from {mart}
                       where as_of_month=:a {mart_where} group by 1 order by 1""", a=asof)
        for w, ps, pe, nrows in wins:
            m = pd.read_sql(
                f"""select building_key, asset_type, addr1, {", ".join(COLS)} from {mart}
                    where as_of_month=%(a)s and window_years=%(w)s {mart_where}""",
                c, params={"a": asof, "w": w})
            from sqlalchemy import text
            rep = pd.read_sql(text(rep_sql(tx, key_expr, tx_where)), c, params={"ps": ps, "pe": pe})
            sets = pd.read_sql(text(sets_sql(tx, key_expr, tx_where)), c, params={"ps": ps, "pe": pe})
            sset = set(norm(sets))
            m_synth = ~norm(m).isin(sset)
            rep_synth = ~norm(rep).isin(sset)
            m["cls"] = classify_df(m, names_all, names_act, sgg_act)
            rep = rep.merge(m[["building_key", "asset_type", "addr1"]], on=["building_key", "asset_type"], how="inner")
            rep["cls"] = classify_df(rep, names_all, names_act, sgg_act)
            sej_m = m["addr1"].fillna("").str.startswith("세종")
            sej_r = rep["addr1"].fillna("").str.startswith("세종")
            out.append(dict(
                mart=label, window=int(w), asof=str(asof), rows=len(m), rep_rows=len(rep),
                synth_now=int(m_synth.sum()), synth_new=int(rep_synth.sum()),
                a_now=int((m.cls == "a").sum()), a_new=int((rep.cls == "a").sum()),
                d_now=int(((m.cls == "d") & ~sej_m).sum()), d_new=int(((rep.cls == "d") & ~sej_r).sum()),
                multi_set_keys=int((rep["n_sets"] > 1).sum()),
                addr_changed=int((~norm(m).isin(set(norm(rep)))).sum()),
                code_changed=int((m.merge(rep[["building_key", "asset_type", "beopjungri_code"]], on=["building_key", "asset_type"],
                                          suffixes=("", "_r")).pipe(lambda x: (x.beopjungri_code.fillna("") != x.beopjungri_code_r.fillna("")))).sum()),
                emd_changed=int((m.merge(rep[["building_key", "asset_type", "beopjungri_code"]], on=["building_key", "asset_type"],
                                         suffixes=("", "_r")).pipe(lambda x: (x.beopjungri_code.fillna("").str[:8] != x.beopjungri_code_r.fillna("").str[:8]))).sum()),
            ))
            log(label, w, out[-1])
            if label == "collective" and w == 5:
                m.to_pickle(OUT / "a3_mart5.pkl")
                rep.to_pickle(OUT / "a3_rep5.pkl")
    return out


def main():
    rc, names_all, names_act, sgg_act = c01.load_region_codes()
    names = (names_all, names_act, sgg_act)
    res = []
    res += measure("collective", "collective_building_stats", "collective_transactions", "building_key", "",
                   "AND unit_price IS NOT NULL AND unit_price > 0", "collective", names)
    try:
        with engine("rent").connect() as c:
            rk = q(c, "select count(*) from information_schema.columns where table_name='rent_building_stats' and column_name='addr5'")[0][0]
        if rk:
            sys.path.insert(0, str(ROOT / "pipeline")); sys.path.insert(0, str(ROOT / "pipeline" / "rent"))
            from stats_pack import BUILDING_KEY_SQL
            res += measure("rent", "rent_building_stats", "rent_transactions",
                           BUILDING_KEY_SQL, "", "", "rent", names)
    except Exception as ex:  # noqa: BLE001
        log("rent ERR", ex)
    R = pd.DataFrame(res)
    R.to_csv(OUT / "a3_summary.csv", index=False)
    L = ["# A-3 결과", "", md_table([tuple(r) for r in R.itertuples(index=False)], list(R.columns))]

    # 내수읍 반대 방향 혼입
    with engine().connect() as c:
        emd = [r[0] for r in q(c, """select distinct eupmyeondong_code from region_codes
                                      where eupmyeondong_name='내수읍' and sigungu_name like '청주%'""")]
    m = pd.read_pickle(OUT / "a3_mart5.pkl")
    rep = pd.read_pickle(OUT / "a3_rep5.pkl")
    for nm, df in (("현행", m), ("새 규칙", rep)):
        sub = df[df["beopjungri_code"].fillna("").str[:8].isin(emd)]
        leaf = [c01.leaf_of(a, b) for a, b in zip(sub["addr3"], sub["addr4"])]
        bad = sub[[lf != "내수읍" for lf in leaf]]
        L.append(f"- 내수읍 코드 mart 행(5년) {nm}: {len(sub)}행, leaf≠내수읍 {len(bad)}행")
        bad[["asset_type", "addr3", "addr4", "addr5", "beopjungri_code"]].to_csv(OUT / f"a3_naesu_{nm}.csv", index=False, encoding="utf-8-sig")
    (OUT / "a3_result.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
