"""Phase C — K-apt 속성·title_fill 을 202607 판 · 새 키만으로 돌리기 전, 쓸 키를 미리 센다(쓰기 없음).

T 결정(2026-11-13): 두 단계 다 `--snapshot-ym 202607 --new-keys-only`. 분할 새 키 3,447개 밖에 쓰면 멈춤.
빌더·title_fill 의 같은 함수로 「쓸 행」을 계산만 한다(DB 는 읽기 전용 세션).
- K-apt: attributes_rows → filter_new_attribute_rows(202607 기존 키 제외) → 쓸 키, builder_master 새 danji 수
- title_fill: classify → filter_fills_new_keys → 쓸 키 (유형별), 그리고 사전(dictionary) 단계가 기존 행 파생 칸을
  바꾸는지(현재 202607 행으로 _derive 한 값 = 저장된 값?)
출력: 표준출력 JSON + logs/collective_p2/c15_scope_outside.csv(분할 새 키 밖 쓸 키, 지번 없음)
"""
from __future__ import annotations

import json
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
KAPT = Path(r"D:\ch2\ch2_Macro\raw\raw addition\K-apt공동주택관리정보시스템\20261002_단지_기본정보.xlsx")
OUT = ROOT / "logs" / "collective_p2"
base = make_url(server_url_from_env())
os.environ["COLLECTIVE_DATABASE_URL"] = base.set(database="collective_stats_p2r").render_as_string(hide_password=False)
os.environ["PARCEL_MASTER_DATABASE_URL"] = base.set(database="parcel_master_p2r").render_as_string(hide_password=False)
os.environ["PGOPTIONS"] = "-c default_transaction_read_only=on"   # 이 분석의 모든 세션 읽기 전용

import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402


def main():
    import importlib.util

    spec = importlib.util.spec_from_file_location("bca", PIPE / "build_collective_building_attributes.py")
    bca = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bca)
    from collective import apply_danji_dictionary as dic
    from parcel_master import apply_title_fill as tf
    from parcel_master.db_utils import get_collective_engine, get_parcel_engine

    coll, parcel = get_collective_engine(), get_parcel_engine()
    for e in (coll, parcel):
        with e.connect() as c:
            db = c.execute(text("select current_database()")).scalar()
            assert REHEARSAL_RE.match(db), db
            assert c.execute(text("show default_transaction_read_only")).scalar() == "on"
    with coll.connect() as c:
        km = pd.read_sql(text("SELECT old_key, new_key, asset_type, reason FROM collective_building_key_map"), c)
    split_new = set(km.loc[km["reason"].str.contains("split", na=False), "new_key"])
    out: dict = {"snapshot_ym": YM, "split_new_keys": len(split_new)}
    outside = []

    # K-apt (아파트)
    eng = create_engine(bca.db_url(), pool_pre_ping=True)
    with eng.connect() as conn:
        region_map = bca.load_region_map(conn)
        buildings = bca.load_buildings(conn, "apartment")
    kapt = bca.attach_kapt_pnu(bca.load_kapt(region_map, KAPT))
    attrs = bca.attributes_rows(buildings, kapt, snapshot_ym=YM, asset_type="apartment")
    existed = bca.existing_attribute_keys(eng, YM, "apartment")
    attrs = bca.filter_new_attribute_rows(attrs, existed)
    keys = set(attrs["building_key"].astype(str))
    out["kapt"] = {"rows": len(attrs), "keys": len(keys), "in_split_new": len(keys & split_new),
                   "outside": len(keys - split_new),
                   "by_tier": attrs.groupby("match_tier", dropna=False).size().to_dict() if len(attrs) else {}}
    outside += [("kapt", "apartment", k) for k in sorted(keys - split_new)]
    bm = bca.builder_master_rows(kapt, YM)
    with eng.connect() as conn:
        have = {str(r[0]) for r in conn.execute(text("SELECT danji_code FROM builder_master WHERE snapshot_ym=:y"), {"y": YM})}
    out["kapt"]["builder_master_new_danji"] = sum(1 for r in bm if str(r["danji_code"]) not in have)
    out["kapt"]["builder_master_rows_total"] = len(bm)

    # title_fill (K-apt 단계를 먼저 돌린 뒤의 상태를 흉내: K-apt 가 쓸 키는 has_attr_row 로 본다)
    with coll.connect() as conn:
        kapt_pnus = {str(r[0]) for r in conn.execute(text(tf.KAPT_PNU_SQL), {"ym": YM})}
        incheon = tf._incheon_current_to_old_bjd(conn)
    with parcel.connect() as conn:
        by_pnu = tf._title_by_pnu(conn)
    out["title_fill"] = {"kapt_pnus": len(kapt_pnus), "title_pnu": len(by_pnu)}
    for kind in tf.DEFAULT_TYPES:
        with coll.connect() as conn:
            b = tf.load_buildings(conn, kind)
            at = pd.read_sql(text(tf.ATTR_SQL), conn, params={"ym": YM, "asset_type": kind})
        if kind == "apartment" and len(attrs):
            at = pd.concat([at, attrs[["building_key", "match_tier", "match_rule", "danji_code"]]], ignore_index=True)
        if at.empty:
            merged = b.copy()
            merged["match_tier"] = None
            merged["danji_code"] = None
            merged["has_attr_row"] = False
        else:
            merged = b.merge(at, on="building_key", how="left")
            merged["has_attr_row"] = merged["match_tier"].notna()
        cl = tf.classify(merged, by_pnu, kapt_pnus, kind=kind, skip_kapt=(kind == "apartment"), refresh_t=False,
                         current_to_old_bjd=incheon)
        fills = tf.filter_fills_new_keys(cl["fill"])
        fk = {str(f["building_key"]) for f in fills}
        out["title_fill"][kind] = {"fill_rows": len(fills), "keys": len(fk), "in_split_new": len(fk & split_new),
                                   "outside": len(fk - split_new), "blocked": len(cl["blocked"]),
                                   "no_title": len(cl["no_title"])}
        outside += [("title_fill", kind, k) for k in sorted(fk - split_new)]

    # 사전 단계: 지금 202607 행으로 파생 칸을 다시 계산하면 저장값과 같은가(기존 키만)
    with coll.connect() as conn:
        df = dic._load(conn, YM)
        names = dic._load_display_names(conn, df["building_key"].astype(str).tolist())
        cur = pd.read_sql(text("SELECT * FROM collective_building_attributes WHERE snapshot_ym=:y"), conn, params={"y": YM})
    der = dic._derive(df, names)
    cols = ["builder_norm", "builder_group", "builder_is_joint", "builder_is_public", "brand", "brand_is_public",
            "brand_confidence", "attr_quality_flags", "dictionary_version"]
    mm = der[["building_key", "asset_type", *cols]].merge(cur[["building_key", "asset_type", *cols]],
                                                         on=["building_key", "asset_type"], suffixes=("_d", "_s"))
    diff = {}
    for c in cols:
        d = ~((mm[f"{c}_d"].isna() & mm[f"{c}_s"].isna()) | (mm[f"{c}_d"].astype(str) == mm[f"{c}_s"].astype(str)))
        if d.any():
            diff[c] = int(d.sum())
    out["dictionary_recompute_diff_on_existing"] = diff
    pd.DataFrame(outside, columns=["step", "asset_type", "building_key"]).to_csv(OUT / "c15_scope_outside.csv", index=False)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
