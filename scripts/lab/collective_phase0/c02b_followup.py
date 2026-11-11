"""C-02 보충 — 복합 옛/새 이름 유형별, market_stats 시도코드 12, 옛 키 전체의 새 키 대응, rolling 구간 수."""
import sys
import pandas as pd
from _db import OUT, ROOT, engine, md_table, q
sys.path.insert(0, str(ROOT))
from pipeline.collective.building_keys import derive_building_key  # noqa: E402

md = []
with engine("built").connect() as c:
    r = q(c, """select addr1, asset_type, contract_year, count(*), count(distinct transaction_hash) from built_transactions
               where is_valid and addr1 in ('광주광역시','전라남도','전남광주통합특별시') and contract_year between 2018 and 2021 group by 1,2,3 order by 2,3,1""")
    md += ["### 복합 원장 — 시도명×유형×연도", md_table(r, ["addr1", "유형", "연도", "건", "hash 수"])]
    r = q(c, """select a.asset_type, a.contract_year, count(*) from built_transactions a
               join built_transactions b on b.is_valid and b.addr1='전남광주통합특별시' and b.addr2=a.addr2 and coalesce(b.addr3,'')=coalesce(a.addr3,'')
                    and b.lot_number=a.lot_number and b.contract_date=a.contract_date and b.price=a.price and b.asset_type=a.asset_type
               where a.is_valid and a.addr1 in ('광주광역시','전라남도') group by 1,2 order by 1,2""")
    md += ["### 복합 — 옛 이름 행 중 새 이름 행과 (시군구·읍면동·지번·계약일·가격) 일치(중복 의심)", md_table(r, ["유형", "연도", "건"])]
with engine("collective").connect() as c:
    r = q(c, """select region_level, left(region_code,2), window_years, count(*), sum(count) from market_stats
               where as_of_month=(select max(as_of_month) from market_stats) and left(region_code,2) in ('12','29','46')
               group by 1,2,3 order by 1,2,3""")
    md += ["### market_stats 최신 — 시도코드 12/29/46", md_table(r, ["level", "sido2", "창", "행", "거래"])]
    r = q(c, """select left(beopjungri_code,2), addr1, contract_year, count(*) from collective_transactions
               where is_valid and addr1 in ('광주광역시','전라남도','전남광주통합특별시') and contract_year between 2019 and 2021 group by 1,2,3 order by 1,2,3""")
    md += ["### 집합 원장 — beopjungri_code 앞2자리 × addr1", md_table(r, ["code2", "addr1", "연도", "건"])]
    # market_stats 7y: 12 지역의 2019-11~2020-10 거래 포함 여부 = 7y count vs 원장
    r = q(c, """select count(*) from collective_transactions where is_valid and left(beopjungri_code,2)='12'
               and contract_date >= '2019-11-01' and contract_date < '2026-11-01'""")
    md.append(f"집합 원장 code 12 의 7년 창 거래: {r[0][0]:,}")
    # 옛 키 전부 → 규칙 재계산 새 키
    tx = pd.DataFrame(q(c, """select addr1, asset_type, building_key, addr2, addr3, addr4, building_name, lot_number, road_name,
                                     count(*) n, count(*) filter (where contract_date >= '2019-11-01') n7
                              from collective_transactions where is_valid and addr1 in ('광주광역시','전라남도')
                              group by 1,2,3,4,5,6,7,8,9"""),
                      columns=["a1", "at", "key", "a2", "a3", "a4", "name", "lot", "road", "n", "n7"])
    newkeys = {x[0] for x in q(c, """select distinct building_key from collective_transactions where is_valid and addr1='전남광주통합특별시'""")}
    mart7 = {x[0] for x in q(c, """select building_key from collective_building_stats where as_of_month=(select max(as_of_month) from collective_building_stats) and window_years=7 and addr1='전남광주통합특별시'""")}
    keymap = {}
    for r_ in tx.drop_duplicates("key").itertuples():
        keymap[r_.key] = None
    # 한 옛 키가 여러 주소 행이면 행별로 재계산해 집합으로
    tgt = {}
    for r_ in tx.itertuples():
        k2 = derive_building_key(asset_type=r_.at, addr1="전남광주통합특별시", addr2=r_.a2, addr3=r_.a3, addr4=r_.a4,
                                 building_name=r_.name, lot_number=r_.lot, road_name=r_.road)
        tgt.setdefault(r_.key, set()).add(k2)
    kk = tx.groupby(["key", "a1", "at"]).agg(n=("n", "sum"), n7=("n7", "sum")).reset_index()
    def kind(k):
        s = tgt[k]
        hit = s & newkeys
        if len(s) == 1 and hit:
            return "1:1 새 키 존재" + (" (7y mart 有)" if hit & mart7 else " (7y mart 無)")
        if len(s) > 1:
            return "1:N"
        return "대응 새 키 없음(2019~20에만 거래)"
    kk["kind"] = kk.key.map(kind)
    s = kk.groupby(["a1", "kind"]).agg(keys=("key", "count"), n=("n", "sum"), n7=("n7", "sum")).reset_index()
    md += ["### 옛 키 전체 → 규칙 재계산(addr1만 새 이름) 대응", md_table(s.values.tolist(), ["옛 시도", "대응", "키", "거래(19~20)", "7년 창 거래(19.11~)"])]
    s2 = kk.groupby(["a1", "at"]).agg(keys=("key", "count"), n7=("n7", "sum")).reset_index()
    md += ["### 옛 키 유형별 7년 창 거래", md_table(s2.values.tolist(), ["옛 시도", "유형", "키", "7년 창 거래"])]
    # 광산구·순천 7y rolling 구간 수 예시
    r = q(c, """select b.addr2, b.addr1, count(distinct r.bucket_index), count(distinct b.building_key)
               from collective_building_stats b join collective_building_rolling_stats r
                 on r.building_key=b.building_key and r.as_of_month=b.as_of_month and r.window_years=7
               where b.as_of_month=(select max(as_of_month) from collective_building_stats) and b.window_years=7
                 and b.addr2 in ('광산구','순천시') and b.asset_type='apartment' group by 1,2""")
    md += ["### 광산구·순천 아파트 7y rolling 버킷 수(키 묶음별)", md_table(r, ["시군구", "addr1", "버킷 종류", "키"])]
(OUT / "c02b_result.md").write_text("\n\n".join(md), encoding="utf-8")
print("\n\n".join(md))
