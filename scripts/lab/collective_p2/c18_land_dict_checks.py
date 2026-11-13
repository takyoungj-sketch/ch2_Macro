"""Phase C — (1) 분할 새 키 공시지가 빈 키 사유 (2) 사전 단계 「목록만 계산 = 전체 계산」 실측. 읽기 전용.

(1) 공시지가 표에 행이 없는 분할 새 키를 나눈다:
    대표 필지 후보 밖(유형 밖·그 유형 building_stats 없음·대표 지번/법정동 없음) / 후보인데 원천에서 못 찾음
    (slim 에 없음·값 갈림·최신 연도 아님) / 기타
(2) collective_building_attributes 202607 전체로 _derive 한 결과와, 목록 키만 걸러 _derive 한 결과를
    목록 키에 대해 칸마다 비교(builder_norm·attr_quality_flags 포함). 리허설 DB 의 지금 저장값과도 비교.
출력: 표준출력(markdown, 지번 없음)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PIPE = ROOT / "pipeline"
for p in (PIPE, PIPE / "collective"):
    sys.path.insert(0, str(p))
from sqlalchemy.engine import make_url  # noqa: E402

from collective.migrate_p2_keys import REHEARSAL_RE, server_url_from_env  # noqa: E402

YM = "202607"
OUT = ROOT / "logs" / "collective_p2"
base = make_url(server_url_from_env())
os.environ["COLLECTIVE_DATABASE_URL"] = base.set(database="collective_stats_p2r").render_as_string(hide_password=False)
os.environ["PGOPTIONS"] = "-c default_transaction_read_only=on"

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

COLS = ["builder_norm", "builder_group", "builder_is_joint", "builder_is_public", "brand", "brand_is_public",
        "brand_confidence", "attr_quality_flags", "dictionary_version"]


def _same(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a.isna() & b.isna()) | (a.astype(str) == b.astype(str))


def main():
    from collective import apply_danji_dictionary as dic
    from collective import import_assessed_land_price as ialp
    from collective.db_utils import get_collective_engine

    eng = get_collective_engine()
    with eng.connect() as c:
        assert REHEARSAL_RE.match(c.execute(text("select current_database()")).scalar())
        km = pd.read_sql(text("SELECT old_key, new_key, asset_type, reason FROM collective_building_key_map"), c)
        lp = pd.read_sql(text("SELECT building_key, asset_type FROM collective_building_assessed_land_price"), c)
        bs = pd.read_sql(text("SELECT DISTINCT building_key, asset_type FROM collective_building_stats"), c)
        cands = ialp._representative_pnus(c, ("apartment", "rowhouse", "officetel"))
    split = km[km["reason"].str.contains("split", na=False)][["new_key", "asset_type"]].drop_duplicates()
    split.columns = ["building_key", "asset_type"]
    have = set(zip(lp["building_key"].str.strip(), lp["asset_type"]))
    miss = split[[ (k, a) not in have for k, a in zip(split["building_key"], split["asset_type"])]].copy()
    cand_keys = {(str(r["building_key"]).strip(), r["asset_type"]) for r in cands}
    in_bs = set(zip(bs["building_key"].str.strip(), bs["asset_type"]))

    def why(r):
        k = (r["building_key"], r["asset_type"])
        if r["asset_type"] not in ("apartment", "rowhouse", "officetel"):
            return f"유형 밖({r['asset_type']}, 공시지가 단계 대상 아님)"
        if k not in in_bs:
            return "그 유형 building_stats 없음"
        if k not in cand_keys:
            return "대표 필지 후보 아님(대표 지번·법정동으로 PNU 못 만듦)"
        return "후보인데 원천 slim 에서 못 씀(없음·값 갈림·최신 연도 아님)"

    miss["reason"] = miss.apply(why, axis=1)
    print(f"## 분할 새 키 공시지가 없음: {len(miss):,} / {len(split):,}\n")
    print(miss.groupby(["asset_type", "reason"]).size().reset_index(name="키").to_string(index=False))

    with eng.connect() as c:
        df = dic._load(c, YM)
        names = dic._load_display_names(c, df["building_key"].astype(str).tolist())
        stored = pd.read_sql(text(f"SELECT building_key, asset_type, {', '.join(COLS)} FROM collective_building_attributes "
                                  "WHERE snapshot_ym = :y"), c, params={"y": YM})
    keys = set(split["building_key"])
    full = dic._derive(df, names)
    from parcel_master.apply_title_fill import dictionary_rows_for_keys

    sub_df = dictionary_rows_for_keys(df, keys)
    part = dic._derive(sub_df, {k: v for k, v in names.items() if k in keys})
    k2 = ["building_key", "asset_type"]
    f = full[full["building_key"].astype(str).str.strip().isin(keys)][k2 + COLS]
    m = f.merge(part[k2 + COLS], on=k2, suffixes=("_full", "_part"))
    s = m.merge(stored[k2 + COLS].rename(columns={c: f"{c}_stored" for c in COLS}), on=k2)
    rows = []
    for c in COLS:
        rows.append((c, len(m), int((~_same(m[f"{c}_full"], m[f"{c}_part"])).sum()),
                     int((~_same(s[f"{c}_full"], s[f"{c}_stored"])).sum())))
    print(f"\n## 사전 단계: 목록 키 {len(m):,}행 — 목록만 계산 vs 전체 계산, 전체 계산 vs 저장값\n")
    print("| 칸 | 행 | 목록만≠전체 | 전체≠저장 |\n|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(f"{v:,}" if isinstance(v, int) else str(v) for v in r) + " |")


if __name__ == "__main__":
    main()
