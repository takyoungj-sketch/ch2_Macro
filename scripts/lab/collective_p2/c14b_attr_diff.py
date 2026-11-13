"""Phase C-14 보충 — 속성 표·builder_master 불변 확인 (원본 vs 리허설, 읽기 전용).

전 = 로컬 원본 collective_stats, 후 = collective_stats_p2r. 판(snapshot_ym)을 지정한다(기본 202607).
- 기존 키(연결표 옛·새 키가 아닌 키)의 그 판 행: 바뀐 칸 수 · 원본에만/리허설에만 행 → 모두 0 이어야 함
- 연결표 새 분할 키: 그 판 행 수(유형별) · 분할 새 키 밖에서 늘어난 행 0
- 다른 판: 원본에 없는 판의 행 수 0
- builder_master 그 판: 바뀐 칸 · 원본에만 · 리허설에만(새 danji) 행
출력: 표준출력(markdown, 지번 없음). 실패 항목이 있으면 종료 코드 1.
"""
from __future__ import annotations

import argparse

import pandas as pd
from sqlalchemy import text

from _db import engine, engine_db, md_table

VOL = {"id", "updated_at", "created_at", "computed_at", "loaded_at"}


def _diff(x: pd.DataFrame, y: pd.DataFrame, key: list[str]) -> tuple[pd.DataFrame, dict, int, int]:
    m = x.merge(y, on=key, how="outer", suffixes=("_b", "_a"), indicator=True)
    both = m[m["_merge"] == "both"]
    changed = {}
    for col in x.columns:
        if col in key or col in VOL or f"{col}_b" not in both:
            continue
        b, a = both[f"{col}_b"], both[f"{col}_a"]
        d = ~((b.isna() & a.isna()) | (b.astype(str) == a.astype(str)))
        if d.any():
            changed[col] = int(d.sum())
    return m, changed, int((m["_merge"] == "left_only").sum()), int((m["_merge"] == "right_only").sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ym", default="202607")
    a = ap.parse_args()
    ym = a.ym
    b, r = engine("collective", 1_800_000), engine_db("collective_stats_p2r", 1_800_000)
    with r.connect() as c:
        km = pd.read_sql(text("SELECT old_key, new_key, reason FROM collective_building_key_map"), c)
    mapped = set(km["old_key"]) | set(km["new_key"])
    split_new = set(km.loc[km["reason"].str.contains("split", na=False), "new_key"])
    q = text("SELECT * FROM collective_building_attributes WHERE snapshot_ym = :ym")
    with b.connect() as c:
        x = pd.read_sql(q, c, params={"ym": ym})
        snaps_b = dict(c.execute(text("SELECT snapshot_ym, count(*) FROM collective_building_attributes GROUP BY 1")).all())
        bm_b = pd.read_sql(text("SELECT * FROM builder_master WHERE snapshot_ym = :ym"), c, params={"ym": ym})
    with r.connect() as c:
        y = pd.read_sql(q, c, params={"ym": ym})
        snaps_a = dict(c.execute(text("SELECT snapshot_ym, count(*) FROM collective_building_attributes GROUP BY 1")).all())
        bm_a = pd.read_sql(text("SELECT * FROM builder_master WHERE snapshot_ym = :ym"), c, params={"ym": ym})
    key = ["building_key", "asset_type", "snapshot_ym"]
    xo, yo = x[~x["building_key"].isin(mapped)], y[~y["building_key"].isin(mapped)]
    _, changed, only_b, only_a = _diff(xo, yo, key)
    new_rows = y[y["building_key"].isin(split_new)]
    outside_added = y[~y["building_key"].isin(mapped) & ~y.set_index(key).index.isin(x.set_index(key).index)]
    other_snaps = {k: v for k, v in snaps_a.items() if str(k) != ym and k not in snaps_b}
    bkey = [c for c in ("snapshot_ym", "danji_code") if c in bm_b.columns]
    _, bm_changed, bm_only_b, bm_only_a = _diff(bm_b, bm_a, bkey)
    checks = [
        (f"기존 키 {ym} 행 바뀐 칸", sum(changed.values()), sum(changed.values()) == 0, str(changed) if changed else ""),
        (f"기존 키 {ym} 원본에만 있는 행", only_b, only_b == 0, ""),
        (f"기존 키 {ym} 리허설에만 있는 행(분할 새 키 밖 추가)", only_a, only_a == 0, ""),
        ("원본에 없는 다른 판 행", sum(other_snaps.values()), not other_snaps, str(other_snaps) if other_snaps else ""),
        (f"분할 새 키 {ym} 행", len(new_rows), True, str(new_rows.groupby("asset_type").size().to_dict())),
        (f"분할 새 키 {ym} 행이 있는 키", new_rows["building_key"].nunique(), True, f"/ 분할 새 키 {len(split_new):,}"),
        (f"builder_master {ym} 바뀐 칸", sum(bm_changed.values()), sum(bm_changed.values()) == 0, str(bm_changed) if bm_changed else ""),
        (f"builder_master {ym} 원본에만", bm_only_b, bm_only_b == 0, ""),
        (f"builder_master {ym} 리허설에만(추가 danji)", bm_only_a, True, "기존 행 불변이면 추가는 보고만"),
    ]
    # 공시지가: 기존 키 값 불변, 분할 새 키 밖 추가 0
    lq = text("SELECT * FROM collective_building_assessed_land_price")
    with b.connect() as c:
        lb = pd.read_sql(lq, c)
    with r.connect() as c:
        la = pd.read_sql(lq, c)
    lk = ["building_key", "asset_type"]
    _, lp_changed, lp_only_b, lp_only_a = _diff(lb[~lb["building_key"].isin(mapped)], la[~la["building_key"].isin(mapped)], lk)
    lp_new = la[la["building_key"].isin(split_new)]
    checks += [
        ("공시지가 기존 키 바뀐 칸", sum(lp_changed.values()), sum(lp_changed.values()) == 0, str(lp_changed) if lp_changed else ""),
        ("공시지가 기존 키 원본에만", lp_only_b, lp_only_b == 0, ""),
        ("공시지가 분할 새 키 밖 추가", lp_only_a, lp_only_a == 0, ""),
        ("공시지가 분할 새 키 행", len(lp_new), True, str(lp_new.groupby("asset_type").size().to_dict())),
    ]
    assert len(outside_added) == only_a
    print(md_table([("OK" if ok else "NG", n, v, note) for n, v, ok, note in checks], ["판정", "항목", "값", "비고"]))
    raise SystemExit(0 if all(ok for _, _, ok, _ in checks) else 1)


if __name__ == "__main__":
    main()
