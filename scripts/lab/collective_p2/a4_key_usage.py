"""Phase A-4 — 바뀌는 키가 붙어 있는 표별 행 수 (읽기 전용).

바뀌는 키 = 호남 옛 키(A-2) ∪ (a) 분할 키(A-1). 비주거 cluster 옛 키(A-2)는 cluster 표에서 센다.
"""
import pandas as pd

from _db import OUT, engine, md_table, q

hon = pd.read_csv(OUT / "a2_honam_keymap.csv", encoding="utf-8-sig")
hon_old = set(hon.iloc[:, 0])
hon_new = set(hon["new_key"])
cls = pd.read_csv(OUT / "a1_classified.csv", encoding="utf-8-sig")
split = set(cls.loc[cls.cls == "a", "key"])
ckeys = set(pd.read_csv(OUT / "a2_commercial_keymap.csv")["old"])

T = [
    ("collective_transactions", "building_key"),
    ("collective_building_stats", "building_key"),
    ("collective_building_rolling_stats", "building_key"),
    ("collective_building_annual_stats", "building_key"),
    ("collective_presale_lifetime_stats", "building_key"),
    ("collective_building_attributes", "building_key"),
    ("collective_building_geocodes", "building_key"),
    ("collective_building_assessed_land_price", "building_key"),
    ("new_apartment_complex_year", "building_key"),
]
CT = [
    ("collective_commercial_transactions", "cluster_key"),
    ("commercial_clusters", "cluster_key"),
    ("collective_commercial_cluster_stats", "cluster_key"),
    ("collective_commercial_cluster_rolling_stats", "cluster_key"),
    ("collective_commercial_cluster_annual_stats", "cluster_key"),
    ("collective_commercial_map_geocodes", "cluster_key"),
    ("collective_cluster_stats", "cluster_key"),
    ("collective_cluster_rolling_stats", "cluster_key"),
    ("collective_cluster_annual_stats", "cluster_key"),
]
rows = []
with engine().connect() as c:
    for t, col in T:
        a = q(c, f"select count(*), count(distinct {col}) from {t} where {col} = any(:k)", k=list(hon_old))[0]
        b = q(c, f"select count(*), count(distinct {col}) from {t} where {col} = any(:k)", k=list(hon_new - hon_old))[0]
        s = q(c, f"select count(*), count(distinct {col}) from {t} where {col} = any(:k)", k=list(split))[0]
        rows.append((t, a[0], a[1], b[0], b[1], s[0], s[1]))
    crow = []
    for t, col in CT:
        a = q(c, f"select count(*), count(distinct {col}) from {t} where {col} = any(:k)", k=list(ckeys))[0]
        crow.append((t, a[0], a[1]))
    # 분할 키의 속성 매칭 tier
    tiers = q(c, "select match_tier, count(*) from collective_building_attributes where building_key = any(:k) group by 1 order by 1", k=list(split))
with engine("rent").connect() as c:
    r1 = q(c, "select count(*), count(distinct sale_building_key) from rent_sale_building_map where sale_building_key = any(:k)", k=list(split))[0]
    r2 = q(c, "select count(*), count(distinct sale_building_key) from rent_sale_building_map where sale_building_key = any(:k)", k=list(hon_old))[0]
    r3 = q(c, "select count(*), count(distinct building_key) from rent_transactions where building_key = any(:k)", k=list(split))[0]
L = ["# A-4 표별 영향 행", "",
     md_table(rows, ["표", "호남 옛 키 행", "옛 키 수", "호남 대응 새 키 행", "새 키 수", "(a) 분할 키 행", "분할 키 수"]), "",
     md_table(crow, ["비주거 표", "옛 cluster 키 행", "키 수"]), "",
     "분할 키 속성 tier: " + str(tiers),
     f"rent_sale_building_map: 분할 키 {r1[1]:,}개({r1[0]:,}행), 호남 옛 키 {r2[1]:,}개({r2[0]:,}행)",
     f"rent_transactions에 같은 키(분할 대상): {r3[1]:,}개 {r3[0]:,}행 — 임대 키도 같은 이름 규칙이라 같은 혼입 가능"]
(OUT / "a4_result.md").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
