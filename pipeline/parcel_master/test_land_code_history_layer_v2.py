import sqlite3
import sys
import unittest
from unittest.mock import patch

from parcel_master import land_trait_link_missing as missing
from parcel_master.land_code_history_layer import resolve_beopjungri
from parcel_master.land_code_history_layer_v2 import (
    FAR_FUTURE,
    RULE_VERSION_V2,
    ledger_generation_pairs,
    missing_prefixes,
)

# These modules import pipeline/db_utils as "db_utils". Built tests import
# pipeline/built/db_utils under the same name during collection, so drop the cache.
sys.modules.pop("db_utils", None)

EFFECTIVE = "2026-07-01"


def _ledger(*pnus: str) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE parcel_observation (pnu TEXT, asof TEXT)")
    db.executemany("INSERT INTO parcel_observation VALUES (?, '2026-07-20')", [(p,) for p in pnus])
    return db


PAIRS = {
    "1211010100": ("2911010100", EFFECTIVE),
    "1211010200": ("2911010200", EFFECTIVE),
    "5111010100": ("4211010100", "2023-06-11"),
}
BRIDGE = {
    "1211010100": ("2911010100", "observed_and_name"),
    "1211010200": ("2911010200", "held_not_1to1"),
}


class LedgerGenerationPairsTests(unittest.TestCase):
    def test_missing_prefix_is_only_the_one_without_parcels(self) -> None:
        db = _ledger("2911010100100010000", "5111010100100010000")
        self.assertEqual(missing_prefixes(PAIRS, db), ["12"])

    def test_confirmed_pair_keeps_previous_code_after_effective_date(self) -> None:
        db = _ledger("2911010100100010000", "5111010100100010000")
        pairs, summary = ledger_generation_pairs(PAIRS, db, BRIDGE)
        self.assertEqual(pairs["1211010100"], ("2911010100", FAR_FUTURE))
        self.assertEqual(resolve_beopjungri("1211010100", "2026-09-01", pairs), ("2911010100", "reissued_1to1"))
        self.assertEqual(summary, {"missing_prefixes": ["12"], "extended_pairs": 1, "held_pairs": 1})

    def test_unconfirmed_pair_behaves_like_v1(self) -> None:
        db = _ledger("2911010100100010000", "5111010100100010000")
        pairs, _ = ledger_generation_pairs(PAIRS, db, BRIDGE)
        self.assertEqual(pairs["1211010200"], PAIRS["1211010200"])
        self.assertEqual(resolve_beopjungri("1211010200", "2026-09-01", pairs), ("1211010200", "current_code"))

    def test_other_generations_are_untouched(self) -> None:
        db = _ledger("2911010100100010000", "5111010100100010000")
        pairs, _ = ledger_generation_pairs(PAIRS, db, BRIDGE)
        self.assertEqual(pairs["5111010100"], PAIRS["5111010100"])

    def test_once_the_ledger_has_new_code_parcels_v2_equals_v1(self) -> None:
        db = _ledger("1211010100100010000", "5111010100100010000")
        pairs, summary = ledger_generation_pairs(PAIRS, db, BRIDGE)
        self.assertEqual(pairs, PAIRS)
        self.assertEqual(summary["missing_prefixes"], [])

    def test_missing_bridge_holds_everything(self) -> None:
        db = _ledger("2911010100100010000")
        pairs, summary = ledger_generation_pairs(PAIRS, db, {})
        self.assertEqual(pairs["1211010100"], PAIRS["1211010100"])
        self.assertEqual(summary["extended_pairs"], 0)


class MonthlyPathTests(unittest.TestCase):
    def test_classify_tags_monthly_records_with_v2(self) -> None:
        captured = {}

        def fake_classify(code, plates, index, pairs, rows, *, conflict_loader, rule_version):
            captured["rule_version"] = rule_version
            return [], {}

        with patch.object(missing.v1, "_classify", side_effect=fake_classify), \
                patch.object(missing, "_ranges", return_value=iter(())):
            missing.classify("12110", [], {}, _ledger())
        self.assertEqual(captured["rule_version"], RULE_VERSION_V2)
        self.assertEqual(RULE_VERSION_V2, "LAND_CODE_HISTORY_LAYER_V2+LAND_LINK_RULE_V1")


if __name__ == "__main__":
    unittest.main()
