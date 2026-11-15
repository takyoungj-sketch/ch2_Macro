# -*- coding: utf-8 -*-
"""c7 매매·임대 연결 실측: C-01 집계에서 c2 가 든 reason(복합 포함)을 뺀다."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

D = Path(__file__).resolve().parents[2] / "scripts" / "lab" / "collective_p2"
sys.path.insert(0, str(D))
_spec = importlib.util.spec_from_file_location("c7", D / "c7_rent_links.py")
c7 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c7)


def test_is_c01_split():
    assert c7.is_c01_split("split")
    assert c7.is_c01_split("honam_sido+split")
    for r in ("c2_split", "c2_chain", "split+c2_split", "honam_sido+c2_split", "honam_sido", "", None):
        assert not c7.is_c01_split(r), r


def test_c01_split_rows_keeps_only_c01_pairs():
    km = pd.DataFrame({"old_key": list("abcdef"), "new_key": list("ABCDEF"), "asset_type": ["apartment"] * 6,
                       "reason": ["split", "split+c2_split", "honam_sido+c2_split", "c2_split", "c2_chain",
                                  "honam_sido+split"]})
    out = c7.c01_split_rows(km)
    assert list(out["old_key"]) == ["a", "f"] and "reason" not in out.columns
