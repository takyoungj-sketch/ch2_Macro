import unittest

from decimal import Decimal

from parcel_master.cheongju_land_label_rule_probe import (
    attach_price,
    attach_price_detail,
    label_pair_status,
    normalized_plate,
)


def _row(shape_label, shape_code="5", zone_label="자연녹지지역", source="a.zip"):
    return (
        "4311110100100120000", "2019-08-08", "2019", "01", source,
        "08", "대", "100",
        "UQA", zone_label, "", "",
        "110", "단독", "2", "평지",
        shape_code, shape_label, "1", "광대로한면",
        "1000",
    )


class LabelRuleTests(unittest.TestCase):
    def test_blank_name_matches_the_dictionary_and_a_second_name_is_an_alias(self):
        official = {"5": "부정형", "2": "평지"}
        self.assertEqual(label_pair_status("05", {"", "부정형"}, official), "official_name")
        self.assertEqual(label_pair_status("5", {"부정형", "삼각형"}, official), "official_plus_alias")
        self.assertEqual(label_pair_status("5", {"삼각형"}, official), "name_not_in_dictionary")

    def test_normalized_plate_uses_the_only_nonempty_zone_name(self):
        plate = normalized_plate([_row(""), _row("부정형", source="b.zip")])
        self.assertIsNotNone(plate)
        self.assertEqual(plate[3], "대")
        self.assertEqual(plate[5], frozenset({"자녹"}))
        self.assertIsNone(normalized_plate([_row("", shape_code="5"), _row("", shape_code="6")]))

    def test_price_uses_the_reference_year_and_treats_equal_numbers_as_one(self):
        def plate(year, price):
            return ("2020-01-01", year, 1, "대", "100.0", frozenset(), price)

        self.assertEqual(attach_price([plate(2020, "1000"), plate(2020, "1000.0")], 2020), "same_year")
        self.assertEqual(attach_price([plate(2019, "900")], 2020), "previous_year")
        self.assertEqual(attach_price([plate(2020, "1"), plate(2020, "2")], 2020), "price_conflict")
        self.assertEqual(attach_price([plate(2018, "1")], 2020), "price_missing")
        status, amount, year = attach_price_detail(
            [plate(2020, "1000"), plate(2020, "1000.0")], 2020
        )
        self.assertEqual((status, amount, year), ("same_year", Decimal("1000"), 2020))
        status, amount, year = attach_price_detail([plate(2020, "1"), plate(2020, "2")], 2020)
        self.assertEqual((status, amount, year), ("price_conflict", None, None))


if __name__ == "__main__":
    unittest.main()
