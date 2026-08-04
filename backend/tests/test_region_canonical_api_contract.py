# -*- coding: utf-8 -*-
"""API contract: user-facing region codes must be canonical (D-028)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.region_canonical import (
    build_history_snapshot,
    normalize_code,
    normalize_result_codes_pure,
    resolve_to_canonical_pure,
)


def _daeso_snapshot():
    return build_history_snapshot([("4377034026", "4377025626", "code_reissue")])


class TestRegionCanonicalApiContract(unittest.TestCase):
    def test_normalize_code_maps_ledger_historical(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            MagicMock(from_code="4377034026", to_code="4377025626", change_type="code_reissue"),
        ]
        self.assertEqual(normalize_code(conn, "4377034026"), "4377025626")
        self.assertEqual(normalize_code(conn, "43770340"), "43770256")

    def test_lookup_response_never_returns_raw_historical(self):
        snap = _daeso_snapshot()
        raw_from_ledger = "43770340"
        user_facing = resolve_to_canonical_pure(snap, [raw_from_ledger])[0]
        self.assertEqual(user_facing, "43770256")
        self.assertNotEqual(user_facing, raw_from_ledger)

    def test_upper_stats_input_historical_resolves_before_mart_key(self):
        snap = _daeso_snapshot()
        ui_code = "43770340"
        mart_key = resolve_to_canonical_pure(snap, [ui_code])[0]
        self.assertEqual(mart_key, "43770256")

    def test_bulk_stats_kept_codes_are_canonical(self):
        snap = _daeso_snapshot()
        payload_codes = ["4377034026", "4377025626"]
        kept = normalize_result_codes_pure(snap, payload_codes)  # type: ignore[arg-type]
        self.assertEqual(kept, ["4377025626"])


if __name__ == "__main__":
    unittest.main()
