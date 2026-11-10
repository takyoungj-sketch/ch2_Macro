import sys
import unittest
from types import SimpleNamespace

from parcel_master import land_trait_link_rejudge as rejudge

# These modules import pipeline/db_utils as "db_utils". Built tests import
# pipeline/built/db_utils under the same name during collection, so drop the cache.
sys.modules.pop("db_utils", None)


def _row(digest, status="other_unmatched", day="2026-08-01"):
    return {
        "transaction_hash": digest, "contract_date": day, "sigungu_code": "12110",
        "previous_status": status, "previous_rule_version": "V1", "previous_price_status": "none",
        "previous_trait_asof": None, "previous_bjd": "1211010100", "previous_code_resolution": "current_code",
        "previous_lot": None,
    }


def _record(digest, status):
    linked = status in rejudge.LINKED
    return {
        "transaction_hash": digest, "link_status": status,
        "price_status": "same_year" if linked else "none", "official_price_won": 1000 if linked else None,
        "price_year": 2026 if linked else None, "trait_asof": "2026-07-20" if linked else None,
        "ledger_beopjungri_code": "2911010100", "code_resolution": "reissued_1to1",
        "recovered_lot": "1-1" if linked else None,
    }


class PlanTests(unittest.TestCase):
    def test_only_changed_rows_enter_the_plan(self) -> None:
        targets = [_row("a" * 64), _row("b" * 64), _row("c" * 64)]
        judged = {
            "a" * 64: _record("a" * 64, "exact"),
            "b" * 64: _record("b" * 64, "other_unmatched"),
            "c" * 64: _record("c" * 64, "multiple_candidates"),
        }
        plan, moves, _, _ = rejudge.build_plan(targets, judged, rejudge.RULE_VERSION_V2)
        self.assertEqual([p["transaction_hash"] for p in plan], ["a" * 64, "c" * 64])
        self.assertEqual(moves["other_unmatched -> exact"], 1)
        self.assertEqual(plan[0]["previous_status"], "other_unmatched")
        self.assertEqual(plan[0]["new_rule_version"], rejudge.RULE_VERSION_V2)


class ApplyGuardTests(unittest.TestCase):
    def _engine(self, host="localhost", db="land_stats"):
        return SimpleNamespace(url=SimpleNamespace(host=host, database=db))

    def test_new_plate_apply_is_refused(self) -> None:
        with self.assertRaises(rejudge.ApplyRefused):
            rejudge.apply_plan(self._engine(), [{}], target="new_plate", cycle_id="x", applied_by="t",
                               latest_asof="2026-07-20", expect_host="localhost", expect_db="land_stats")

    def test_host_mismatch_is_refused(self) -> None:
        with self.assertRaises(rejudge.ApplyRefused):
            rejudge.apply_plan(self._engine(host="13.209.203.178"), [{}], target="honam_v2", cycle_id="x",
                               applied_by="t", latest_asof="2026-07-20", expect_host="localhost",
                               expect_db="land_stats")

    def test_cli_requires_guards_and_blocks_new_plate(self) -> None:
        parser = rejudge.build_parser()
        for argv in (
            ["--target", "new_plate", "--plate-asof", "2026-07-20", "--apply", "--cycle-id", "x",
             "--expect-host", "h", "--expect-db", "d", "--out", "o.json"],
            ["--target", "honam_v2", "--apply", "--out", "o.json"],
        ):
            args = parser.parse_args(argv)
            with self.assertRaises(SystemExit):
                rejudge.check_args(parser, args)

    def test_mismatched_rowcount_rolls_back(self) -> None:
        class Conn:
            def __init__(self):
                self.calls = 0

            def execute(self, statement, params=None):
                self.calls += 1
                sql = str(statement)
                if "to_regclass" in sql:
                    return SimpleNamespace(scalar=lambda: True)
                return SimpleNamespace(rowcount=1 if "INSERT INTO" in sql else 0)

        class Begin:
            def __init__(self):
                self.conn = Conn()
                self.rolled_back = False

            def __enter__(self):
                return self.conn

            def __exit__(self, kind, value, tb):
                self.rolled_back = kind is not None
                return False

        begin = Begin()
        engine = SimpleNamespace(url=SimpleNamespace(host="localhost", database="land_stats"), begin=lambda: begin)
        with self.assertRaises(rejudge.ApplyRefused):
            rejudge.apply_plan(engine, [{"transaction_hash": "a" * 64}], target="honam_v2", cycle_id="x",
                               applied_by="t", latest_asof="2026-07-20", expect_host="localhost",
                               expect_db="land_stats")
        self.assertTrue(begin.rolled_back)


if __name__ == "__main__":
    unittest.main()
