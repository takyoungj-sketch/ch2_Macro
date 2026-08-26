"""집합 월간 러너 — skip-enrich 기본."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_collective_cycle_csv import build_parser, should_run_enrich  # noqa: E402


def test_enrich_off_by_default():
    ns = build_parser().parse_args(["--cycle-id", "202609"])
    assert ns.enrich_new_keys is False
    assert should_run_enrich(enrich_new_keys=ns.enrich_new_keys, skip_enrich=ns.skip_enrich) is False


def test_enrich_new_keys_opt_in():
    ns = build_parser().parse_args(["--cycle-id", "202609", "--enrich-new-keys"])
    assert should_run_enrich(enrich_new_keys=ns.enrich_new_keys, skip_enrich=ns.skip_enrich) is True


def test_skip_wins():
    ns = build_parser().parse_args(["--cycle-id", "202609", "--enrich-new-keys", "--skip-enrich"])
    assert should_run_enrich(enrich_new_keys=ns.enrich_new_keys, skip_enrich=ns.skip_enrich) is False


def test_refresh_flags_are_parsed_for_runner_reject():
    t = build_parser().parse_args(["--cycle-id", "202609", "--refresh-title-t"])
    assert t.refresh_title_t is True
    p = build_parser().parse_args(["--cycle-id", "202609", "--refresh-land-price"])
    assert p.refresh_land_price is True
