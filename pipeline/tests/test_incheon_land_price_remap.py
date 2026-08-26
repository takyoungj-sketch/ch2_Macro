"""인천 분구 PNU 조인 — 공부 구코드로 조회한 뒤 신 PNU로 되돌린다."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collective.import_assessed_land_price import load
from parcel_master.pnu import remap_pnu_bjd


def test_load_joins_old_pnu_and_stores_current():
    current = "2829010300100140001"
    old = remap_pnu_bjd(current, {"2829010300": "2826011300"})
    assert old == "2826011300100140001"
    source = pd.DataFrame(
        [
            {
                "pnu": old,
                "assessed_land_price": 1230000.0,
                "assessed_land_price_year": 2026,
            }
        ]
    )
    captured: list[list[dict]] = []

    class _Conn:
        def execute(self, _sql, records):
            captured.append(records)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class _Engine:
        def begin(self):
            return _Conn()

    n_cand, n_loaded = load(
        _Engine(),
        source,
        ("apartment",),
        candidates=[
            {
                "building_key": "apt|인천광역시 검단구|마전동|1|name:테스트",
                "asset_type": "apartment",
                "pnu": current,
            }
        ],
        source_label="parcel_land_price",
        current_to_old_bjd={"2829010300": "2826011300"},
    )
    assert n_cand == 1
    assert n_loaded == 1
    row = captured[0][0]
    assert row["pnu"] == current
    assert row["assessed_land_price"] == 1230000.0
