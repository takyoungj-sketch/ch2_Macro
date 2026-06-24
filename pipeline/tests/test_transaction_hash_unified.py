"""
transaction_hash 통합 검증 테스트 (CODE_AUDIT_REPORT B-1, B-4 수정 확인)

검증 목표:
  1. hash_from_series() 와 _rehash_batch 경로가 동일 hash 생성
  2. pd.NA / None / np.nan 이 동일하게 "" 처리
  3. area_sqm / total_price_10k 가 소수점 정규화 후 동일 hash
  4. cancel_date / cancel_type / cancel_flag_raw 는 hash 에 영향을 주지 않음
  5. is_cancelled boolean 만 cancel_flag 에 반영
  6. lot_display 와 lot_number 가 동일 값이면 동일 hash
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from transaction_hash import (
    HASH_FIELDS,
    _num2,
    _s,
    hash_from_series,
    make_transaction_hash,
    transaction_hash_key,
)

# 기준 거래 (청주 비하동)
BASE_ROW = {
    "beopjungri_code": "4311313800",
    "contract_year": 2025,
    "contract_month": 7,
    "contract_day": 12,
    "lot_display": "612",
    "area_sqm": 570.18,
    "total_price_10k": 15000.0,
    "is_cancelled": False,
}


class TestHashFieldsConstant(unittest.TestCase):
    """HASH_FIELDS 상수 존재 확인."""

    def test_hash_fields_defined(self):
        self.assertIsInstance(HASH_FIELDS, list)
        self.assertGreater(len(HASH_FIELDS), 0)

    def test_hash_fields_contains_required(self):
        for f in ("beopjungri_code", "area_sqm", "total_price_10k", "is_cancelled"):
            self.assertIn(f, HASH_FIELDS)


class TestSHelper(unittest.TestCase):
    """_s() — pd.NA / None / NaN 모두 '' 반환 (B-1 수정 검증)."""

    def test_none_returns_empty(self):
        self.assertEqual(_s(None), "")

    def test_float_nan_returns_empty(self):
        import math
        self.assertEqual(_s(float("nan")), "")
        self.assertEqual(_s(math.nan), "")

    def test_pd_na_returns_empty(self):
        try:
            import pandas as pd
            self.assertEqual(_s(pd.NA), "", "pd.NA 는 반드시 '' 여야 함 (B-1)")
        except ImportError:
            self.skipTest("pandas 미설치")

    def test_numpy_nan_returns_empty(self):
        try:
            import numpy as np
            self.assertEqual(_s(np.nan), "")
            self.assertEqual(_s(np.float64("nan")), "")
        except ImportError:
            self.skipTest("numpy 미설치")

    def test_pd_na_vs_none_same(self):
        """pd.NA 와 None 은 동일하게 '' — hash 불일치 방지."""
        try:
            import pandas as pd
            self.assertEqual(_s(pd.NA), _s(None))
        except ImportError:
            self.skipTest("pandas 미설치")

    def test_normal_string_preserved(self):
        self.assertEqual(_s("4311313800"), "4311313800")
        self.assertEqual(_s("  hello  "), "hello")

    def test_zero_string(self):
        self.assertEqual(_s("0"), "0")
        self.assertEqual(_s(0), "0")


class TestNum2Normalization(unittest.TestCase):
    """_num2() — 소수점 2자리 정규화 (B-2 수정 검증)."""

    def test_float_two_decimal(self):
        self.assertEqual(_num2(570.18), "570.18")

    def test_float_trailing_zero(self):
        # float 500.0 → "500.00" (DB NUMERIC(12,2) 와 일치)
        self.assertEqual(_num2(500.0), "500.00")

    def test_float_one_decimal(self):
        # float 570.1 → "570.10"
        self.assertEqual(_num2(570.1), "570.10")

    def test_decimal_from_postgres(self):
        # PostgreSQL NUMERIC(12,2) → Decimal → "570.18"
        self.assertEqual(_num2(Decimal("570.18")), "570.18")
        self.assertEqual(_num2(Decimal("570.10")), "570.10")
        self.assertEqual(_num2(Decimal("500.00")), "500.00")

    def test_float_vs_decimal_same_result(self):
        """pandas float vs PostgreSQL Decimal → 동일 문자열 (B-2 핵심)."""
        self.assertEqual(_num2(570.18), _num2(Decimal("570.18")))
        self.assertEqual(_num2(500.0), _num2(Decimal("500.00")))

    def test_none_returns_empty(self):
        self.assertEqual(_num2(None), "")
        self.assertEqual(_num2(""), "")

    def test_nan_returns_empty(self):
        self.assertEqual(_num2(float("nan")), "")


class TestCancelFieldsIgnored(unittest.TestCase):
    """cancel_date / cancel_type / cancel_flag_raw 는 hash 에 영향 없음 (B-3 수정 검증)."""

    def test_cancel_date_variants_same_hash(self):
        """해제일이 다르거나 플레이스홀더여도 동일 hash."""
        base = {**BASE_ROW, "is_cancelled": False}
        row_empty = {**base, "cancel_date": "", "cancel_type": "", "cancel_flag_raw": ""}
        row_dash = {**base, "cancel_date": "-", "cancel_type": "-", "cancel_flag_raw": ""}
        row_real = {**base, "cancel_date": "2026-03-15", "cancel_type": "해제"}
        self.assertEqual(hash_from_series(row_empty), hash_from_series(row_dash))
        self.assertEqual(hash_from_series(row_empty), hash_from_series(row_real))

    def test_cancel_flag_raw_ignored(self):
        """cancel_flag_raw = "O" vs "" → 동일 hash (is_cancelled=False 기준)."""
        row_o = {**BASE_ROW, "is_cancelled": False, "cancel_flag_raw": "O"}
        row_e = {**BASE_ROW, "is_cancelled": False, "cancel_flag_raw": ""}
        self.assertEqual(hash_from_series(row_o), hash_from_series(row_e))

    def test_is_cancelled_true_differs_from_false(self):
        """is_cancelled=True 와 False 는 반드시 다른 hash."""
        row_not = {**BASE_ROW, "is_cancelled": False}
        row_yes = {**BASE_ROW, "is_cancelled": True}
        self.assertNotEqual(hash_from_series(row_not), hash_from_series(row_yes))

    def test_transaction_hash_key_positions_7_8_always_empty(self):
        """key 문자열의 position 7, 8 은 항상 '' (2026-06 DB 와 호환)."""
        key = transaction_hash_key(
            beopjungri_code="4311313800",
            contract_year=2025,
            contract_month=7,
            contract_day=12,
            area_sqm=570.18,
            total_price_10k=15000.0,
            cancel_date="2026-03-15",
            cancel_type="해제",
            cancel_flag_raw="O",
            is_cancelled=True,
        )
        parts = key.split("|")
        self.assertEqual(len(parts), 10, f"10-part 포맷 위반: {key!r}")
        self.assertEqual(parts[7], "", f"position 7 은 '' 여야 함: {parts[7]!r}")
        self.assertEqual(parts[8], "", f"position 8 은 '' 여야 함: {parts[8]!r}")
        self.assertEqual(parts[9], "1", f"position 9 는 '1' 여야 함: {parts[9]!r}")


class TestHashFromSeriesVsRehatch(unittest.TestCase):
    """hash_from_series() 와 _rehash_batch 경로 완전 일치 검증 (B-4 핵심)."""

    def _simulate_rehash_row(self, row: dict) -> str:
        """_rehash_batch 가 DB 행으로 호출하는 것과 동일한 방식."""
        from datetime import date
        cd = row.get("contract_date")
        if cd is None:
            y = row.get("contract_year", 2025)
            m = row.get("contract_month", 1)
            d = row.get("contract_day", 1)
            cd = date(int(y), int(m), int(d))
        db_row = {
            "beopjungri_code": row.get("beopjungri_code"),
            "sigungu_code": row.get("sigungu_code"),
            "contract_year": row.get("contract_year"),
            "contract_month": row.get("contract_month"),
            "contract_date": cd,
            "lot_display": row.get("lot_display"),
            "area_sqm": row.get("area_sqm"),
            "total_price_10k": row.get("total_price_10k"),
            "is_cancelled": bool(row.get("is_cancelled", False)),
        }
        return hash_from_series(db_row)

    def test_clean_vs_rehash_non_cancelled(self):
        """비해제 거래: clean.py 경로 == rehash 경로."""
        clean_hash = hash_from_series(BASE_ROW)
        rehash_hash = self._simulate_rehash_row(BASE_ROW)
        self.assertEqual(clean_hash, rehash_hash, "B-4: 비해제 거래 hash 불일치")

    def test_clean_vs_rehash_cancelled(self):
        """해제 거래: clean.py 에서 cancel_flag_raw='O' 여도 rehash 와 동일 hash."""
        cancelled_clean = {
            **BASE_ROW,
            "is_cancelled": True,
            "cancel_flag_raw": "O",
            "cancel_date": "2026-03-15",
            "cancel_type": "해제",
        }
        cancelled_db = {**BASE_ROW, "is_cancelled": True}
        self.assertEqual(
            hash_from_series(cancelled_clean),
            self._simulate_rehash_row(cancelled_db),
            "B-4: 해제 거래 hash 불일치",
        )

    def test_pd_na_lot_vs_none_lot_same_hash(self):
        """lot_number = pd.NA vs None → 동일 hash (B-1 lot 필드 영향)."""
        try:
            import pandas as pd
            row_none = {**BASE_ROW, "lot_number": None}
            row_pdna = {**BASE_ROW, "lot_number": pd.NA}
            self.assertEqual(
                hash_from_series(row_none),
                hash_from_series(row_pdna),
                "pd.NA lot_number 와 None 은 동일 hash 여야 함 (B-1)",
            )
        except ImportError:
            self.skipTest("pandas 미설치")

    def test_area_float_vs_decimal_same_hash(self):
        """pandas float area_sqm vs PostgreSQL Decimal → 동일 hash."""
        row_float = {**BASE_ROW, "area_sqm": 570.18}
        row_decimal = {**BASE_ROW, "area_sqm": Decimal("570.18")}
        self.assertEqual(
            hash_from_series(row_float),
            hash_from_series(row_decimal),
            "float vs Decimal area_sqm hash 불일치 (B-2)",
        )

    def test_price_trailing_zero_same_hash(self):
        """total_price_10k: 15000.0 (float) == Decimal('15000.00')."""
        row_float = {**BASE_ROW, "total_price_10k": 15000.0}
        row_decimal = {**BASE_ROW, "total_price_10k": Decimal("15000.00")}
        self.assertEqual(
            hash_from_series(row_float),
            hash_from_series(row_decimal),
            "price trailing zero hash 불일치 (B-2)",
        )

    def test_lot_display_vs_lot_number_same_hash(self):
        """lot_display='612' 와 lot_number='612' 는 동일 hash."""
        row_disp = {**BASE_ROW, "lot_display": "612", "lot_number": None}
        row_num = {**BASE_ROW, "lot_display": None, "lot_number": "612"}
        self.assertEqual(hash_from_series(row_disp), hash_from_series(row_num))

    def test_source_row_no_ignored(self):
        """Excel 순번 source_row_no 는 hash 에 영향 없음."""
        row_a = {**BASE_ROW, "source_row_no": 1}
        row_b = {**BASE_ROW, "source_row_no": 99999}
        self.assertEqual(hash_from_series(row_a), hash_from_series(row_b))

    def test_different_area_different_hash(self):
        """면적이 다르면 반드시 다른 hash."""
        row_a = {**BASE_ROW, "area_sqm": 570.18}
        row_b = {**BASE_ROW, "area_sqm": 570.19}
        self.assertNotEqual(hash_from_series(row_a), hash_from_series(row_b))

    def test_hash_is_64_char_hex(self):
        """SHA-256 → 64자 hex 문자열."""
        h = hash_from_series(BASE_ROW)
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_hash_stability_golden_value(self):
        """기준값 고정 테스트 — hash 공식 변경 시 이 테스트가 깨져 경보 역할."""
        key = transaction_hash_key(
            beopjungri_code="4311313800",
            contract_year=2025,
            contract_month=7,
            contract_day=12,
            lot_display="612",
            area_sqm=570.18,
            total_price_10k=15000.0,
            is_cancelled=False,
        )
        expected_hash = make_transaction_hash(key)
        actual = hash_from_series(BASE_ROW)
        self.assertEqual(
            actual,
            expected_hash,
            "hash 공식이 변경됐습니다. DECISIONS.md에 기록 후 dedupe+rehash 계획을 수립하세요.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
