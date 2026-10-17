"""복원 확정 시 표제부 관리번호 — 동이 하나로 정해질 때만."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from built.recover_address import build_parcels, match_all

TITLE_COLS = ["pk", "addr_lot", "addr_road", "sigungu_code", "bjd_code", "bun", "ji", "land_area",
              "gross_area", "struct_name", "use_name", "floors_above", "approve_date"]


def _title(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [[pk, "", "", "43111", "10100", bun, "0", "200", gross, "벽돌구조", "단독주택", "2", "19900101"]
         for pk, bun, gross in rows],
        columns=TITLE_COLS,
    )


def _tx(gross: float) -> pd.DataFrame:
    return pd.DataFrame([{
        "id": 1, "transaction_hash": "a" * 64, "asset_type": "detached", "beopjungri_code": "4311110100",
        "lot_number": "1**", "road_name": "", "zone_type": "", "gross_area": gross, "land_area": 200,
        "building_age": None, "contract_year": 2025, "contract_month": 1,
    }])


def _match(title: pd.DataFrame, gross: float) -> dict:
    summ = pd.DataFrame(columns=["sigungu_code", "bjd_code", "bun", "ji", "land_area"])
    parcels, idx = build_parcels(title, summ, {})
    return match_all(_tx(gross), parcels, idx).iloc[0].to_dict()


def test_single_building_sets_pk():
    rec = _match(_title([("P1", "120", "88.5"), ("P2", "130", "70")]), 88.5)
    assert rec["tier"] == "A1"
    assert rec["bldrgst_pk"] == "P1"


def test_tied_buildings_leave_pk_empty():
    rec = _match(_title([("P1", "120", "88.5"), ("P2", "120", "88.5"), ("P3", "130", "70")]), 88.5)
    assert rec["tier"] == "A1"
    assert rec["struct"] == "벽돌구조"
    assert rec["bldrgst_pk"] is None
