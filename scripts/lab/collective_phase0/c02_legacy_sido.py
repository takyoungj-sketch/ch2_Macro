"""C-02 — 옛/새 시도명 × 계약연도 건수, 단지 키 분리, mart 누락 측정 (읽기 전용).

출력: logs/collective_phase0/c02_result.md
"""
from __future__ import annotations

import sys

import pandas as pd

from _db import OUT, ROOT, engine, md_table, q

sys.path.insert(0, str(ROOT))
from pipeline.collective.building_keys import derive_building_key  # noqa: E402

SIDOS = ["광주광역시", "전라남도", "전남광주통합특별시", "강원도", "강원특별자치도", "전라북도", "전북특별자치도"]
LEDGERS = {
    "collective_transactions": ("collective", "collective_transactions", "is_valid"),
    "collective_commercial_transactions": ("collective", "collective_commercial_transactions", "is_valid"),
    "built_transactions": ("built", "built_transactions", "is_valid"),
    "rent_transactions": ("rent", "rent_transactions", "is_valid"),
}


def year_table():
    md = []
    for name, (db, t, w) in LEDGERS.items():
        with engine(db).connect() as c:
            rows = q(
                c,
                f"""select addr1, asset_type, contract_year, count(*) from {t}
                    where {w} and addr1 = any(:s) and contract_year between 2018 and 2026 group by 1,2,3""",
                s=SIDOS,
            )
        df = pd.DataFrame(rows, columns=["addr1", "at", "y", "n"])
        if df.empty:
            md.append(f"### {name}\n(해당 시도명 행 없음)")
            continue
        piv = df.pivot_table(index=["addr1"], columns="y", values="n", aggfunc="sum", fill_value=0)
        piv = piv.reindex([s for s in SIDOS if s in piv.index])
        md.append(f"### {name} (전 유형 합)\n" + md_table([[i] + [int(v) for v in r] for i, r in zip(piv.index, piv.values)], ["addr1"] + [str(c) for c in piv.columns]))
        df.to_csv(OUT / f"c02_year_{name}.csv", index=False, encoding="utf-8-sig")
    return md


def month_edge():
    """옛 이름이 끝나고 새 이름이 시작되는 월."""
    with engine("collective").connect() as c:
        rows = q(
            c,
            """select addr1, min(contract_date), max(contract_date), count(*) from collective_transactions
               where is_valid and addr1 = any(:s) group by 1 order by 1""",
            s=SIDOS,
        )
        rows2 = q(
            c,
            """select addr1, to_char(contract_date,'YYYY-MM') ym, count(*) from collective_transactions
               where is_valid and addr1 = any(:s) and contract_date between '2019-06-01' and '2021-03-31'
               group by 1,2 order by 2,1""",
            s=["광주광역시", "전라남도", "전남광주통합특별시"],
        )
    md = ["### 시도명별 계약일 범위 (collective_transactions)", md_table(rows, ["addr1", "최소", "최대", "건"])]
    piv = pd.DataFrame(rows2, columns=["a1", "ym", "n"]).pivot_table(index="ym", columns="a1", values="n", fill_value=0)
    md.append("### 호남 월별 (2019-06~2021-03)\n" + md_table([[i] + [int(v) for v in r] for i, r in zip(piv.index, piv.values)], ["월"] + list(piv.columns)))
    return md


def key_split():
    """옛 이름 행의 building_key 가 최신 mart(building_stats)에 있는지, 옛↔새 키 대응."""
    with engine("collective").connect() as c:
        mart_keys = {r[0] for r in q(c, "select distinct building_key from collective_building_stats where as_of_month=(select max(as_of_month) from collective_building_stats)")}
        tx = pd.DataFrame(
            q(
                c,
                """select addr1, asset_type, contract_year, building_key, addr2, addr3, addr4, building_name, building_year, lot_number, road_name, count(*) n
                   from collective_transactions where is_valid and addr1 = any(:s)
                   group by 1,2,3,4,5,6,7,8,9,10,11""",
                s=SIDOS,
            ),
            columns=["a1", "at", "y", "key", "a2", "a3", "a4", "name", "by", "lot", "road", "n"],
        )
    tx["in_mart"] = tx.key.isin(mart_keys)
    old = tx[tx.a1.isin(["광주광역시", "전라남도", "강원도", "전라북도"])]
    missing = old[~old.in_mart]
    md = []
    t = missing.groupby(["a1", "at", "y"]).n.sum().reset_index()
    piv = t.pivot_table(index=["a1", "at"], columns="y", values="n", fill_value=0)
    md.append("### 옛 시도명 거래 중 최신 mart 에 없는 키의 거래 수\n" + md_table([[*i] + [int(v) for v in r] for i, r in zip(piv.index, piv.values)], ["addr1", "유형"] + [str(c) for c in piv.columns]))
    tot_old = old.groupby(["a1"]).n.sum()
    md.append("옛 이름 행 합계: " + ", ".join(f"{k} {int(v):,}" for k, v in tot_old.items()))

    # 옛 키 ↔ 현재 키: 새 sido 명으로 같은 규칙 재계산
    new_name = {"광주광역시": "전남광주통합특별시", "전라남도": "전남광주통합특별시", "강원도": "강원특별자치도", "전라북도": "전북특별자치도"}
    newer = tx[tx.a1.isin(["전남광주통합특별시", "강원특별자치도", "전북특별자치도"])]
    new_keys = set(newer.key)
    # 신 시도의 키 → (a2,a3,name,by) 속성 집합
    attr_idx: dict = {}
    for r in newer.drop_duplicates("key").itertuples():
        attr_idx.setdefault((r.a1, r.a2, r.a3, r.name or "", r.lot or ""), set()).add(r.key)
    res = []
    for r in missing.drop_duplicates("key").itertuples():
        k2 = derive_building_key(asset_type=r.at, addr1=new_name[r.a1], addr2=r.a2, addr3=r.a3, addr4=r.a4,
                                 building_name=r.name, lot_number=r.lot, road_name=r.road)
        if k2 in new_keys and k2 in mart_keys:
            res.append((r.a1, r.at, "1:1 (규칙 재계산 키가 mart 에 있음)", r.key))
        else:
            cands = attr_idx.get((new_name[r.a1], r.a2, r.a3, r.name or "", r.lot or ""), set()) & mart_keys
            if len(cands) == 1:
                res.append((r.a1, r.at, "1:1 (이름·지번 대응)", r.key))
            elif len(cands) > 1:
                res.append((r.a1, r.at, "1:N", r.key))
            else:
                res.append((r.a1, r.at, "대응 불가", r.key))
    rd = pd.DataFrame(res, columns=["a1", "at", "kind", "key"])
    key_n = missing.groupby("key").n.sum()
    rd["n"] = rd.key.map(key_n)
    s = rd.groupby(["a1", "kind"]).agg(keys=("key", "count"), n=("n", "sum")).reset_index()
    md.append("### 누락 키 대응 (키 수 / 거래 수)\n" + md_table(s.values.tolist(), ["옛 시도", "대응", "키", "거래"]))
    return md


def mart_gap():
    with engine("collective").connect() as c:
        bs = q(
            c,
            """select addr1, window_years, count(*), sum(count) from collective_building_stats
               where as_of_month=(select max(as_of_month) from collective_building_stats) and addr1 = any(:s)
               group by 1,2 order by 1,2""",
            s=SIDOS,
        )
        # 7년 창(2019-11~2026-10) 거래 중 해당 키가 7y building_stats 에 없는 건
        miss7 = q(
            c,
            """with m as (select distinct building_key from collective_building_stats
                          where as_of_month=(select max(as_of_month) from collective_building_stats) and window_years=7)
               select t.addr1, count(*) filter (where m.building_key is null) miss, count(*) tot
               from collective_transactions t left join m using (building_key)
               where t.is_valid and t.contract_date >= date '2019-11-01' and t.contract_date < date '2026-11-01'
               group by 1 order by 2 desc""",
        )
        roll = q(
            c,
            """select r.window_years, r.bucket_index, min(r.period_start), max(r.period_end), count(*)
               from collective_building_rolling_stats r
               where r.as_of_month=(select max(as_of_month) from collective_building_rolling_stats)
               group by 1,2 order by 1,2""",
        )
        ann = q(
            c,
            """select addr1, contract_year, count(*), sum(count) from collective_building_annual_stats
               where addr1 = any(:s) and contract_year between 2018 and 2022 group by 1,2 order by 1,2""",
            s=SIDOS,
        )
        ms = q(
            c,
            """select region_level, left(region_code,2) sido2, window_years, count(*), sum(count)
               from market_stats where as_of_month=(select max(as_of_month) from market_stats)
               and left(region_code,2) in ('29','46','52','42','51','45') group by 1,2,3 order by 1,2,3""",
        )
    md = [
        "### building_stats 최신 as_of — 시도명별 (행/거래 합)",
        md_table(bs, ["addr1", "창", "단지", "거래"]),
        "### 7년 창 거래 중 7y building_stats 에 키가 없는 거래 (시도명별)",
        md_table([r for r in miss7 if r[1]], ["addr1", "누락", "창 내 전체"]),
        "### rolling 버킷 구성 (최신 as_of)",
        md_table(roll, ["창", "bucket", "시작", "끝", "행"]),
        "### annual_stats — 시도명×연도 (행/거래 합)",
        md_table(ann, ["addr1", "연도", "단지", "거래"]),
        "### market_stats 최신 as_of — 시도코드 앞2자리별",
        md_table(ms, ["level", "sido2", "창", "행", "거래"]),
    ]
    return md


def main():
    md = ["## 2-1 시도명 × 연도"] + year_table() + month_edge()
    md += ["## 2-2 키 분리"] + key_split()
    md += ["## 2-4 mart 영향"] + mart_gap()
    (OUT / "c02_result.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
