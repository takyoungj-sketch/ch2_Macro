"""transaction_hash — Excel 순번과 무관하게 동일 거래는 동일 hash."""

from __future__ import annotations

import unittest

from transaction_hash import hash_from_series, transaction_hash_key


class TestTransactionHash(unittest.TestCase):
    def test_same_transaction_different_source_row_no_same_hash(self):
        base = {
            "beopjungri_code": "4311313800",
            "contract_year": 2025,
            "contract_month": 7,
            "contract_day": 12,
            "lot_number": "6**",
            "area_sqm": 562.0,
            "total_price_10k": 10329.0,
            "cancel_date": "",
            "cancel_type": "",
            "cancel_flag_raw": "",
        }
        row_a = {**base, "source_row_no": 20057, "_raw_id": 100}
        row_b = {**base, "source_row_no": 99999, "_raw_id": 200}
        self.assertEqual(hash_from_series(row_a), hash_from_series(row_b))

    def test_different_transactions_different_hash(self):
        a = {
            "beopjungri_code": "4311313800",
            "contract_year": 2025,
            "contract_month": 5,
            "contract_day": 30,
            "area_sqm": 1269.0,
            "total_price_10k": 23740.0,
        }
        b = {**a, "contract_month": 7, "area_sqm": 562.0, "total_price_10k": 10329.0}
        self.assertNotEqual(hash_from_series(a), hash_from_series(b))

    def test_transaction_hash_key_excludes_source_row(self):
        key = transaction_hash_key(
            beopjungri_code="4311313800",
            contract_year=2025,
            contract_month=7,
            contract_day=12,
            lot_number="6**",
            area_sqm=562,
            total_price_10k=10329,
        )
        self.assertNotIn("20057", key)
        self.assertIn("4311313800", key)


if __name__ == "__main__":
    unittest.main()
