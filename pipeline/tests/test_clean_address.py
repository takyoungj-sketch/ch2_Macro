"""clean.py 주소 파싱·행정명 정규화 단위 테스트."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PIPELINE = Path(__file__).resolve().parents[1]
if str(_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_PIPELINE))

from clean import _normalize_admin_label, _parse_address_structured  # noqa: E402


class TestNormalizeAdminLabel(unittest.TestCase):
    def test_strips_ascii_paren_hanja(self) -> None:
        self.assertEqual(_normalize_admin_label("기암리(岐岩)"), "기암리")

    def test_strips_fullwidth_paren(self) -> None:
        self.assertEqual(_normalize_admin_label("가경동（佳景洞）"), "가경동")

    def test_nested_parens(self) -> None:
        self.assertEqual(_normalize_admin_label("리(甲(乙))"), "리")


class TestParseAddressStructured(unittest.TestCase):
    def test_ri_with_hanja_paren(self) -> None:
        addr = "충청북도 청주시 상당구 미원면 기암리(岐岩)"
        self.assertEqual(
            _parse_address_structured(addr),
            ("충청북도", "청주시 상당구", "미원면", "기암리"),
        )

    def test_ri_without_paren(self) -> None:
        addr = "충청북도 단양군 가곡면 여천리"
        self.assertEqual(
            _parse_address_structured(addr),
            ("충청북도", "단양군", "가곡면", "여천리"),
        )

    def test_dong_with_hanja_paren(self) -> None:
        addr = "충청북도 청주시 흥덕구 가경동(佳景洞)"
        self.assertEqual(
            _parse_address_structured(addr),
            ("충청북도", "청주시 흥덕구", "가경동", "가경동"),
        )

    def test_empty(self) -> None:
        self.assertEqual(_parse_address_structured(""), ("", "", "", ""))


if __name__ == "__main__":
    unittest.main()
