"""Phase C — 속성 행이 없는 키의 사유 (읽기 전용, 리허설 DB·표제부 사본).

1) 분할 새 키 중 202607 속성 행 없는 키 → 사유: K-apt 매칭 대상 아님(아파트 빌더 목록 밖) / 표제부 없음 /
   막힘(blocked: K-apt 우선 등) / 주거 아님·세대 없음 / 재건축 / 기타
2) 분할과 무관하게 202607 속성 행이 없는 키(빌더 목록 기준) → 유형별 건수 · 첫 거래가 202607 판 이후인지
title_fill 분류(classify)는 실제 단계와 같은 함수·같은 판·같은 표제부 사본으로 계산한다.
출력: 표준출력(markdown, 지번 없음) + logs/collective_p2/c17_empty_keys.csv(키·사유)
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
os.environ["PARCEL_MASTER_DATABASE_URL"] = base.set(database="parcel_master_p2r").render_as_string(hide_password=False)
os.environ["PGOPTIONS"] = "-c default_transaction_read_only=on"

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

CATS = ("blocked", "no_title", "no_housing", "no_households", "rebuild", "has_kapt", "keep_t", "fill")


def main():
    from parcel_master import apply_title_fill as tf
    from parcel_master.db_utils import get_collective_engine, get_parcel_engine

    coll, parcel = get_collective_engine(), get_parcel_engine()
    for e in (coll, parcel):
        with e.connect() as c:
            assert REHEARSAL_RE.match(c.execute(text("select current_database()")).scalar())
    with coll.connect() as c:
        km = pd.read_sql(text("SELECT old_key, new_key, asset_type, reason FROM collective_building_key_map"), c)
        have = pd.read_sql(text("SELECT building_key, asset_type FROM collective_building_attributes WHERE snapshot_ym=:y"),
                           c, params={"y": YM})
        kapt_pnus = {str(r[0]) for r in c.execute(text(tf.KAPT_PNU_SQL), {"ym": YM})}
        incheon = tf._incheon_current_to_old_bjd(c)
    with parcel.connect() as c:
        by_pnu = tf._title_by_pnu(c)
    split_new = set(km.loc[km["reason"].str.contains("split", na=False), "new_key"])
    have_keys = set(have["building_key"].str.strip())
    rows = []
    for kind in ("apartment", "rowhouse", "officetel"):
        with coll.connect() as c:
            b = tf.load_buildings(c, kind)
            at = pd.read_sql(text(tf.ATTR_SQL), c, params={"ym": YM, "asset_type": kind})
        merged = b.merge(at, on="building_key", how="left")
        merged["has_attr_row"] = merged["match_tier"].notna()
        cl = tf.classify(merged, by_pnu, kapt_pnus, kind=kind, skip_kapt=(kind == "apartment"), refresh_t=False,
                         current_to_old_bjd=incheon)
        cat_of: dict[str, str] = {}
        for cat in CATS:
            for rec in cl.get(cat, []):
                cat_of.setdefault(str(rec.get("building_key")), cat)
        listed = set(b["building_key"].astype(str).str.strip())
        missing = listed - have_keys
        for k in missing:
            rows.append({"building_key": k, "asset_type": kind, "split_new": k in split_new,
                         "title_category": cat_of.get(k, "unclassified")})
    # 분할 새 키인데 빌더 목록(load_buildings)에도 없는 키 = 그 유형 단지 목록 밖(분양권 등)
    listed_all = {r["building_key"] for r in rows} | have_keys
    for k in split_new - listed_all:
        at = km.loc[km["new_key"] == k, "asset_type"].iloc[0]
        rows.append({"building_key": k, "asset_type": at, "split_new": True, "title_category": "not_in_builder_list"})
    df = pd.DataFrame(rows)
    with coll.connect() as c:
        first = pd.read_sql(text("SELECT building_key, min(contract_date) AS d0 FROM collective_transactions "
                                 "WHERE is_valid AND building_key = ANY(:k) GROUP BY 1"), c,
                            params={"k": list(df["building_key"])})
    df = df.merge(first, on="building_key", how="left")
    df["first_tx_after_snapshot"] = pd.to_datetime(df["d0"]) >= "2026-07-01"

    def reason(r):
        if r["title_category"] == "not_in_builder_list":
            return "단지 목록 밖(그 유형 building_stats 없음)"
        if r["asset_type"] == "apartment":
            return {"blocked": "막힘(K-apt 우선, K-apt 매칭 실패)", "no_title": "K-apt 매칭 실패 + 표제부 없음"}.get(
                r["title_category"], f"K-apt 매칭 실패 + 표제부 {r['title_category']}")
        return {"no_title": "표제부 없음", "blocked": "막힘", "no_housing": "표제부 주거 아님",
                "no_households": "표제부 세대 없음", "rebuild": "재건축", "unclassified": "기타"}.get(r["title_category"], "기타")

    df["reason"] = df.apply(reason, axis=1)
    df.drop(columns=["d0"]).to_csv(OUT / "c17_empty_keys.csv", index=False, encoding="utf-8-sig")
    s = df[df["split_new"]]
    print(f"## 분할 새 키 중 {YM} 속성 행 없는 키: {len(s):,}\n")
    g = s.groupby(["asset_type", "reason"]).size().reset_index(name="키")
    print(g.to_string(index=False))
    o = df[~df["split_new"]]
    print(f"\n## 분할과 무관하게 {YM} 속성 행 없는 키: {len(o):,}\n")
    g2 = o.groupby(["asset_type", "first_tx_after_snapshot", "reason"]).size().reset_index(name="키")
    print(g2.to_string(index=False))


if __name__ == "__main__":
    main()
