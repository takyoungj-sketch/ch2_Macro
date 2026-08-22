import sys
from pathlib import Path

_PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
sys.path.insert(0, str(_PIPELINE))

from parcel_master.pnu import (  # noqa: E402
    beopjungri_code,
    gbn_from_title,
    make_pnu,
    parse_lot,
    pnu_from_title_parts,
    pnu_from_tx,
    split_pnu,
    structure_group,
)


def test_pnu_from_title_daejeon_sample():
    pnu = pnu_from_title_parts("30110", "11400", "0", "0182", "0007")
    assert pnu == "3011011400101820007"
    parts = split_pnu(pnu)
    assert parts["beopjungri_code"] == "3011011400"
    assert parts["gbn"] == "1"
    assert parts["bun"] == "0182"
    assert parts["ji"] == "0007"


def test_san_gbn():
    assert gbn_from_title("0") == "1"
    assert gbn_from_title("1") == "2"
    parsed = parse_lot("산123-4")
    assert parsed == ("0123", "0004", "2")
    assert make_pnu("3011011400", "2", "0123", "0004") == "3011011400201230004"


def test_kapt_example_pnu_shape():
    pnu = "1111011800100720000"
    parts = split_pnu(pnu)
    assert parts["beopjungri_code"] == "1111011800"
    assert parts["gbn"] == "1"
    assert parts["bun"] == "0072"
    assert parts["ji"] == "0000"


def test_tx_lot():
    assert pnu_from_tx("4311312500", "1200") == "4311312500112000000"
    assert pnu_from_tx("4311312500", "1200-1") == "4311312500112000001"


def test_beopjungri_concat():
    assert beopjungri_code("30110", "11400") == "3011011400"


def test_structure_group():
    assert structure_group("철근콘크리트구조") == "RC"
    assert structure_group("일반철골구조") == "steel"
    assert structure_group("벽돌구조") == "masonry"
    assert structure_group("일반목구조") == "wood"
