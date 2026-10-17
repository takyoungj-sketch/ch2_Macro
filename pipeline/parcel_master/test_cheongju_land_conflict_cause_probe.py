import unittest

from parcel_master.cheongju_land_conflict_cause_probe import conflict_signature, filename_day


def _row(source, jimok="01", area="10", zone="UQA", price="1000", label="대"):
    return (
        "4311110100100120000",
        "2020-08-12",
        "2020",
        "01",
        source,
        jimok,
        label,
        area,
        zone,
        "도시지역",
        "",
        "",
        "110",
        "대지",
        "01",
        "평지",
        "01",
        "정방형",
        "08",
        "광대로",
        price,
    )


class ConflictCauseTests(unittest.TestCase):
    def test_price_area_zone_and_format_stay_separate(self):
        price = conflict_signature([_row("a.zip", price="1000"), _row("b.zip", price="1200")])
        self.assertEqual(price["category"], "price_only")
        self.assertFalse(price["same_zip"])
        area = conflict_signature([_row("a.zip", area="10"), _row("a.zip", area="12")])
        self.assertEqual((area["category"], area["same_zip"]), ("area_only", True))
        zone = conflict_signature([_row("a.zip", zone="UQA"), _row("b.zip", zone="UQB")])
        self.assertEqual(zone["category"], "zone_only")
        formatted = conflict_signature([_row("a.zip", area="10"), _row("b.zip", area="10.0")])
        self.assertEqual(formatted["category"], "area_format_only")
        both = conflict_signature([_row("a.zip", price="1", area="10"), _row("b.zip", price="2", area="12")])
        self.assertEqual(both["category"], "multiple")
        self.assertEqual(both["variants"], 2)
        blank = conflict_signature([_row("AL_43111_D195_20190328.zip", label=""), _row("AL_43_D195_20220916.zip", label="대")])
        self.assertEqual(blank["category"], "label_only")
        self.assertEqual(blank["label_values"]["jimok_label"], ["", "대"])

    def test_three_variants_and_filename_day_do_not_choose_a_plate(self):
        rows = [_row("a.zip", price=str(price)) for price in (1, 2, 3)]
        signature = conflict_signature(rows)
        self.assertEqual(signature["category"], "price_only")
        self.assertEqual(signature["variants"], 3)
        self.assertEqual(filename_day("AL_D195_43_20200812.zip"), "2020-08-12")
        self.assertEqual(filename_day("no-date.zip"), "")


if __name__ == "__main__":
    unittest.main()
