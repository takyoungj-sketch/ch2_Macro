"""임대 보류: collective_reuse 만 해제 후보고, 대장 분할과 part 0 임대 전용은 보류."""
from __future__ import annotations

import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))

from rent import build_sale_building_map as m  # noqa: E402

REUSE = "r" * 64
TITLE = "t" * 64
PART0 = "p" * 64
PEND = "d" * 64
SHA = m.COLLECTIVE_SHA


def _row(key, evidence, decision="split"):
    return {
        "key": key,
        "asset_type": "apartment",
        "decision": decision,
        "evidence": evidence,
        "collective_sha256": SHA,
    }


def test_only_collective_reuse_with_matching_conditions_is_released():
    rows = [
        _row(REUSE, "collective_reuse"),
        _row(TITLE, "title_register"),
        _row(PART0, "title_register"),
        _row(PEND, "", decision="pending"),
    ]
    sale = {("apartment", REUSE), ("apartment", TITLE), ("apartment", PART0)}
    rent = {("apartment", REUSE), ("apartment", TITLE), ("apartment", PART0)}
    held = m.apply_rent_hold(
        {REUSE, TITLE},
        rows,
        sale=sale,
        rent=rent,
        lot_ok={REUSE},
        fanout=set(),
    )
    assert REUSE not in held
    assert TITLE in held
    assert PART0 in held
    assert PEND in held


def test_reuse_stays_held_when_lot_or_fanout_fails():
    row = [_row(REUSE, "collective_reuse")]
    sale = {("apartment", REUSE)}
    rent = {("apartment", REUSE)}
    held = m.apply_rent_hold(set(), row, sale=sale, rent=rent, lot_ok=set(), fanout=set())
    assert REUSE in held
    held = m.apply_rent_hold({REUSE}, row, sale=sale, rent=rent, lot_ok={REUSE}, fanout={REUSE})
    assert REUSE in held
