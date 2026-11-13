"""집합 2단계 실제 반영(로컬 실제 DB) 전 — 속성·표제부·공시지가 단계가 「키 목록 밖」에 쓰는지 미리 센다(쓰기 없음).

리허설 `scripts/lab/collective_p2/c15_scope_dryrun.py` 의 실제 DB 판. 실제 실행과 같은 함수·같은 키 목록 제한으로 쓸 행을 계산한다.
  - K-apt:  attributes_rows → filter_new_attribute_rows(판의 기존 키 제외) → restrict_to_keys(목록) · builder_master 는 참조 단지 코드만
  - title_fill: classify → filter_fills_new_keys → filter_fills_to_keys(목록) (유형별 fill·blocked)
  - 사전 단계: dictionary_rows_for_keys(목록) — 목록 밖 행은 계산 대상에 들어가지 않음을 센다
  - 공시지가: _representative_pnus → restrict_candidates_to_keys(목록), 이미 행이 있는 키(추가 전용이라 건너뜀)
기대: 모든 「목록 밖」 = 0. 하나라도 있으면 종료 코드 1(실행하지 말 것).

가드(진짜 로컬 DB 이름):
  - 집합 DB 이름 = --collective-db(기본 collective_stats), 표제부 DB = --parcel-db(기본 parcel_master) 와 정확히 같아야 한다.
  - *_p2r(리허설) 이름은 거부한다(리허설은 c15 를 쓴다). 접속 호스트는 localhost·127.0.0.1·::1 만 허용(운영 접속 차단).
  - 모든 세션 PGOPTIONS default_transaction_read_only=on, 시작 때 SHOW 로 확인.
출력: 표준출력 JSON(건수만) + --outside-csv(목록 밖 키, 지번 없음, logs/ 에 둘 것)
예상 소요: 약 5~10분(K-apt 파일 읽기·표제부 PNU 적재가 대부분, 로컬 리허설 c15 실측 기반)

  python scripts/ops/collective_p2_local/scope_dryrun.py --keys-file logs/collective_p2/p2_split_new_keys.txt \
      --kapt-file "<raw>/K-apt…/20261002_단지_기본정보.xlsx" --snapshot-ym 202607
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PIPE = ROOT / "pipeline"
for p in (PIPE, PIPE / "collective"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

REHEARSAL_RE = re.compile(r"_p2r(_[a-z0-9]+)?$")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", None, ""}


def guard_url(url: str, expected_db: str) -> None:
    """실제 로컬 DB 이름·로컬 호스트만 허용. 어긋나면 SystemExit(값은 출력하지 않음)."""
    from sqlalchemy.engine import make_url

    u = make_url(url)
    if u.host not in LOCAL_HOSTS:
        raise SystemExit("로컬 호스트가 아님 — 중단(운영 접속 차단)")
    if REHEARSAL_RE.search(u.database or ""):
        raise SystemExit(f"리허설 DB({u.database}) — 이 도구는 실제 로컬 DB 용(리허설은 c15)")
    if u.database != expected_db:
        raise SystemExit(f"DB 이름이 {expected_db} 가 아님: {u.database}")


def outside(written: set[str], keys: set[str]) -> set[str]:
    return {k for k in written if k not in keys}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keys-file", type=Path, required=True)
    ap.add_argument("--kapt-file", type=Path, required=True)
    ap.add_argument("--snapshot-ym", required=True)
    ap.add_argument("--collective-db", default="collective_stats")
    ap.add_argument("--parcel-db", default="parcel_master")
    ap.add_argument("--outside-csv", type=Path, default=ROOT / "logs" / "collective_p2" / "scope_outside_local.csv")
    a = ap.parse_args(argv)

    os.environ["PGOPTIONS"] = "-c default_transaction_read_only=on"
    from parcel_master.db_utils import get_collective_engine, get_parcel_engine

    coll, parcel = get_collective_engine(), get_parcel_engine()
    guard_url(coll.url.render_as_string(hide_password=False), a.collective_db)
    guard_url(parcel.url.render_as_string(hide_password=False), a.parcel_db)

    import importlib.util

    import pandas as pd
    from sqlalchemy import text

    for e, want in ((coll, a.collective_db), (parcel, a.parcel_db)):
        with e.connect() as c:
            assert c.execute(text("SELECT current_database()")).scalar() == want
            if c.execute(text("SHOW default_transaction_read_only")).scalar() != "on":
                raise SystemExit("읽기 전용 세션이 아님 — 중단")

    spec = importlib.util.spec_from_file_location("bca", PIPE / "build_collective_building_attributes.py")
    bca = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bca)
    from collective import apply_danji_dictionary as dic
    from collective import import_assessed_land_price as ialp
    from parcel_master import apply_title_fill as tf

    keys = bca.load_keys_file(a.keys_file)
    ym = a.snapshot_ym
    out: dict = {"snapshot_ym": ym, "keys": len(keys)}
    rows_out: list[tuple[str, str, str]] = []

    # K-apt
    with coll.connect() as conn:
        region_map = bca.load_region_map(conn)
        buildings = bca.load_buildings(conn, "apartment")
    kapt = bca.attach_kapt_pnu(bca.load_kapt(region_map, a.kapt_file))
    attrs = bca.filter_new_attribute_rows(bca.attributes_rows(buildings, kapt, snapshot_ym=ym, asset_type="apartment"),
                                          bca.existing_attribute_keys(coll, ym, "apartment"))
    before = set(attrs["building_key"].astype(str))
    attrs = bca.restrict_to_keys(attrs, keys)
    wk = set(attrs["building_key"].astype(str))
    codes = bca.referenced_danji_codes(attrs)
    bm = bca.builder_master_for_codes(bca.builder_master_rows(kapt, ym), codes)
    with coll.connect() as conn:
        have = {str(r[0]) for r in conn.execute(text("SELECT danji_code FROM builder_master WHERE snapshot_ym=:y"), {"y": ym})}
    out["kapt"] = {"rows": len(attrs), "keys": len(wk), "outside": len(outside(wk, keys)),
                   "new_keys_before_list_filter": len(before), "builder_master_new": sum(1 for r in bm if str(r["danji_code"]) not in have)}
    rows_out += [("kapt", "apartment", k) for k in sorted(outside(wk, keys))]

    # title_fill (K-apt 단계를 먼저 돌린 상태를 흉내: K-apt 가 쓸 키는 has_attr_row)
    with coll.connect() as conn:
        kapt_pnus = {str(r[0]) for r in conn.execute(text(tf.KAPT_PNU_SQL), {"ym": ym})}
        incheon = tf._incheon_current_to_old_bjd(conn)
    with parcel.connect() as conn:
        by_pnu = tf._title_by_pnu(conn)
    out["title_fill"] = {}
    for kind in tf.DEFAULT_TYPES:
        with coll.connect() as conn:
            b = tf.load_buildings(conn, kind)
            at = pd.read_sql(text(tf.ATTR_SQL), conn, params={"ym": ym, "asset_type": kind})
        if kind == "apartment" and len(attrs):
            at = pd.concat([at, attrs[["building_key", "match_tier", "match_rule", "danji_code"]]], ignore_index=True)
        if at.empty:
            merged = b.assign(match_tier=None, danji_code=None, has_attr_row=False)
        else:
            merged = b.merge(at, on="building_key", how="left")
            merged["has_attr_row"] = merged["match_tier"].notna()
        cl = tf.classify(merged, by_pnu, kapt_pnus, kind=kind, skip_kapt=(kind == "apartment"), refresh_t=False,
                         current_to_old_bjd=incheon)
        fills = tf.filter_fills_to_keys(tf.filter_fills_new_keys(cl["fill"]), keys)
        fk = {str(f["building_key"]) for f in fills}
        out["title_fill"][kind] = {"fill": len(fills), "keys": len(fk), "outside": len(outside(fk, keys)),
                                   "blocked_all": len(cl["blocked"])}
        rows_out += [("title_fill", kind, k) for k in sorted(outside(fk, keys))]

    # 사전 단계: 계산 대상 행이 목록 키뿐인지
    with coll.connect() as conn:
        df = dic._load(conn, ym)
    sub = tf.dictionary_rows_for_keys(df, keys)
    dk = set(sub["building_key"].astype(str).str.strip())
    out["dictionary"] = {"rows_now_in_list": len(sub), "outside": len(outside(dk, keys)), "rows_in_snapshot": len(df)}

    # 공시지가(추가 전용)
    with coll.connect() as conn:
        cands = ialp.restrict_candidates_to_keys(ialp._representative_pnus(conn, ("apartment", "rowhouse", "officetel")), keys)
        have_lp = {(str(r[0]).strip(), r[1]) for r in conn.execute(text(
            "SELECT building_key, asset_type FROM collective_building_assessed_land_price"))}
    ck = {str(c["building_key"]).strip() for c in cands}
    out["land_price"] = {"candidates": len(cands), "outside": len(outside(ck, keys)),
                         "already_have_row(skip)": sum(1 for c in cands if (str(c["building_key"]).strip(), c["asset_type"]) in have_lp)}

    a.outside_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows_out, columns=["step", "asset_type", "building_key"]).to_csv(a.outside_csv, index=False)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    bad = out["kapt"]["outside"] + sum(v["outside"] for v in out["title_fill"].values()) + out["dictionary"]["outside"] \
        + out["land_price"]["outside"]
    print("목록 밖 쓰기 " + ("0 — 진행 가능" if bad == 0 else f"{bad} — 실행하지 말 것"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
