# -*- coding: utf-8 -*-
"""집합 2단계 P4 — C-2 분할 아파트 조각 표시 이름 「단지명 (YYYY년 준공)」."""
from __future__ import annotations

from app.collective import display_label as dl
from app.collective.building_stats_query import _stats_row_from_parts
from app.collective.key_remap import KeyMapCache
from app.collective.schemas import AnalysisFeatures
from app.collective.transaction_export import transactions_csv_bytes

BASE, FRAG, C01_OLD, C01_NEW, OTHER = "b" * 64, "f" * 64, "o" * 64, "n" * 64, "x" * 64
MAP = {"collective": {
    BASE: [(FRAG, 1, 30, "c2")],                     # C-2: 본 조각(옛 키)·조각(새 키)
    C01_OLD: [(C01_NEW, 1, 10, "")],                 # C-01 만 — 라벨 대상 아님
}}


def _cache(m=MAP):
    return KeyMapCache(loader=lambda name: m.get(name, {}), ttl=0)


def test_fragment_keys_from_c2_rows_only():
    assert dl.c2_fragment_keys(_cache()) == {BASE, FRAG}
    assert dl.c2_fragment_keys(_cache({})) == frozenset()


def test_label_only_for_apartment_fragments_with_year():
    ks = frozenset({BASE, FRAG})
    assert dl.c2_label(FRAG, "주공", "apartment", 1986, keys=ks) == "주공 (1986년 준공)"
    assert dl.c2_label(BASE, "주공", "apartment", 2009.0, keys=ks) == "주공 (2009년 준공)"
    assert dl.c2_label(OTHER, "주공", "apartment", 1986, keys=ks) is None          # 조각 아님
    assert dl.c2_label(FRAG, "빌라", "rowhouse", 2015, keys=ks) is None            # 아파트만
    assert dl.c2_label(FRAG, "주공", "apartment", None, keys=ks) is None           # 연도 없음 → 이름 그대로
    assert dl.c2_label(FRAG, "", "apartment", 1986, keys=ks) is None


def test_list_row_keeps_display_name_and_adds_label(monkeypatch):
    monkeypatch.setattr(dl, "CACHE", _cache())
    base = dict(addr3="소사구", addr4="소사본동", addr5=None, lot_number="1", road_name="", display_name="주공",
                asset_type="apartment", building_year=1986, count=40, mean=1.0, median=1.0, ci_lower=None, ci_upper=None)
    row = _stats_row_from_parts({**base, "building_key": FRAG}, asset_type="apartment", gates=AnalysisFeatures())
    assert row.display_name == "주공" and row.display_label == "주공 (1986년 준공)"
    row = _stats_row_from_parts({**base, "building_key": OTHER}, asset_type="apartment", gates=AnalysisFeatures())
    assert row.display_name == "주공" and row.display_label is None
    assert "display_label" in row.model_dump()


def test_csv_building_column_uses_label():
    rows = [{"building_key": FRAG, "display_name": "주공", "contract_date": "2024-01-02", "price": 1},
            {"building_key": OTHER, "display_name": "래미안", "contract_date": "2024-01-03", "price": 2}]
    body = transactions_csv_bytes(rows, asset_type="apartment", include_building=True,
                                  labels={FRAG: "주공 (1986년 준공)"}).decode("utf-8")
    lines = body.lstrip("﻿").splitlines()
    assert lines[1].startswith("주공 (1986년 준공),") and lines[2].startswith("래미안,")
    # 단지 칸이 없는 내보내기는 그대로
    assert transactions_csv_bytes(rows, asset_type="apartment").decode("utf-8") == \
        transactions_csv_bytes(rows, asset_type="apartment", labels={FRAG: "x"}).decode("utf-8")


def test_labels_for_keys_queries_only_fragment_keys():
    calls = []

    class _Res:
        def mappings(self):
            return self

        def all(self):
            return [{"building_key": FRAG, "display_name": "주공", "asset_type": "apartment", "building_year": 1986}]

    class _Conn:
        def execute(self, stmt, params=None):
            calls.append(params)
            return _Res()

    ks = frozenset({BASE, FRAG})
    assert dl.c2_labels_for_keys(_Conn(), [OTHER], keys=ks) == {} and calls == []      # 조각 키가 없으면 조회하지 않음
    assert dl.c2_labels_for_keys(_Conn(), [FRAG, OTHER], keys=ks) == {FRAG: "주공 (1986년 준공)"}
    assert calls == [{"k": [FRAG]}]
