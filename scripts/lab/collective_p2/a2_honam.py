"""Phase A-2 — 호남 옛 시도명 표준화 건수·키 재계산(읽기 전용)."""
import sys
from collections import defaultdict
import pandas as pd
from _db import OUT, ROOT, engine, q, md_table
sys.path.insert(0, str(ROOT / "pipeline"))
from collective.building_keys import derive_building_key  # noqa
from collective_commercial.cluster_keys import make_road_cluster_key  # noqa
OLD = ["광주광역시", "전라남도"]; NEW = "전남광주통합특별시"
L = ["# A-2 결과", ""]
with engine().connect() as c:
    rows = q(c, "select asset_type, addr1, contract_year, count(*) from collective_transactions where addr1=any(:o) group by 1,2,3 order by 1,2,3", o=OLD)
    L += ["## 집합 주거 원장 옛 이름 행", md_table(rows, ["유형", "addr1", "연도", "행"]), f"합계 {sum(r[3] for r in rows):,}", ""]
    # 주거 키
    combos = q(c, "select distinct asset_type, building_key, addr1, addr2, addr3, addr4, building_name, lot_number, road_name from collective_transactions where addr1=any(:o)", o=OLD)
    m = defaultdict(set); asset_of = {}
    for r in combos:
        m[r[1]].add(derive_building_key(asset_type=r[0], addr1=NEW, addr2=r[3], addr3=r[4], addr4=r[5], building_name=r[6], lot_number=r[7], road_name=r[8]))
        asset_of[r[1]] = r[0]
    newkeys = {k for v in m.values() for k in v}
    exist = {x[0] for x in q(c, "select distinct building_key from collective_transactions where building_key = any(:k) and addr1 = :n", k=list(newkeys), n=NEW)}
    merged = sum(1 for k, v in m.items() if next(iter(v)) in exist)
    n_to_1 = pd.Series([next(iter(v)) for v in m.values()]).value_counts()
    L.append(f"- 주거 옛 키 {len(m):,} → 새 이름 키와 합쳐짐 {merged:,} · 새로 생김 {len(m)-merged:,} · 1:N {sum(1 for v in m.values() if len(v)>1)} · 여러 옛 키→한 새 키 {int((n_to_1>1).sum())}")
    by_asset = pd.DataFrame([(asset_of[k], next(iter(v)) in exist) for k, v in m.items()], columns=["asset", "merged"]).value_counts().sort_index()
    L.append(md_table([(a, str(b), int(n)) for (a, b), n in by_asset.items()], ["유형", "합쳐짐", "키"]))
    # 비주거
    cm = q(c, "select distinct asset_type, cluster_key, addr1, addr2, addr3, addr4, road_name, addr5 from collective_commercial_transactions where addr1=any(:o)", o=OLD)
    cmap = defaultdict(set); bad = 0
    for r in cm:
        a4 = r[5]
        if make_road_cluster_key(asset_type=r[0], addr1=r[2], addr2=r[3], addr3=r[4], addr4=a4, road_name=r[6]) != r[1]:
            a4 = r[7]  # 옛 적재: 리가 addr4에 있던 시점의 키
            if make_road_cluster_key(asset_type=r[0], addr1=r[2], addr2=r[3], addr3=r[4], addr4=a4, road_name=r[6]) != r[1]:
                bad += 1
        cmap[r[1]].add(make_road_cluster_key(asset_type=r[0], addr1=NEW, addr2=r[3], addr3=r[4], addr4=a4, road_name=r[6]))
    cnew = {k for v in cmap.values() for k in v}
    cex = {x[0] for x in q(c, "select distinct cluster_key from collective_commercial_transactions where cluster_key=any(:k)", k=list(cnew))}
    cmerged = sum(1 for v in cmap.values() if next(iter(v)) in cex)
    crows = q(c, "select asset_type, addr1, count(*) from collective_commercial_transactions where addr1=any(:o) group by 1,2", o=OLD)
    ccl = q(c, "select count(*) from commercial_clusters where addr1=any(:o)", o=OLD)[0][0]
    L += ["", "## 비주거", md_table(crows, ["유형", "addr1", "행"]),
          f"- cluster 옛 키 {len(cmap):,}(재계산 불일치 {bad}) → 기존 키와 합쳐짐 {cmerged:,} · 새로 생김 {len(cmap)-cmerged:,} · 1:N {sum(1 for v in cmap.values() if len(v)>1)} · commercial_clusters 옛 이름 행 {ccl:,}"]
    pd.DataFrame([(k, next(iter(v))) for k, v in cmap.items()], columns=["old", "new"]).to_csv(OUT / "a2_commercial_keymap.csv", index=False)
with engine("built").connect() as c:
    br = q(c, "select asset_type, addr1, contract_year, count(*) from built_transactions where addr1=any(:o) group by 1,2,3 order by 1,2,3", o=OLD)
    L += ["", "## 복합(키 없음, addr1만)", md_table(br, ["유형", "addr1", "연도", "행"]), f"합계 {sum(r[3] for r in br):,}"]
(OUT / "a2_result.md").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
