"""조건 3 — 매매·임대 정확 연결의 분할 전후 예측(읽기 전용, migrate 계획 재사용).

rent_sale_building_map 은 (매매 키 = 임대 키, 유형) 정확 일치 + 둘 다 유효 거래가 있는 키.
분할 뒤 새 연결 = 매매 새 키 ∩ 임대 새 키. 지금 연결 1,083개(분할 대상) 중 몇 개가 새 키로 이어지는지 센다.
"""
import sys
import pandas as pd
from sqlalchemy import text
from _db import ROOT, engine, md_table
sys.path.insert(0, str(ROOT / "pipeline")); sys.path.insert(0, str(ROOT / "pipeline" / "collective"))
from collective.building_keys import load_split_units
from collective.migrate_p2_keys import Plan, _split_part_lookup, plan_collective, plan_rent

units = load_split_units()
parts = _split_part_lookup()
plan = Plan()
with engine().connect() as c:
    plan_collective(c, units, parts, plan)
with engine("rent").connect() as c:
    plan_rent(c, units, parts, plan)
    cur = pd.read_sql(text("SELECT sale_building_key, rent_building_key, asset_type FROM rent_sale_building_map WHERE sale_building_key = ANY(:k)"),
                      c, params={"k": list(units)})
JOIN = ("apartment", "rowhouse", "officetel")
s = plan.keymap[plan.keymap.reason.str.contains("split") & plan.keymap.asset_type.isin(JOIN)]
r = plan.rentmap[plan.rentmap.asset_type.isin(JOIN)]
sale_new = s.groupby("old_key")["new_key"].apply(set).to_dict()
rent_new = r.groupby("old_key")["new_key"].apply(set).to_dict()
rows = []
restored = partial = lost = 0
new_links = 0
for base in cur["sale_building_key"]:
    sn, rn = sale_new.get(base, set()), rent_new.get(base, set())
    both = sn & rn
    new_links += len(both)
    if both and both == sn:
        restored += 1
    elif both:
        partial += 1
    else:
        lost += 1
# 한 임대 단지 → 여러 매매 단지: 정확 일치 규칙이라 0이어야 함(새 키 하나당 한 쌍)
all_new = s["new_key"].value_counts()
multi = int((all_new > 1).sum())
print(md_table([("현재 연결(분할 대상 매매 키)", len(cur)),
                ("분할 뒤 모든 매매 조각이 임대와 이어짐", restored),
                ("일부 조각만 이어짐(나머지 조각은 임대 거래 없음)", partial),
                ("하나도 안 이어짐", lost),
                ("분할 뒤 새 연결 수(조각 단위)", new_links),
                ("한 새 키가 여러 옛 키에서 옴", multi)], ["항목", "값"]))
