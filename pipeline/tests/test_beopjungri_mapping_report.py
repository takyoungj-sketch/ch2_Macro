"""beopjungri_mapping_report 단위 테스트 — DB 없이 게이트·delta·신규 미매칭."""

from __future__ import annotations

from beopjungri_mapping_report import (
    ProductReport,
    SliceStats,
    aggregate_overall,
    compare_with_previous,
    evaluate_gates,
    find_newly_unmapped,
)


def _sample_report(mapped_pct: float = 99.9, *, cycle_id: str = "202606") -> dict:
    valid = 10_000
    mapped = int(valid * mapped_pct / 100)
    overall = {
        "valid": valid,
        "mapped": mapped,
        "unmapped": valid - mapped,
        "mapped_pct": mapped_pct,
        "needs_review": 50,
    }
    return {
        "cycle_id": cycle_id,
        "overall": overall,
        "products": [
            {"product": "land", **overall},
            {"product": "collective", **overall},
            {"product": "built", **overall},
        ],
        "unmapped_fingerprints": [
            {"product": "built", "address_key": "충청북도|청주시|상당구||"},
        ],
    }


def test_slice_stats_mapped_pct():
    s = SliceStats(valid=1000, mapped=997, needs_review=3)
    assert s.unmapped == 3
    assert s.mapped_pct == 99.7


def test_aggregate_overall_includes_commercial():
    products = [
        ProductReport("land", "land_transactions", SliceStats(100, 100, 0)),
        ProductReport("collective", "collective_transactions", SliceStats(200, 199, 1)),
        ProductReport("built", "built_transactions", SliceStats(300, 298, 2)),
        ProductReport(
            "collective_commercial",
            "collective_commercial_transactions",
            SliceStats(50, 49, 1),
        ),
    ]
    agg = aggregate_overall(products)
    assert agg.valid == 650
    assert agg.mapped == 646


def test_evaluate_gates_pass():
    report = _sample_report(99.9)
    gate = evaluate_gates(report, min_mapped_pct=99.7)
    assert gate["passed"] is True
    assert gate["errors"] == []


def test_evaluate_gates_fail_below_threshold():
    report = _sample_report(99.0)
    gate = evaluate_gates(report, min_mapped_pct=99.7)
    assert gate["passed"] is False
    assert any("전체 매칭률" in e for e in gate["errors"])


def test_compare_with_previous_delta():
    cur = _sample_report(99.8, cycle_id="202606")
    prev = _sample_report(99.9, cycle_id="202605")
    delta = compare_with_previous(cur, prev)
    assert delta["previous_available"] is True
    assert delta["overall_mapped_pct_change_pp"] == -0.1


def test_find_newly_unmapped():
    previous = {
        "unmapped_fingerprints": [
            {"product": "built", "address_key": "old|key|||"},
        ]
    }
    current_groups = [
        {"product": "built", "address_key": "old|key|||", "count": 5, "sample_label": "old"},
        {"product": "built", "address_key": "new|key|||", "count": 10, "sample_label": "new"},
    ]
    new = find_newly_unmapped(current_groups, previous, top_n=10)
    assert len(new) == 1
    assert new[0]["address_key"] == "new|key|||"
    assert new[0]["count"] == 10


def test_compare_without_previous():
    delta = compare_with_previous(_sample_report(), None)
    assert delta["previous_available"] is False
