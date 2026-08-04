# -*- coding: utf-8 -*-
"""upper_stats 연도별 쿼리 — canonical eup → historical ledger prefix (D-028)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.region_canonical import build_history_snapshot, expand_to_ledger_codes_pure
from app.routers.upper_stats import _ledger_prefixes_for_level, _tx_where_for_level


class TestUpperStatsLedgerExpand(unittest.TestCase):
    def test_daeso_canonical_includes_historical_eup_prefix(self):
        snap = build_history_snapshot([("4377034026", "4377025626", "code_reissue")])
        expanded = expand_to_ledger_codes_pure(snap, ["43770256"])
        prefixes = sorted({c[:8] for c in expanded if len(c) >= 8})
        self.assertIn("43770256", prefixes)
        self.assertIn("43770340", prefixes)

    def test_ledger_prefixes_for_level_eupmyeondong(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            MagicMock(from_code="4377034026", to_code="4377025626", change_type="code_reissue"),
        ]
        prefixes = _ledger_prefixes_for_level(conn, "eupmyeondong", "43770256")
        self.assertIn("43770256", prefixes)
        self.assertIn("43770340", prefixes)

    def test_tx_where_uses_any_for_expanded_codes(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            MagicMock(from_code="4377034026", to_code="4377025626", change_type="code_reissue"),
        ]
        where, params = _tx_where_for_level(conn, "eupmyeondong", "43770256")
        self.assertIn("ANY(:tx_codes)", where)
        self.assertIn("43770340", params["tx_codes"])
        self.assertIn("43770256", params["tx_codes"])


if __name__ == "__main__":
    unittest.main()
