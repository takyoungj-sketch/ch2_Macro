"""집합상가 cluster 1층=100. 가격 원자료 없음."""
from __future__ import annotations

from app.shop_floor_lab.ratio import (
    cell_stats,
    opened_bins,
    rows_to_clusters,
    summarize_f2_by_n1,
    summarize_profile,
)
import pandas as pd


def _bin(key, bin_name, n_bin, med, addr1="서울특별시", addr3="강남구", addr4="역삼동"):
    return {
        "cluster_key": key,
        "bin": bin_name,
        "n_bin": n_bin,
        "med": med,
        "addr1": addr1,
        "addr3": addr3,
        "addr4": addr4,
    }


def test_f1_100_and_thin_bin_dropped():
    rows = [
        _bin("a", "f1", 10, 1000),
        _bin("a", "f2", 10, 820),
        _bin("a", "low", 10, 700),
        _bin("a", "mid", 3, 500),
    ]
    # 10+10+10+3 = 33 < 50, so pad with more f1 counts via another bin
    rows.append(_bin("a", "high", 20, 600))
    clusters = rows_to_clusters(rows)
    assert len(clusters) == 1
    row = clusters[0]
    assert row["idx_f2"] == 82
    assert row["idx_low"] == 70
    assert row["idx_mid"] is None
    assert row["idx_high"] == 60
    assert row["tier"] == "metro"
    assert row["n1_band"] == "n1_10_19"
    assert "med" not in row


def test_phase2_opens_only_when_both_weights_and_iqr_are_below_100():
    below = pd.DataFrame(
        [{"n": 50, "idx_f2": 80, "idx_low": None, "idx_mid": None, "idx_high": None, "idx_ultra": None}]
        * 30
    )
    opened = cell_stats(below, "idx_f2")
    assert opened["phase2_open"] is True
    assert opened["p75"] < 100

    wide = pd.DataFrame([{"n": 50, "idx_f2": 90}] * 20 + [{"n": 50, "idx_f2": 130}] * 10)
    flat = cell_stats(wide, "idx_f2")
    assert flat["equal"] < 100
    assert flat["iqr_excludes_100"] is False
    assert flat["phase2_open"] is False

    mixed = pd.DataFrame(
        [{"n": 50, "idx_f2": 80}] * 29 + [{"n": 5000, "idx_f2": 120}]
    )
    split = cell_stats(mixed, "idx_f2")
    assert split["equal"] < 100
    assert split["weighted"] > 100
    assert split["phase2_open"] is False
    assert opened_bins([{"bin": "f2", "phase2_open": False}]) == []


def test_f2_split_by_first_floor_count():
    clusters = []
    for i, n_f1 in enumerate([6, 12, 25]):
        clusters.append(
            {
                "cluster_key": f"c{i}",
                "n": 80,
                "n_f1": n_f1,
                "n1_band": {6: "n1_5_9", 12: "n1_10_19", 25: "n1_20"}[n_f1],
                "tier": "metro",
                "idx_f2": 70 + i,
            }
        )
    # need 30 in one band for phase2 flag, but this test only checks the split exists
    rows = summarize_f2_by_n1(clusters * 10)
    by = {r["n1_band"]: r["equal"] for r in rows}
    assert by["n1_5_9"] == 70
    assert by["n1_10_19"] == 71
    assert by["n1_20"] == 72


def test_profile_does_not_use_a_ten_point_bar():
    clusters = [
        {
            "n": 50,
            "idx_f2": 95,
            "idx_low": 95,
            "idx_mid": 95,
            "idx_high": 95,
            "idx_ultra": 95,
        }
        for _ in range(30)
    ]
    profile = summarize_profile(clusters)
    f2 = next(r for r in profile if r["bin"] == "f2")
    assert f2["equal"] == 95
    assert f2["phase2_open"] is True
