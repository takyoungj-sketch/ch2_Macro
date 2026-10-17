from collections import Counter

from parcel_master.build_land_trait_slim_v1 import _bounds, _fold

BITS = {"2023-08-03": 0, "2024-01-23": 1, "2025-01-16": 2}


def _row(asof, year, price="1000", zone_label="제2종일반주거지역"):
    return ("1111010100100010000", asof, year, "01",
            "08", "120.5", "13", "", "", "", "", "", price,
            "대", zone_label, "", "", "", "", "")


def test_same_values_across_asofs_fold_into_one_row_with_mask():
    rows = [(_row("2023-08-03", "2023"), False), (_row("2024-01-23", "2023"), False)]
    counts = Counter()
    out = _fold(rows, BITS, Counter(), counts)
    assert len(out) == 1
    assert out[0][2] == 0b011
    assert out[0][3] == 0
    assert counts["observation_keys"] == 2


def test_label_only_conflict_folds_and_marks_conflict_bit():
    rows = [
        (_row("2025-01-16", "2025", zone_label=""), True),
        (_row("2025-01-16", "2025"), True),
        (_row("2024-01-23", "2025"), False),
    ]
    counts = Counter()
    out = _fold(rows, BITS, Counter(), counts)
    assert len(out) == 1
    assert out[0][2] == 0b110
    assert out[0][3] == 0b100
    assert counts["conflict_keys"] == 1
    assert counts["semantic_conflicts"] == 0


def test_different_price_years_stay_separate():
    rows = [(_row("2025-01-16", "2024", price="900"), False), (_row("2025-01-16", "2025"), False)]
    out = _fold(rows, BITS, Counter(), Counter())
    assert sorted(r[0] for r in out) == ["2024", "2025"]


def test_semantic_difference_is_counted():
    rows = [(_row("2025-01-16", "2025", price="900"), True), (_row("2025-01-16", "2025"), True)]
    counts = Counter()
    _fold(rows, BITS, Counter(), counts)
    assert counts["semantic_conflicts"] == 1


def test_bounds():
    assert _bounds("43") == ("4300000000000000000", "4400000000000000000")
    assert _bounds("09") == ("0900000000000000000", "1000000000000000000")
