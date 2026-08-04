# -*- coding: utf-8 -*-
"""Contract/property tests for region_canonical pure resolver (D-028).

DB-free: uses explicit history snapshots only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))

from region_canonical import (  # noqa: E402
    build_history_snapshot,
    expand_to_ledger_codes_pure,
    is_canonical_pure,
    normalize_result_codes_pure,
    resolve_to_canonical_pure,
)

_DAESO_ROWS = (("4377034026", "4377025626", "code_reissue"),)
_YANGJI_ROWS = (("4146136029", "4146126229", "code_reissue"),)
_MERGE_ROWS = (
    ("1111111111", "2222222222", "merge"),
    ("1111111112", "2222222222", "merge"),
)
_SPLIT_ROWS = (("3333333333", "4444444444", "split"),)


def _snap(*row_groups):
    rows = []
    for g in row_groups:
        rows.extend(g)
    return build_history_snapshot(rows)


class TestResolveToCanonicalPure(unittest.TestCase):
    def test_identity_for_unmapped(self):
        snap = _snap()
        self.assertEqual(resolve_to_canonical_pure(snap, ["1234567890"]), ["1234567890"])

    def test_daeso_beopjungri_historical_to_canonical(self):
        snap = _snap(_DAESO_ROWS)
        self.assertEqual(resolve_to_canonical_pure(snap, ["4377034026"]), ["4377025626"])
        self.assertFalse(is_canonical_pure(snap, "4377034026"))
        self.assertTrue(is_canonical_pure(snap, "4377025626"))

    def test_daeso_eup_prefix_historical_to_canonical(self):
        snap = _snap(_DAESO_ROWS)
        self.assertEqual(resolve_to_canonical_pure(snap, ["43770340"]), ["43770256"])

    def test_yangji_eup_prefix(self):
        snap = _snap(_YANGJI_ROWS)
        self.assertEqual(resolve_to_canonical_pure(snap, ["41461360"]), ["41461262"])

    def test_split_not_auto_mapped(self):
        snap = _snap(_SPLIT_ROWS)
        self.assertEqual(resolve_to_canonical_pure(snap, ["3333333333"]), ["3333333333"])

    def test_dedupe_preserves_order(self):
        snap = _snap(_DAESO_ROWS)
        out = resolve_to_canonical_pure(snap, ["4377034026", "4377025626", "4377034026"])
        self.assertEqual(out, ["4377025626"])


class TestExpandToLedgerCodesPure(unittest.TestCase):
    def test_property_canonical_expand_normalize(self):
        snap = _snap(_DAESO_ROWS)
        canonical = ["4377025626"]
        expanded = expand_to_ledger_codes_pure(snap, canonical)
        normalized = resolve_to_canonical_pure(snap, expanded)
        self.assertEqual(normalized, canonical)

    def test_property_historical_in_expand(self):
        snap = _snap(_DAESO_ROWS)
        hist = "4377034026"
        canonical = resolve_to_canonical_pure(snap, [hist])
        expanded = expand_to_ledger_codes_pure(snap, canonical)
        self.assertIn(hist, expanded)

    def test_eup_prefix_expand_includes_historical(self):
        snap = _snap(_DAESO_ROWS)
        expanded = expand_to_ledger_codes_pure(snap, ["43770256"])
        self.assertIn("4377034026", expanded)
        self.assertIn("43770340", expanded)

    def test_merge_multiple_historical(self):
        snap = _snap(_MERGE_ROWS)
        expanded = expand_to_ledger_codes_pure(snap, ["2222222222"])
        self.assertIn("1111111111", expanded)
        self.assertIn("1111111112", expanded)


class TestNormalizeResultCodesPure(unittest.TestCase):
    def test_idempotent(self):
        snap = _snap(_DAESO_ROWS)
        once = normalize_result_codes_pure(snap, ["4377034026", "43770340"])
        twice = normalize_result_codes_pure(snap, once)  # type: ignore[arg-type]
        self.assertEqual(once, twice)

    def test_record_shallow_copy(self):
        snap = _snap(_DAESO_ROWS)
        src = [{"code": "4377034026", "name": "수태리"}]
        out = normalize_result_codes_pure(snap, src)
        self.assertEqual(out[0]["code"], "4377025626")
        self.assertEqual(out[0]["name"], "수태리")
        self.assertEqual(src[0]["code"], "4377034026")

    def test_record_dedupe_by_code(self):
        snap = _snap(_DAESO_ROWS)
        src = [{"code": "4377034026", "n": 1}, {"code": "4377025626", "n": 2}]
        out = normalize_result_codes_pure(snap, src)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["code"], "4377025626")


class TestRegressionFixedPairs(unittest.TestCase):
    def test_daeso_pairs(self):
        snap = _snap(_DAESO_ROWS)
        for hist, canon in (("4377034026", "4377025626"), ("43770340", "43770256")):
            with self.subTest(hist=hist):
                self.assertEqual(resolve_to_canonical_pure(snap, [hist]), [canon])

    def test_yangji_pairs(self):
        snap = _snap(_YANGJI_ROWS)
        for hist, canon in (("4146136029", "4146126229"), ("41461360", "41461262")):
            with self.subTest(hist=hist):
                self.assertEqual(resolve_to_canonical_pure(snap, [hist]), [canon])


if __name__ == "__main__":
    unittest.main()
