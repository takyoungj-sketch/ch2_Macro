"""Phase C-7 — 매매·임대 연결 실측(조건 4). 리허설 DB(읽기 전용).

전: rent_stats_p2r.rent_sale_building_map_p2_before (이전 직전 전체 사본) / 후: 재생성된 rent_sale_building_map
분할 옛 키별: 전 조각 이어짐 / 일부만 / 끊김. 다중 연결: 한 임대 키가 여러 매매 키에, 한 매매 키가 여러 임대 키에.
정확성: 이어진 연결(분할 조각)마다 임대 쪽 최빈 법정동8·지번이 매매 조각의 최빈 법정동8·지번과 같은지.
표본(지번 포함)은 logs/collective_p2/c7_mismatch_sample.csv.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

import sys

from _db import OUT, ROOT, engine_db, md_table

sys.path.insert(0, str(ROOT / "pipeline"))
from rent.build_sale_building_map import c2_hold_keys, exact_links  # noqa: E402


def is_c01_split(reason: str | None) -> bool:
    """연결표 reason 이 C-01(동 단위) 분할인가. '+' 로 이은 복합 reason 에 c2 가 하나라도 들면 C-01 집계에서 뺀다."""
    parts = [p.strip() for p in str(reason or "").split("+") if p.strip()]
    return "split" in parts and not any(p.startswith("c2") for p in parts)


def c01_split_rows(km: pd.DataFrame) -> pd.DataFrame:
    return km[km["reason"].map(is_c01_split)].drop(columns="reason").reset_index(drop=True)


def mode_addr(conn, table: str, keys: list[str]) -> pd.DataFrame:
    return pd.read_sql(text(f"""
        SELECT DISTINCT ON (building_key) building_key, left(beopjungri_code, 8) AS emd8, lot_number, n
        FROM (SELECT building_key, beopjungri_code, lot_number, count(*) n FROM {table}
              WHERE building_key = ANY(:k) AND is_valid GROUP BY 1,2,3) z
        ORDER BY building_key, n DESC, beopjungri_code NULLS LAST, lot_number NULLS LAST"""), conn, params={"k": keys})


def main():
    c_eng, r_eng = engine_db("collective_stats_p2r"), engine_db("rent_stats_p2r")
    with c_eng.connect() as c:
        # C-01 분할만 — c2 가 든 reason(c2_split·c2_chain·split+c2_split·honam_sido+c2_split …)은 모두 뺀다.
        # C-2 로 옮겨진 쌍은 아래 「C-2 보류」에서 따로 센다.
        km = c01_split_rows(pd.read_sql(text("""SELECT old_key, new_key, asset_type, reason FROM collective_building_key_map
                                                 WHERE reason LIKE '%split%'"""), c))
        hold = c2_hold_keys(c)
        sale_keys = {(str(a), str(k).strip()) for k, a in c.execute(text(
            "SELECT DISTINCT building_key, asset_type FROM collective_transactions WHERE is_valid "
            "AND asset_type IN ('apartment', 'rowhouse', 'officetel')"))}
    with r_eng.connect() as r:
        before = pd.read_sql(text("SELECT sale_building_key, rent_building_key, asset_type FROM rent_sale_building_map_p2_before"), r)
        after = pd.read_sql(text("SELECT sale_building_key, rent_building_key, asset_type FROM rent_sale_building_map"), r)
        rent_keys = {(str(a), str(k).strip()) for k, a in r.execute(text(
            "SELECT DISTINCT building_key, asset_type FROM rent_transactions WHERE is_valid "
            "AND asset_type IN ('apartment', 'rowhouse', 'officetel')"))}
    _, held = exact_links(sale_keys, rent_keys, hold)
    held_by = pd.Series([a for a, _ in held]).value_counts().to_dict() if held else {}
    leaked = int(after["sale_building_key"].str.strip().isin(hold).sum())
    olds = set(km["old_key"])
    b_split = before[before["sale_building_key"].isin(olds)]
    pieces = km.groupby("old_key")["new_key"].apply(set).to_dict()
    linked = set(after["sale_building_key"])
    full = part = lost = 0
    for k in b_split["sale_building_key"]:
        got = pieces.get(k, set()) & linked
        if got and got == pieces.get(k, set()):
            full += 1
        elif got:
            part += 1
        else:
            lost += 1
    multi_r = int(after.groupby("rent_building_key")["sale_building_key"].nunique().gt(1).sum())
    multi_s = int(after.groupby("sale_building_key")["rent_building_key"].nunique().gt(1).sum())
    # 분할 아닌 연결의 전후 변화
    keep_b = before[~before["sale_building_key"].isin(olds)]
    kb = set(map(tuple, keep_b[["sale_building_key", "asset_type"]].values))
    ka = set(map(tuple, after[["sale_building_key", "asset_type"]].values))
    lost_other = len(kb - ka)
    # 정확성: 분할 조각 연결
    new_links = after[after["sale_building_key"].isin(set(km["new_key"]))]
    keys = sorted(set(new_links["sale_building_key"]) | set(new_links["rent_building_key"]))
    with c_eng.connect() as c:
        sa = mode_addr(c, "collective_transactions", keys).rename(columns={"emd8": "s_emd8", "lot_number": "s_lot", "n": "s_n"})
    with r_eng.connect() as r:
        ra = mode_addr(r, "rent_transactions", keys).rename(columns={"emd8": "r_emd8", "lot_number": "r_lot", "n": "r_n"})
    m = (new_links.merge(sa, left_on="sale_building_key", right_on="building_key", how="left").drop(columns="building_key")
         .merge(ra, left_on="rent_building_key", right_on="building_key", how="left").drop(columns="building_key"))
    m["emd_ok"] = m["s_emd8"] == m["r_emd8"]
    m["lot_ok"] = m["s_lot"].fillna("") == m["r_lot"].fillna("")
    bad = m[~m["emd_ok"] | ~m["lot_ok"]]
    bad.sample(n=min(20, len(bad)), random_state=20261112).to_csv(OUT / "c7_mismatch_sample.csv", index=False, encoding="utf-8-sig") \
        if len(bad) else pd.DataFrame().to_csv(OUT / "c7_mismatch_sample.csv", index=False)
    L = ["# C-7 매매·임대 연결 실측", "",
         md_table([
             ("연결 전체(전 → 후)", f"{len(before):,} → {len(after):,}"),
             ("분할 대상 매매 키의 연결(전)", f"{len(b_split):,}"),
             ("모든 조각 이어짐", f"{full:,}"), ("일부 조각만 이어짐", f"{part:,}"), ("끊김", f"{lost:,}"),
             ("분할 조각 연결(후)", f"{len(new_links):,}"),
             ("한 임대 키 → 여러 매매 키", f"{multi_r:,}"), ("한 매매 키 → 여러 임대 키", f"{multi_s:,}"),
             ("분할 아닌 연결 중 사라진 것", f"{lost_other:,}"),
             ("조각 연결 법정동8 불일치", f"{int((~m['emd_ok']).sum()):,}"),
             ("조각 연결 대표 지번 불일치", f"{int((~m['lot_ok']).sum()):,}"),
             ("C-2 보류 연결(판정 키·조각 키, 매매·임대 키 둘 다 있음)", f"{len(held):,} " + str(held_by)),
             ("C-2 보류 대상인데 연결된 것(0 이어야 함)", f"{leaked:,}"),
         ], ["항목", "값"]),
         "", "- 불일치 표본(최대 20, 지번 포함): logs/collective_p2/c7_mismatch_sample.csv"]
    (OUT / "c7_rent_links.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
