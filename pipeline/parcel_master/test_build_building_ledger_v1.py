import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parcel_master.build_building_ledger_v1 import identity  # noqa: E402


def test_general_lot_short_bjd():
    assert identity("43111", "10100", "0", "12", "3") == ("4311110100100120003", "canonical_address")


def test_mountain_lot_full_bjd():
    assert identity("43111", "4311110100", "1", "12", "0")[0] == "4311110100200120000"


def test_land_type_two_is_held():
    assert identity("43111", "10100", "2", "12", "3") == (None, "unknown_land_type")


def test_bjd_must_belong_to_sigungu():
    assert identity("43111", "4311210100", "0", "1", "0") == (None, "invalid_bjd")


def test_bad_lot_numbers():
    assert identity("43111", "10100", "0", "12345", "0")[1] == "invalid_main_lot"
    assert identity("43111", "10100", "0", "1", "")[1] == "invalid_sub_lot"
    assert identity("4311", "10100", "0", "1", "0")[1] == "invalid_district"
