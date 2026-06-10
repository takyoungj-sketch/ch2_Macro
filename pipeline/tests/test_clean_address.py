"""clean.py 주소 파싱·행정명 정규화 단위 테스트."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

_PIPELINE = Path(__file__).resolve().parents[1]
if str(_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_PIPELINE))

from clean import (  # noqa: E402
    _extract_paren_content,
    _normalize_admin_label,
    _parse_address_structured,
    map_beopjungri_codes,
)


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


class TestMapBeopjungriFallbacks(unittest.TestCase):
    """방법 1: 시도 별칭 + 분구 토큰 drop fallback."""

    region_maps = {
        "by_sigungu_name": {
            ("경기도", "화성시", "남양읍", "남양리"): "4159026221",
            ("전북특별자치도", "전주시 완산구", "효자동1가", "효자동1가"): "5211114000",
            ("충청북도", "청주시 상당구", "미원면", "기암리"): "4311132026",
        },
        "by_sigungu_code": {},
        "by_eup_prefix": {
            ("전북특별자치도", "전주시 완산구", "효자동"): ["5211114000"],
        },
    }

    def _map_one(self, addr: str) -> tuple[str, bool, str]:
        df = pd.DataFrame({"sigungu_name": [addr]})
        out = map_beopjungri_codes(df, self.region_maps)
        return (
            str(out["beopjungri_code"].iloc[0]),
            bool(out["needs_review"].iloc[0]),
            str(out["mapping_notes"].iloc[0]),
        )

    def test_subgu_dropped_hwaseong_manse(self) -> None:
        code, review, note = self._map_one("경기도 화성시 만세구 남양읍 남양리")
        self.assertEqual(code, "4159026221")
        self.assertFalse(review)
        self.assertEqual(note, "subgu_dropped")

    def test_sido_alias_jeonbuk(self) -> None:
        code, review, note = self._map_one("전북특별자치도 전주시 완산구 효자동")
        self.assertEqual(code, "5211114000")
        self.assertFalse(review)
        self.assertIn(note, ("", "sido_alias", "eup_prefix", "eup_prefix_ambiguous"))

    def test_historical_short_addr_jeonbuk(self) -> None:
        code, review, note = self._map_one("전주광역시 완산구 효자동")
        self.assertEqual(code, "5211114000")
        self.assertFalse(review)
        self.assertIn(note, ("historical_short_addr", "eup_prefix", "eup_prefix_ambiguous"))

    def test_historical_city_dong_jeonbuk(self) -> None:
        maps = {
            **self.region_maps,
            "by_sigungu_name": {
                **self.region_maps["by_sigungu_name"],
                ("전북특별자치도", "군산시", "나운동", "나운동"): "5213014400",
            },
        }
        df = pd.DataFrame({"sigungu_name": ["군산시 나운동"]})
        out = map_beopjungri_codes(df, maps)
        self.assertEqual(str(out["beopjungri_code"].iloc[0]), "5213014400")
        self.assertEqual(str(out["mapping_notes"].iloc[0]), "historical_short_addr")

    def test_plain_match_no_fallback_note(self) -> None:
        code, review, note = self._map_one("충청북도 청주시 상당구 미원면 기암리(岐岩)")
        self.assertEqual(code, "4311132026")
        self.assertFalse(review)
        self.assertEqual(note, "")

    def test_sejong_two_token_dong(self) -> None:
        maps = {
            **self.region_maps,
            "by_sigungu_name": {
                **self.region_maps["by_sigungu_name"],
                ("세종특별자치시", "집현동", "", ""): "3611011800",
            },
        }
        df = pd.DataFrame({"sigungu_name": ["세종특별자치시  집현동"]})
        out = map_beopjungri_codes(df, maps)
        self.assertEqual(str(out["beopjungri_code"].iloc[0]), "3611011800")
        self.assertFalse(bool(out["needs_review"].iloc[0]))
        self.assertEqual(str(out["mapping_notes"].iloc[0]), "sejong_admin_leaf")


class TestExtractParenContent(unittest.TestCase):
    def test_ascii(self) -> None:
        self.assertEqual(_extract_paren_content("기암리(岐岩)"), "岐岩")

    def test_fullwidth(self) -> None:
        self.assertEqual(_extract_paren_content("화산리（花山）"), "花山")

    def test_no_paren(self) -> None:
        self.assertEqual(_extract_paren_content("가경동"), "")

    def test_multiple(self) -> None:
        self.assertEqual(_extract_paren_content("(岐岩)(里)"), "岐岩里")


class TestDisambiguateHomonym(unittest.TestCase):
    """동명이리(같은 정규화 이름, 다른 한자) 분기 — A 작업."""

    region_maps = {
        "by_sigungu_name": {
            # 두 동명이리 중 by_name 에는 마지막 등록 코드만 남아 있을 수 있다.
            ("충청북도", "청주시 상당구", "미원면", "기암리"): "4311132026",
        },
        "by_sigungu_code": {},
        "disamb_by_name": {
            ("충청북도", "청주시 상당구", "미원면", "기암리"): [
                ("4311132026", "岐岩", "기암리(岐岩)"),
                ("4311132033", "基岩", "기암리(基岩)"),
            ],
        },
        "disamb_by_code": {},
    }

    def _map(self, addr: str) -> tuple[str, bool, str]:
        df = pd.DataFrame({"sigungu_name": [addr]})
        out = map_beopjungri_codes(df, self.region_maps)
        return (
            str(out["beopjungri_code"].iloc[0]),
            bool(out["needs_review"].iloc[0]),
            str(out["mapping_notes"].iloc[0]),
        )

    def test_picks_kiam_giam(self) -> None:
        code, review, note = self._map("충청북도 청주시 상당구 미원면 기암리(岐岩)")
        self.assertEqual(code, "4311132026")
        self.assertFalse(review)
        self.assertEqual(note, "disambiguated_hanja")

    def test_picks_kiam_giam_second(self) -> None:
        code, review, note = self._map("충청북도 청주시 상당구 미원면 기암리(基岩)")
        self.assertEqual(code, "4311132033")
        self.assertFalse(review)
        self.assertEqual(note, "disambiguated_hanja")

    def test_no_hanja_falls_back_to_first(self) -> None:
        # 한자가 없으면 disambiguation 못 함 → 기존 by_name 매핑(첫 등록 코드)이 작동
        code, review, note = self._map("충청북도 청주시 상당구 미원면 기암리")
        self.assertEqual(code, "4311132026")
        self.assertFalse(review)
        # disambiguation 분기가 아니므로 note 는 빈 문자열
        self.assertEqual(note, "")


if __name__ == "__main__":
    unittest.main()
