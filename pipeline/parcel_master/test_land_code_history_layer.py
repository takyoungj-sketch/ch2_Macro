import unittest

from parcel_master.land_code_history_layer import (
    AmbiguousCodeMap,
    add_pair,
    prefix_previous,
    resolve_beopjungri,
)


class CodeHistoryLayerTests(unittest.TestCase):
    def test_before_the_effective_date_uses_the_previous_code(self) -> None:
        pairs: dict[str, tuple[str, str]] = {}
        add_pair(pairs, {}, "5111010100", prefix_previous("5111010100", "42"), "2023-06-11")
        self.assertEqual(resolve_beopjungri("5111010100", "2023-06-10", pairs), ("4211010100", "reissued_1to1"))

    def test_on_the_effective_date_keeps_the_current_code(self) -> None:
        pairs = {"5211110100": ("4511110100", "2024-01-18")}
        self.assertEqual(resolve_beopjungri("5211110100", "2024-01-18", pairs), ("5211110100", "current_code"))

    def test_unknown_or_ambiguous_codes_are_held(self) -> None:
        self.assertEqual(resolve_beopjungri("1211010100", "2019-05-01", {}), ("1211010100", "held"))
        pairs: dict[str, tuple[str, str]] = {}
        owners: dict[str, str] = {}
        add_pair(pairs, owners, "1211010100", "4611010100", "2026-07-01")
        with self.assertRaises(AmbiguousCodeMap):
            add_pair(pairs, owners, "1211010200", "4611010100", "2026-07-01")


if __name__ == "__main__":
    unittest.main()
