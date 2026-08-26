"""용도지역 빈도 정렬 — 동수는 라벨 문자열로 결정론화 (D-050 P0.4)."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from built.recover_address import TX_SQL, build_parser, order_zone_labels


def test_order_zone_labels_count_then_name():
    cnt = Counter({"제2종일반주거지역": 3, "일반상업지역": 5, "제1종일반주거지역": 5})
    got = order_zone_labels(cnt, broad=set())
    assert got[0] == "일반상업지역"
    assert got[1] == "제1종일반주거지역"
    assert got[2] == "제2종일반주거지역"


def test_order_zone_labels_coarse_last_even_if_more_frequent():
    cnt = Counter({"도시지역": 9, "제2종일반주거지역": 2, "제3종일반주거지역": 2})
    got = order_zone_labels(cnt, broad={"도시지역"})
    assert got[-1] == "도시지역"
    assert got[0] == "제2종일반주거지역"
    assert got[1] == "제3종일반주거지역"


def test_tx_sql_gates_min_year():
    assert "contract_year >= :min_year" in TX_SQL


def test_cli_min_year_defaults_to_2019():
    ns = build_parser().parse_args([])
    assert ns.min_year == 2019
    assert ns.snapshot == "all"
    assert ns.policy == "time_fallback"
