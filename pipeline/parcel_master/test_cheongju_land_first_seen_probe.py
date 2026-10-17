import unittest

from parcel_master.cheongju_land_first_seen_probe import classify_presence


PNU = "4311110100100120000"


class PresenceTests(unittest.TestCase):
    def test_absent_conflict_and_held_are_separate(self):
        self.assertEqual(classify_presence(PNU, "2020-06-01", ["2024-07-30"], []), "absent_before_contract")
        self.assertEqual(
            classify_presence(PNU, "2020-06-01", ["2024-07-30"], ["2024-08-01"]),
            "conflict_only_after_contract",
        )
        self.assertEqual(
            classify_presence(PNU, "2020-06-01", ["2024-07-30"], ["2019-08-08"]),
            "conflict_precontract",
        )
        self.assertEqual(
            classify_presence(PNU, "2020-06-01", ["2019-08-08"], ["2018-07-31"]),
            "clean_precontract",
        )
        self.assertEqual(
            classify_presence("4311110100100000000", "2020-06-01", ["2024-07-30"], []),
            "noncanonical_zero_main_lot",
        )


if __name__ == "__main__":
    unittest.main()
