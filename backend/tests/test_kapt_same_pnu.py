"""오피스텔 같은 지번·같은 이름 K-apt 복사. DB 없음."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
sys.path.insert(0, str(_PIPELINE))

from parcel_master.apply_kapt_same_pnu import (  # noqa: E402
    MATCH_RULE,
    classify_kapt_same_pnu,
    compact_display,
)

PNU = "4311311700104590000"


def _ot(**kw):
    base = {
        "building_key": "o" * 64,
        "display_name": "신해블루지움",
        "pnu": PNU,
        "match_tier": "T",
        "match_rule": "title_pnu",
        "danji_code": None,
        "n_tx": 215,
        "building_year": 2019,
        "has_attr_row": True,
    }
    base.update(kw)
    return base


def _apt(**kw):
    base = {
        "building_key": "a" * 64,
        "display_name": "신해블루지움",
        "pnu": PNU,
        "match_tier": "C",
        "match_rule": "lot_exact",
        "danji_code": "A10026655",
        "approved_year": 2019,
        "builder_raw": "신해공영",
        "households": 299,
        "kapt_name": "청주블루지움B910",
        "n_tx": 157,
    }
    base.update(kw)
    return base


def test_compact_display_strips_spaces():
    assert compact_display("신해 블루지움") == "신해블루지움"


def test_same_name_copies_builder_as_p_kapt_same_pnu():
    classified = classify_kapt_same_pnu([_ot()], [_apt()], {})
    assert len(classified["fill"]) == 1
    rec = classified["fill"][0]
    assert rec["match_tier"] == "P"
    assert rec["match_rule"] == MATCH_RULE
    assert rec["builder_raw"] == "신해공영"
    assert rec["households"] == 299
    assert rec["danji_code"] == "A10026655"


def test_different_name_same_lot_not_copied():
    classified = classify_kapt_same_pnu(
        [_ot(display_name="파크하비오")],
        [_apt(display_name="파크하비오아파트")],
        {},
    )
    assert classified["fill"] == []
    assert len(classified["skip_mismatch"]) == 1


def test_already_p_keep():
    classified = classify_kapt_same_pnu(
        [_ot(match_tier="P", match_rule=MATCH_RULE, danji_code="A10026655")],
        [_apt()],
        {},
    )
    assert classified["fill"] == []
    assert len(classified["keep"]) == 1


def test_unique_kapt_names_compatible_without_apt_sibling():
    master = SimpleNamespace(danji_name="한화꿈에그린", **{k: None for k in (
        "danji_code", "approved_date", "builder_raw", "developer_raw", "structure_raw",
        "households", "households_sale", "households_rent", "dong_count", "max_floor",
        "parking_total", "danji_class", "supply_type",
    )})
    master.danji_code = "A999"
    master.builder_raw = "한화"
    master.households = 100
    classified = classify_kapt_same_pnu(
        [_ot(display_name="한화꿈에그린", pnu="1111010100100010001")],
        [],
        {"1111010100100010001": master},
    )
    assert len(classified["fill"]) == 1
    assert classified["fill"][0]["match_rule"] == MATCH_RULE
