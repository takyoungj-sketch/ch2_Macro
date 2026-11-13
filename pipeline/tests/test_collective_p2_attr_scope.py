# -*- coding: utf-8 -*-
"""집합 2단계 Phase C (a) — 속성·표제부·공시지가를 분할 새 키 목록에만 쓰기.

- 키 목록 밖 키에 쓰기 0 (K-apt 속성 행·builder_master·title_fill fill)
- 사전 단계는 목록 키의 행만 갱신(기존 행 파생 칸 불변)
- 공시지가 추가 전용: 기존 값 불변, 목록 키만
- K-apt PNU 파일을 못 읽으면 실패
- 토지 DB 대체 조회는 리허설 모드에서 *_p2r 이름일 때만
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

PIPE = Path(__file__).resolve().parents[1]
for p in (PIPE, PIPE / "collective"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from collective import import_assessed_land_price as ialp  # noqa: E402
from collective import migrate_p2_keys as mig  # noqa: E402
from parcel_master import apply_title_fill as tf  # noqa: E402

DB = "ch2_attrscope_p2r"


def _bca():
    spec = importlib.util.spec_from_file_location("bca_scope", PIPE / "build_collective_building_attributes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def eng():
    try:
        base = make_url(mig.server_url_from_env())
        admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {DB}"))
            c.execute(text(f"CREATE DATABASE {DB}"))
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"로컬 PostgreSQL 임시 DB 생성 불가: {type(ex).__name__}")
    e = create_engine(base.set(database=DB))
    yield e
    e.dispose()
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)"))
    admin.dispose()


# ---- K-apt 속성 빌더 -------------------------------------------------------------------------

def test_kapt_rows_and_builder_master_limited_to_key_list():
    bca = _bca()
    attrs = pd.DataFrame({
        "building_key": ["NEW1", "NEW2", "OLD9"],
        "danji_code": ["A1", None, "C3"],
        "match_danji_codes": ["A1,B2", None, "C3"],
    })
    keep = bca.restrict_to_keys(attrs, {"NEW1", "NEW2"})
    assert set(keep["building_key"]) == {"NEW1", "NEW2"}            # 목록 밖(OLD9) 0
    codes = bca.referenced_danji_codes(keep)
    assert codes == {"A1", "B2"}                                    # OLD9 의 C3 는 빠짐
    bm = [{"danji_code": c} for c in ("A1", "B2", "C3", "D4")]
    assert [r["danji_code"] for r in bca.builder_master_for_codes(bm, codes)] == ["A1", "B2"]


def test_kapt_pnu_missing_file_fails(monkeypatch):
    bca = _bca()
    import parcel_master.load_kapt_pnu as lkp

    def _boom():
        raise FileNotFoundError("단지_필지고유번호 xlsx 없음")

    monkeypatch.setattr(lkp, "load_pnu_map", _boom)
    with pytest.raises(RuntimeError, match="PNU"):
        bca.attach_kapt_pnu(pd.DataFrame({"단지코드": ["A1"]}))
    monkeypatch.setattr(lkp, "load_pnu_map", lambda: pd.DataFrame({"danji_code": ["ZZ"], "pnu": ["1"]}))
    with pytest.raises(RuntimeError, match="하나도"):
        bca.attach_kapt_pnu(pd.DataFrame({"단지코드": ["A1"]}))   # 붙은 행 0 도 실패


def test_kapt_keys_file_needs_snapshot_and_new_keys_only(monkeypatch, tmp_path):
    bca = _bca()
    kf = tmp_path / "k.txt"
    kf.write_text("NEW1\n", encoding="utf-8")
    for argv in (["x", "--keys-file", str(kf), "--snapshot-ym", "202607"],                         # new-keys-only 없음
                 ["x", "--keys-file", str(kf), "--new-keys-only"],                                 # 판 없음
                 ["x", "--keys-file", str(kf), "--new-keys-only", "--snapshot-ym", "202607", "--replace"]):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit):
            bca.main()
    (tmp_path / "e.txt").write_text("# 주석만\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        bca.load_keys_file(tmp_path / "e.txt")


# ---- title_fill ------------------------------------------------------------------------------

def test_title_fill_fills_only_listed_keys_and_requires_snapshot():
    fills = [{"building_key": k, "has_attr_row": False} for k in ("NEW1", "OLD9", "NEW2")]
    assert [f["building_key"] for f in tf.filter_fills_to_keys(tf.filter_fills_new_keys(fills), {"NEW1", "NEW2"})] \
        == ["NEW1", "NEW2"]
    for kw in ({"keys": {"NEW1"}, "new_keys_only": True},                       # 판 없음 → 최신 판으로 가는 경로 차단
               {"keys": {"NEW1"}, "snapshot_ym": "202607"},                      # new_keys_only 없음
               {"keys": set(), "new_keys_only": True, "snapshot_ym": "202607"}):  # 빈 목록
        with pytest.raises(SystemExit):
            tf.run(**kw)


def test_dictionary_updates_only_listed_rows(eng):
    from collective.apply_danji_dictionary import _write

    with eng.begin() as c:
        c.execute(text("""CREATE TABLE collective_building_attributes (building_key char(64), snapshot_ym char(6),
            asset_type text, builder_norm varchar(200), builder_group varchar(200), builder_is_joint bool,
            builder_is_public bool, brand varchar(80), brand_is_public bool, brand_confidence varchar(10),
            attr_quality_flags varchar(120), dictionary_version varchar(20))"""))
        c.execute(text("""INSERT INTO collective_building_attributes VALUES
            ('OLD9','202607','apartment','옛값','옛그룹',false,false,'옛브랜드',false,'low','old_flag','v0'),
            ('NEW1','202607','rowhouse',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)"""))
    derived_all = pd.DataFrame([
        {"building_key": "OLD9", "snapshot_ym": "202607", "builder_norm": "새값", "builder_group": "새그룹",
         "builder_is_joint": True, "builder_is_public": True, "brand": "새브랜드", "brand_is_public": True,
         "brand_confidence": "high", "attr_quality_flags": "new_flag", "dictionary_version": "v9"},
        {"building_key": "NEW1", "snapshot_ym": "202607", "builder_norm": "가", "builder_group": "가",
         "builder_is_joint": False, "builder_is_public": False, "brand": None, "brand_is_public": False,
         "brand_confidence": None, "attr_quality_flags": None, "dictionary_version": "v9"},
    ])
    only = tf.dictionary_rows_for_keys(derived_all, {"NEW1"})
    with eng.begin() as c:
        _write(c, only)
    with eng.connect() as c:
        old = c.execute(text("SELECT builder_norm, attr_quality_flags, dictionary_version FROM collective_building_attributes "
                             "WHERE building_key='OLD9'")).one()
        new = c.execute(text("SELECT builder_norm, dictionary_version FROM collective_building_attributes "
                             "WHERE building_key='NEW1'")).one()
    assert tuple(old) == ("옛값", "old_flag", "v0")       # 기존 행 파생 칸 불변
    assert tuple(new) == ("가", "v9")


# ---- 공시지가 --------------------------------------------------------------------------------

def test_land_price_insert_only_keeps_existing_and_list_only(eng):
    with eng.begin() as c:
        c.execute(text("""CREATE TABLE collective_building_assessed_land_price (building_key text, asset_type text,
            representative_pnu text, assessed_land_price numeric, assessed_land_price_year int, source text,
            loaded_at timestamptz DEFAULT now(), PRIMARY KEY (building_key, asset_type))"""))
        c.execute(text("""INSERT INTO collective_building_assessed_land_price
            (building_key, asset_type, representative_pnu, assessed_land_price, assessed_land_price_year, source)
            VALUES ('OLD9','apartment','1',100,2025,'land_trait_slim')"""))
    cands = [{"building_key": k, "asset_type": "apartment", "pnu": p} for k, p in (("OLD9", "1"), ("NEW1", "2"))]
    cands = ialp.restrict_candidates_to_keys(cands, {"NEW1", "OLD9"})
    src = pd.DataFrame({"pnu": ["1", "2"], "assessed_land_price": [999, 500], "assessed_land_price_year": [2026, 2026]})
    ialp.load(eng, src, ("apartment",), candidates=cands, source_label="land_trait_slim", insert_only=True)
    with eng.connect() as c:
        rows = dict(c.execute(text("SELECT building_key, assessed_land_price FROM collective_building_assessed_land_price")).all())
    assert float(rows["OLD9"]) == 100.0      # 기존 값 불변(옛 upsert 였다면 999)
    assert float(rows["NEW1"]) == 500.0
    assert ialp.restrict_candidates_to_keys(cands, {"NEW1"}) == [cands[1]]


def test_land_db_fallback_guarded_in_rehearsal(monkeypatch):
    class _E:
        url = make_url("postgresql+psycopg2://u:p@localhost:5432/land_stats")

        def connect(self):
            raise AssertionError("리허설 모드에서 진짜 토지 DB 에 접속하면 안 됨")

    class _Coll:
        def connect(self):
            class _C:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False
            return _C()

    monkeypatch.setattr(ialp, "_reform_bjd_maps", lambda conn: ({}, {}))
    monkeypatch.setattr(ialp, "get_land_engine_for_region_copy", lambda: _E())
    monkeypatch.setitem(ialp._REHEARSAL, "on", True)
    with pytest.raises(SystemExit, match="리허설"):
        ialp._load_reform_bjd_maps(_Coll())
