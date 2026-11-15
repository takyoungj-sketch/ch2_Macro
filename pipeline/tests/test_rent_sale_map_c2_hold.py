# -*- coding: utf-8 -*-
"""매매·임대 exact 연결: C-2 판정 키(본 조각)·조각 키는 보류(Codex 검토)."""
from __future__ import annotations

import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))

from rent import build_sale_building_map as m  # noqa: E402

K, K1, H0, H1, H1p, U = "k" * 64, "m" * 64, "h" * 64, "i" * 64, "j" * 64, "u" * 64


class _Conn:
    def __init__(self, tables=True):
        self.tables = tables

    def execute(self, stmt, params=None):
        s = str(stmt)

        class R(list):
            def scalar(self_inner):
                return self.tables

        if "to_regclass" in s:
            return R()
        if "collective_building_key_c2_units" in s:
            return R([(K,), (H1,)])
        if "collective_building_key_map" in s:
            return R([(K, K1, "c2_split"), (H0, H1p, "honam_sido+c2_split"), (H1, H1p, "c2_chain")])
        raise AssertionError(s)


def test_hold_keys_cover_base_and_fragments_not_vanished_old_keys():
    assert m.c2_hold_keys(_Conn()) == {K, K1, H1, H1p}          # H0(호남 옛 키, 사라짐)는 대상 아님
    assert m.c2_hold_keys(_Conn(tables=False)) == set()


def test_exact_links_hold_c2_keys():
    sale = {("apartment", K), ("apartment", K1), ("apartment", U), ("officetel", "o" * 64)}
    rent = {("apartment", K), ("apartment", U), ("rowhouse", "r" * 64)}
    exact, held = m.exact_links(sale, rent, {K, K1})
    assert exact == {("apartment", U)} and held == {("apartment", K)}
    exact, held = m.exact_links(sale, rent, set())
    assert exact == {("apartment", U), ("apartment", K)} and held == set()
