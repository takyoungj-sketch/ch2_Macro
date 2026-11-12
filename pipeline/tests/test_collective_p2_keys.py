# -*- coding: utf-8 -*-
"""집합 2단계 Phase B — 키 규칙·분할·행정명 정규화·가드 단위 테스트(DB 없음)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest

PIPE = Path(__file__).resolve().parents[1]
for p in (PIPE, PIPE / "collective"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from admin_names import canonical_sido_name, normalize_addr1_column  # noqa: E402
from collective import building_keys as bk  # noqa: E402
from collective.migrate_p2_keys import GuardError, assert_rehearsal_db, compute_new_keys  # noqa: E402
from collective.rep_address_sql import rep_address_query  # noqa: E402


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


ROWS = [
    # 이름 있는 단지
    dict(asset="apartment", addr1="충청북도", addr2="청주시", addr3="청원구", addr4="우암동", building_name="삼일",
         lot_number="1-1", road_name="공항로", raw="apartment|충청북도|청주시|청원구|name:삼일"),
    # 이름 없는 연립
    dict(asset="rowhouse", addr1="경기도", addr2="부천시", addr3="원미구", addr4="춘의동", building_name="",
         lot_number="12-3", road_name="부일로", raw="rowhouse|경기도|부천시|원미구|춘의동|12-3|부일로"),
    # 분양권: 이름 정규화(공백 제거·IPARK 별칭)
    dict(asset="presale", addr1="충청북도", addr2="청주시", addr3="흥덕구", addr4="가경동",
         building_name="청주 가경 IPARK 4단지", lot_number="", road_name="",
         raw="presale|충청북도|청주시|흥덕구|name:청주가경아이파크4단지"),
]


@pytest.mark.parametrize("r", ROWS, ids=[r["asset"] for r in ROWS])
def test_unaffected_keys_are_bit_identical(r):
    """분할 목록 밖 키는 이전 규칙 문자열 그대로(1비트도 바뀌지 않음)."""
    df = pd.DataFrame([{k: v for k, v in r.items() if k not in ("asset", "raw")}])
    out = bk.attach_building_identity(df, r["asset"])
    assert out["building_key"].iloc[0] == _sha(r["raw"])
    assert bk.building_key_raw_series(df, r["asset"]).iloc[0] == r["raw"]
    derived = bk.derive_building_key(asset_type=r["asset"], addr1=r["addr1"], addr2=r["addr2"], addr3=r["addr3"],
                                     addr4=r["addr4"], building_name=r["building_name"], lot_number=r["lot_number"],
                                     road_name=r["road_name"])
    assert derived == _sha(r["raw"])
    # 분할 목록이 있어도 목록 밖이면 그대로
    out2 = bk.apply_building_key_split(out.assign(beopjungri_code="4311425036"), r["asset"],
                                       split_units={"deadbeef" * 8: ({"43114250": "43114250"}, "43114250")})
    assert out2["building_key"].iloc[0] == _sha(r["raw"])


def test_split_key_suffix_and_unit_resolution():
    r = ROWS[0]
    base = _sha(r["raw"])
    units = {base: ({"43114250": "43114250", "43114310": "43114310", "43114999": "43114310"}, "43114250")}
    df = pd.DataFrame([{**{k: v for k, v in r.items() if k not in ("asset", "raw")}, "beopjungri_code": c}
                       for c in ("4311425036", "4311431021", "4311499900", None, "4311488800")])
    df = bk.attach_building_identity(df, "apartment")
    out = bk.apply_building_key_split(df, "apartment", split_units=units)
    exp = [_sha(r["raw"] + "|emd:" + u) for u in ("43114250", "43114310", "43114310", "43114250", "43114888")]
    assert out["building_key"].tolist() == exp
    # 코드 변형(43114999)은 같은 조각, 코드 없음은 1조각, 처음 보는 동은 그 동 자체
    assert len(set(out["building_key"])) == 3


def test_split_skips_rows_whose_raw_does_not_reproduce_key():
    r = ROWS[0]
    base = _sha(r["raw"])
    df = pd.DataFrame([{**{k: v for k, v in r.items() if k not in ("asset", "raw")}, "beopjungri_code": "4311425036",
                        "building_key": base}])
    df.loc[0, "addr2"] = "다른시"  # 원문이 키를 재현하지 못함
    out = bk.apply_building_key_split(df, "apartment", split_units={base: ({}, "43114250")})
    assert out["building_key"].iloc[0] == base


def test_frozen_split_list_shape():
    units = bk.load_split_units(str(bk.SPLIT_UNITS_PATH))
    df = pd.read_csv(bk.SPLIT_UNITS_PATH, dtype=str)
    assert set(df["decision"]) <= {"split", "keep"}
    assert len(units) == df.loc[df.decision == "split", "base_key"].nunique()
    assert all(len(k) == 64 for k in units)
    # 같은 키의 조각 대표 법정동8 은 조각마다 다르다(새 키 충돌 없음)
    sp = df[df.decision == "split"].drop_duplicates(["base_key", "part"])
    assert not sp.duplicated(["base_key", "unit_emd8"]).any()
    assert (sp.groupby("base_key")["part"].nunique() >= 2).all()
    # 지번 칸이 없다(gitignore 밖 커밋 파일)
    assert list(df.columns) == ["base_key", "asset_type", "emd8", "unit_emd8", "part", "decision", "reason"]


def test_split_disable_env(monkeypatch):
    monkeypatch.setenv("CH2_COLLECTIVE_KEY_SPLIT", "0")
    bk.load_split_units.cache_clear()
    try:
        assert bk.load_split_units(str(bk.SPLIT_UNITS_PATH)) == {}
    finally:
        monkeypatch.delenv("CH2_COLLECTIVE_KEY_SPLIT")
        bk.load_split_units.cache_clear()


def test_admin_names_canonical_sido():
    assert canonical_sido_name("광주광역시") == "전남광주통합특별시"
    assert canonical_sido_name(" 전라남도") == "전남광주통합특별시"
    assert canonical_sido_name("전북특별자치도") == "전북특별자치도"
    assert canonical_sido_name(None) is None
    df = pd.DataFrame({"addr1": ["광주광역시", "서울특별시", None]})
    got = normalize_addr1_column(df)["addr1"].tolist()
    assert got[:2] == ["전남광주통합특별시", "서울특별시"]
    assert got[2] is None or got[2] != got[2]  # 결측은 결측 그대로(pandas 문자열 dtype은 NaN)


def test_refine_built_parser_normalizes_addr1():
    from built.refine_built import parse_sigungu_to_addr

    out = parse_sigungu_to_addr(pd.Series(["전라남도 순천시 조례동", "광주광역시 광산구 수완동"]))
    assert out["addr1"].tolist() == ["전남광주통합특별시", "전남광주통합특별시"]


def test_compute_new_keys_honam_then_split():
    """호남 표준화 키가 분할 목록에 있으면 두 사유가 같이 붙는다. 표준화만이면 honam_sido."""
    a = dict(id=1, asset_type="apartment", addr1="광주광역시", addr2="광산구", addr3="수완동", addr4=None,
             building_name="자이", lot_number="1", road_name="", beopjungri_code="1233010100")
    raw_old = "apartment|광주광역시|광산구|수완동|name:자이"
    raw_new = "apartment|전남광주통합특별시|광산구|수완동|name:자이"
    df = pd.DataFrame([{**a, "building_key": _sha(raw_old)}, {**a, "id": 2, "building_key": _sha(raw_old)}])
    out = compute_new_keys(df, {}, {})
    assert out["new_key"].tolist() == [_sha(raw_new)] * 2
    assert set(out["reason"]) == {"honam_sido"}
    units = {_sha(raw_new): ({"12330101": "12330101"}, "12330101")}
    out2 = compute_new_keys(df, units, {(_sha(raw_new), "12330101"): 1})
    assert out2["new_key"].iloc[0] == _sha(raw_new + "|emd:12330101")
    assert out2["reason"].iloc[0] == "honam_sido+split"
    assert int(out2["split_part"].iloc[0]) == 1


class _FakeConn:
    def __init__(self, name):
        self.name = name

    def execute(self, *_a, **_k):
        class R:
            def __init__(s, v):
                s.v = v

            def scalar(s):
                return s.v

        return R(self.name)


@pytest.mark.parametrize("cur,expected,ok", [
    ("collective_stats_p2r", "collective_stats_p2r", True),
    ("ch2_p2r_fixture", "ch2_p2r_fixture", True),
    ("collective_stats", "collective_stats", False),       # 실제 로컬 DB
    ("collective_stats_p2r", "rent_stats_p2r", False),      # 다른 DB에 붙음
    ("collective_stats_p2rx", "collective_stats_p2rx", False),
    ("rent_stats", "rent_stats", False),
])
def test_rehearsal_guard(cur, expected, ok):
    if ok:
        assert assert_rehearsal_db(_FakeConn(cur), expected) == cur
    else:
        with pytest.raises(GuardError):
            assert_rehearsal_db(_FakeConn(cur), expected)


def test_rep_address_query_shape():
    sql = rep_address_query(base_sql="SELECT * FROM t WHERE x {addr1_clause}", group_cols=["building_key", "asset_type"],
                            aggregates="array_agg(b.unit_price) AS prices")
    assert "DISTINCT ON (building_key, asset_type)" in sql
    assert "_n DESC, _d DESC NULLS LAST, beopjungri_code NULLS LAST, lot_number NULLS LAST" in sql
    assert "{addr1_clause}" in sql  # 빌더의 .format 자리 표시 보존
    assert "MAX(addr4)" not in sql
