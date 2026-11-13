"""Phase C-14 보충 — title_fill 사본 리허설 뒤 collective_building_attributes 변화 원인(읽기 전용).

전 = 로컬 원본 collective_stats, 후 = collective_stats_p2r. 분할 새 키·옛 키는 제외(키가 바뀐 행).
같은 (키·유형·snapshot_ym) 행에서 바뀐 칸 수, 원본에 없던 행의 match_tier·match_rule 분포.
출력: 표준출력(markdown, 지번 없음)
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from _db import engine, engine_db, md_table

YM = "202610"


def main():
    b, a = engine("collective", 1_800_000), engine_db("collective_stats_p2r", 1_800_000)
    with a.connect() as c:
        km = pd.read_sql(text("SELECT old_key, new_key FROM collective_building_key_map"), c)
        cols = [r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='collective_building_attributes' "
            "AND table_schema='public' ORDER BY ordinal_position"))]
    skip = set(km["old_key"]) | set(km["new_key"])
    q = text("SELECT * FROM collective_building_attributes WHERE snapshot_ym = :ym")
    with b.connect() as c:
        x = pd.read_sql(q, c, params={"ym": YM})
    with a.connect() as c:
        y = pd.read_sql(q, c, params={"ym": YM})
    x, y = x[~x["building_key"].isin(skip)], y[~y["building_key"].isin(skip)]
    key = ["building_key", "asset_type", "snapshot_ym"]
    m = x.merge(y, on=key, how="outer", suffixes=("_b", "_a"), indicator=True)
    both = m[m["_merge"] == "both"]
    vol = {"id", "updated_at", "created_at", "computed_at"}
    changed_cols = {}
    for col in cols:
        if col in key or col in vol or f"{col}_b" not in both:
            continue
        d = both[f"{col}_b"].astype(str) != both[f"{col}_a"].astype(str)
        if d.any():
            changed_cols[col] = int(d.sum())
    added = m[m["_merge"] == "right_only"]
    print(md_table([("원본·리허설 둘 다 있는 행", len(both)), ("리허설에만(추가)", len(added)),
                    ("원본에만(사라짐)", int((m["_merge"] == "left_only").sum()))], ["구분", "행"]))
    print()
    print(md_table(sorted(changed_cols.items(), key=lambda kv: -kv[1]), ["바뀐 칸", "행"]))
    print()
    tier = added.groupby(["asset_type", "match_tier_a", "match_rule_a"], dropna=False).size().reset_index(name="n") \
        if "match_tier_a" in added else pd.DataFrame()
    print(md_table([tuple(r) for r in tier.sort_values("n", ascending=False).head(15).values],
                   ["유형", "tier", "rule", "행"]))


if __name__ == "__main__":
    main()
