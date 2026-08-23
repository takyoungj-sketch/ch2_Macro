"""표제부 스냅샷 선택·정책 결합."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from built.snapshot_policy import (
    apply_snapshot_policy,
    contract_ym,
    pick_snapshot,
    pick_snapshot_series,
    policy_coverage,
)


SNAPS = ["2024-09", "2025-07", "2026-07"]


def test_pick_snapshot_prefers_latest_past():
    assert pick_snapshot("2022-12", SNAPS) == "2024-09"
    assert pick_snapshot("2025-03", SNAPS) == "2024-09"
    assert pick_snapshot("2025-07", SNAPS) == "2025-07"
    assert pick_snapshot("2026-03", SNAPS) == "2025-07"
    assert pick_snapshot("2026-07", SNAPS) == "2026-07"
    assert pick_snapshot("2026-08", SNAPS) == "2026-07"


def test_pick_snapshot_missing_ym_uses_latest():
    assert pick_snapshot(None, SNAPS) == "2026-07"


def test_pick_snapshot_series_matches_scalar():
    yms = ["2022-12", "2025-03", "2025-07", "2026-08", None]
    got = pick_snapshot_series(pd.Series(yms), SNAPS)
    want = [pick_snapshot(x, SNAPS) for x in yms]
    assert got.tolist() == want


def test_contract_ym_defaults_month_to_june():
    assert contract_ym(2025, None) == "2025-06"
    assert contract_ym(2025, 3) == "2025-03"


def _snap_df(snap: str, parcel: str | None, year: int, month: int, tid: int = 1) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": tid,
                "asset_type": "factory",
                "contract_year": year,
                "contract_month": month,
                "tier": "A1" if parcel else None,
                "fail": None if parcel else "no_gross_match",
                "parcel": parcel,
                "n_range": 10 if parcel else 0,
                "n_exact": 1 if parcel else 0,
            }
        ]
    )


def test_time_picks_2024_for_2022_deal():
    by = {
        "2024-09": _snap_df("2024-09", "x|146-6", 2022, 12),
        "2025-07": _snap_df("2025-07", "x|146-6", 2022, 12),
        "2026-07": _snap_df("2026-07", "x|114-8", 2022, 12),
    }
    latest = apply_snapshot_policy(by, policy="latest", primary="2026-07")
    time = apply_snapshot_policy(by, policy="time", primary="2026-07")
    union = apply_snapshot_policy(by, policy="union", primary="2026-07")
    assert latest.iloc[0]["parcel"] == "x|114-8"
    assert time.iloc[0]["parcel"] == "x|146-6"
    assert time.iloc[0]["snapshot_used"] == "2024-09"
    # 합집합은 146-6 vs 114-8 충돌 → 미상
    assert pd.isna(union.iloc[0]["parcel"]) or union.iloc[0]["parcel"] in (None, "")
    assert union.iloc[0]["fail"] == "snapshot_conflict"


def test_time_fallback_does_not_override_primary_hit():
    """1본이 이미 확정하면 다른 본이 달라도 뒤집지 않는다 (가락동)."""
    by = {
        "2024-09": _snap_df("2024-09", "x|146-6", 2022, 12),
        "2026-07": _snap_df("2026-07", "x|114-8", 2022, 12),
    }
    fb = apply_snapshot_policy(by, policy="time_fallback", primary="2026-07")
    assert fb.iloc[0]["parcel"] == "x|146-6"
    assert fb.iloc[0]["snapshot_via"] == "time"


def test_time_fallback_adopts_unique_other_snap():
    by = {
        "2024-09": _snap_df("2024-09", None, 2022, 12),
        "2026-07": _snap_df("2026-07", "x|99-1", 2022, 12),
    }
    fb = apply_snapshot_policy(by, policy="time_fallback", primary="2026-07")
    assert fb.iloc[0]["parcel"] == "x|99-1"
    assert fb.iloc[0]["snapshot_via"] == "fallback"


def test_time_fallback_conflict_on_miss_only():
    by = {
        "2024-09": _snap_df("2024-09", None, 2022, 12),
        "2025-07": _snap_df("2025-07", "x|1-1", 2022, 12),
        "2026-07": _snap_df("2026-07", "x|2-2", 2022, 12),
    }
    fb = apply_snapshot_policy(by, policy="time_fallback", primary="2026-07")
    assert fb.iloc[0]["fail"] == "snapshot_conflict"
    assert not (isinstance(fb.iloc[0]["parcel"], str) and fb.iloc[0]["parcel"])


def test_policy_coverage_counts_conflict():
    by = {
        "2024-09": _snap_df("2024-09", "x|1-1", 2022, 12),
        "2026-07": _snap_df("2026-07", "x|2-2", 2022, 12),
    }
    union = apply_snapshot_policy(by, policy="union", primary="2026-07")
    cov = policy_coverage(union)
    assert cov["confirmed"] == 0
    assert cov["conflict"] == 1


def test_cli_defaults_are_all_and_time_fallback():
    from built.recover_address import build_parser

    ns = build_parser().parse_args([])
    assert ns.snapshot == "all"
    assert ns.policy == "time_fallback"
