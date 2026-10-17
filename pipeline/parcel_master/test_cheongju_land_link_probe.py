import unittest

from parcel_master.cheongju_land_link_probe import (
    classify_link,
    exclusion_reason,
    official_price_summary,
    reference_price_summary,
    reference_year_price,
)


def _plate(asof, year, jimok, area, zone, price="10", month=1):
    return (asof, year, month, jimok, area, frozenset({zone}), price)


def _world():
    plates = {
        "4311110100100120000": [
            _plate("2019-08-08", 2019, "대", "100.0", "자녹", "1000"),
            _plate("2024-07-30", 2024, "대", "100.0", "자녹", "2000"),
        ],
        "4311110100100990000": [
            _plate("2026-05-12", 2026, "대", "100.0", "자녹", "3000"),
        ],
        "4311110100200120000": [
            _plate("2024-07-30", 2024, "임", "100.0", "자녹", "4000"),
        ],
    }
    for rows in plates.values():
        rows.sort()
    index = {}
    for pnu, rows in plates.items():
        for row in rows:
            index.setdefault((pnu[:10], row[3], row[4]), set()).add(pnu)
    return plates, index


class LinkProbeTests(unittest.TestCase):
    def test_unique_candidate_uses_latest_plate_on_or_before_contract(self):
        plates, index = _world()
        result = classify_link(
            beopjungri_code="4311110100",
            land_category="대",
            zone_type="자녹",
            area_sqm="100",
            lot_display="1*",
            contract_date="2024-08-01",
            index=index,
            plates=plates,
        )
        self.assertEqual(result["status"], "unique_unverified")
        self.assertEqual(result["trait_asof"], "2024-07-30")
        self.assertEqual(result["price_year"], "2024")
        self.assertEqual(result["price"], "2000")

    def test_multiple_and_later_plate_are_separate(self):
        plates, index = _world()
        plates["4311110100100130000"] = [_plate("2024-01-23", 2024, "대", "100.0", "자녹", "9")]
        index[("4311110100", "대", "100.0")].add("4311110100100130000")
        multiple = classify_link(
            beopjungri_code="4311110100",
            land_category="대",
            zone_type="자녹",
            area_sqm=100,
            lot_display="1*",
            contract_date="2025-01-01",
            index=index,
            plates=plates,
        )
        self.assertEqual(multiple["status"], "multiple_candidates")
        later = classify_link(
            beopjungri_code="4311110100",
            land_category="대",
            zone_type="자녹",
            area_sqm=100,
            lot_display="9*",
            contract_date="2020-01-01",
            index=index,
            plates=plates,
        )
        self.assertEqual(later["status"], "no_prior_plate")

    def test_mountain_lot_and_exclusions(self):
        plates, index = _world()
        mountain = classify_link(
            beopjungri_code="4311110100",
            land_category="임",
            zone_type="자녹",
            area_sqm="100.0",
            lot_display="산12",
            contract_date="2025-01-01",
            index=index,
            plates=plates,
        )
        self.assertEqual(mountain["status"], "unique_unverified")
        self.assertEqual(exclusion_reason({"is_cancelled": True, "is_valid": True, "zone_type": "자녹", "lot_display": "1", "area_sqm": 1}), "cancelled")
        self.assertEqual(exclusion_reason({"is_valid": False, "zone_type": "자녹", "lot_display": "1", "area_sqm": 1}), "invalid")
        self.assertEqual(exclusion_reason({"is_valid": True, "zone_type": "기타", "lot_display": "1", "area_sqm": 1}), "unsupported_zone")

    def test_march_contract_keeps_previous_year_price(self):
        plates = {
            "4311110100100120000": [
                _plate("2023-08-03", 2022, "대", "100.0", "자녹", "1000"),
                _plate("2023-08-03", 2023, "대", "100.0", "자녹", "1100"),
                _plate("2024-07-30", 2024, "대", "100.0", "자녹", "1200"),
            ]
        }
        plates["4311110100100120000"].sort()
        index = {("4311110100", "대", "100.0"): {"4311110100100120000"}}
        march = classify_link(
            beopjungri_code="4311110100",
            land_category="대",
            zone_type="자녹",
            area_sqm="100",
            lot_display="12",
            contract_date="2024-03-01",
            index=index,
            plates=plates,
        )
        self.assertEqual(march["price_year"], "2023")
        self.assertEqual(march["trait_asof"], "2023-08-03")
        summary = official_price_summary([
            {"status": "unique_unverified", "contract_date": "2024-03-01", "price_year": "2023", "price": "1100", "price_on_or_before_contract_year": True},
            {"status": "unique_unverified", "contract_date": "2024-09-01", "price_year": "2024", "price": "1200", "price_on_or_before_contract_year": True},
            {"status": "no_prior_plate", "contract_date": "2019-06-01", "price_year": "", "price": "", "price_on_or_before_contract_year": False},
            {"status": "unique_unverified", "contract_date": "2018-06-01", "price_year": "2018", "price": "1", "price_on_or_before_contract_year": True},
        ])
        self.assertEqual(summary["comparable"], 3)
        self.assertEqual(summary["same_year"], 1)
        self.assertEqual(summary["previous_year"], 1)
        self.assertEqual(summary["attached"], 2)

    def test_reference_year_uses_later_plate_and_stops_at_one_year_back(self):
        rows = [
            _plate("2019-08-08", 2019, "대", "100.0", "자녹", "1000"),
            _plate("2023-08-03", 2023, "대", "100.0", "자녹", "1100"),
            _plate("2024-07-30", 2024, "대", "100.0", "자녹", "1200"),
        ]
        march = reference_year_price(rows, 2024, "2024-03-01")
        self.assertEqual(march["price_rule"], "same_year")
        self.assertEqual(march["reference_price"], "1200")
        self.assertTrue(march["reference_after_contract"])
        without_2024 = [row for row in rows if row[1] != 2024]
        self.assertEqual(reference_year_price(without_2024, 2024, "2024-03-01")["price_rule"], "previous_year")
        only_2019 = [row for row in rows if row[1] == 2019]
        self.assertEqual(reference_year_price(only_2019, 2024, "2024-03-01")["price_rule"], "price_missing")
        conflict = rows + [_plate("2025-05-12", 2024, "대", "100.0", "자녹", "9999")]
        self.assertEqual(reference_year_price(conflict, 2024, "2024-03-01")["price_rule"], "conflict")

    def test_reference_summary_keeps_parcel_gaps_separate_from_price_gaps(self):
        summary = reference_price_summary([
            {"status": "unique_unverified", "contract_date": "2024-03-01", "price_rule": "same_year", "reference_after_contract": True},
            {"status": "unique_unverified", "contract_date": "2024-03-01", "price_rule": "previous_year", "reference_after_contract": False},
            {"status": "unique_unverified", "contract_date": "2019-06-01", "price_rule": "price_missing", "reference_after_contract": False},
            {"status": "unique_unverified", "contract_date": "2019-06-01", "price_rule": "conflict", "reference_after_contract": False},
            {"status": "multiple_candidates", "contract_date": "2020-01-01"},
            {"status": "no_prior_plate", "contract_date": "2020-01-01"},
            {"status": "no_candidate", "contract_date": "2021-01-01"},
            {"status": "unique_unverified", "contract_date": "2018-01-01", "price_rule": "same_year", "reference_after_contract": False},
        ])
        self.assertEqual(summary["comparable"], 7)
        self.assertEqual(summary["same_year"], 1)
        self.assertEqual(summary["previous_year_fallback"], 1)
        self.assertEqual(summary["parcel_found_price_missing"], 1)
        self.assertEqual(summary["price_conflict"], 1)
        self.assertEqual(summary["parcel_not_found"], 2)
        self.assertEqual(summary["multiple_candidates"], 1)
        self.assertEqual(summary["same_year_from_later_plate"], 1)


if __name__ == "__main__":
    unittest.main()
