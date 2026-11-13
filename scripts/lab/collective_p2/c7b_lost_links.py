"""Phase C-7 보충 — 분할이 아닌데 전후로 사라진 매매·임대 연결의 원인 분류(읽기 전용, 리허설 DB).

분류: 호남 키 변경(연결표 old_key → new_key 가 이어짐 / 안 이어짐) · 매매 원장에서 그 키·유형 0건 · 임대 쪽 짝 키 없음 · 그 밖.
출력: 표준출력 + logs/collective_p2/c7b_lost_links.csv (키만, 지번 없음)
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from _db import OUT, engine_db, md_table


def main():
    c_eng, r_eng = engine_db("collective_stats_p2r"), engine_db("rent_stats_p2r")
    with c_eng.connect() as c:
        km = pd.read_sql(text("SELECT old_key, new_key, asset_type, reason FROM collective_building_key_map"), c)
    with r_eng.connect() as r:
        before = pd.read_sql(text("SELECT sale_building_key, rent_building_key, asset_type FROM rent_sale_building_map_p2_before"), r)
        after = pd.read_sql(text("SELECT sale_building_key, rent_building_key, asset_type FROM rent_sale_building_map"), r)
    split_olds = set(km.loc[km["reason"].str.contains("split", na=False), "old_key"])
    keep_b = before[~before["sale_building_key"].isin(split_olds)]
    ka = set(map(tuple, after[["sale_building_key", "asset_type"]].values))
    lost = keep_b[[tuple(x) not in ka for x in keep_b[["sale_building_key", "asset_type"]].values]].copy()
    remap = km.groupby("old_key")["new_key"].apply(set).to_dict()
    reason = dict(zip(km["old_key"], km["reason"]))
    linked_after = set(after["sale_building_key"])
    rows = []
    with c_eng.connect() as c, r_eng.connect() as r:
        for _, x in lost.iterrows():
            k, at, rk = x["sale_building_key"], x["asset_type"], x["rent_building_key"]
            n_sale = c.execute(text("SELECT count(*) FROM collective_transactions WHERE building_key=:k AND asset_type=:a AND is_valid"),
                               {"k": k, "a": at}).scalar()
            n_rent = r.execute(text("SELECT count(*) FROM rent_transactions WHERE building_key=:k AND is_valid"), {"k": rk}).scalar()
            if k in remap:
                cat = "호남 키 변경 → 새 키로 이어짐" if remap[k] & linked_after else "호남 키 변경 → 새 키 연결 없음"
            elif n_sale == 0:
                cat = "매매 원장에 그 키·유형 0건"
            elif n_rent == 0:
                cat = "임대 원장에 짝 키 0건"
            else:
                cat = "그 밖"
            rows.append({"sale_key": k, "asset_type": at, "rent_key": rk, "reason": reason.get(k), "sale_n": n_sale,
                         "rent_n": n_rent, "category": cat})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "c7b_lost_links.csv", index=False, encoding="utf-8-sig")
    summ = df.groupby("category").size().reset_index(name="n") if len(df) else pd.DataFrame(columns=["category", "n"])
    print(md_table([tuple(v) for v in summ.values], ["원인", "연결 수"]))
    print(df[["asset_type", "reason", "sale_n", "rent_n", "category"]].to_string())


if __name__ == "__main__":
    main()
