"""built 월간 러너 — skip-enrich 기본, 동결 지문 비교."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_built_cycle_csv import build_parser, should_run_enrich  # noqa: E402
from verify_built_enrichment_freeze import compare_fingerprints, fingerprint  # noqa: E402


def test_enrich_off_by_default():
    ns = build_parser().parse_args(["--cycle-id", "202609"])
    assert ns.enrich is False
    assert ns.skip_enrich is False
    assert should_run_enrich(enrich=ns.enrich, skip_enrich=ns.skip_enrich) is False


def test_enrich_opt_in():
    ns = build_parser().parse_args(["--cycle-id", "202609", "--enrich"])
    assert should_run_enrich(enrich=ns.enrich, skip_enrich=ns.skip_enrich) is True


def test_skip_enrich_wins_over_enrich():
    ns = build_parser().parse_args(["--cycle-id", "202609", "--enrich", "--skip-enrich"])
    assert should_run_enrich(enrich=ns.enrich, skip_enrich=ns.skip_enrich) is False


def test_retry_unmatched_flag_present():
    ns = build_parser().parse_args(["--cycle-id", "202609", "--retry-unmatched"])
    assert ns.retry_unmatched is True


def test_fingerprint_stable():
    assert fingerprint("a|1", "RC", "제2종") == fingerprint("a|1", "RC", "제2종")
    assert fingerprint("a|1", "RC", "제2종") != fingerprint("a|2", "RC", "제2종")


def test_compare_detects_change_and_insert():
    before = {"h1": "aaa", "h2": "bbb"}
    after = {"h1": "aaa", "h2": "ccc", "h3": "ddd"}
    got = compare_fingerprints(before, after)
    assert got["changed"] == 1
    assert got["inserted"] == 1
    assert got["disappeared"] == 0
