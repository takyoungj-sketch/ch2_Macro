from parcel_master.audit_land_trait_prices import price_cause


def plate(year, month, price, asof='2026-07-20'):
    return (asof, year, month, '대', '100.0', frozenset({'1주'}), price)


def test_different_reference_months_are_not_same_period_conflicts():
    assert price_cause([plate(2025, 1, '100'), plate(2025, 7, '110')], 2025) == ('between_reference_months_only', 2025)


def test_same_month_changes_across_observations_are_separate():
    assert price_cause([plate(2025, 1, '100', '2025-03-01'), plate(2025, 1, '110')], 2025) == ('same_reference_month_variation', 2025)


def test_equal_amounts_and_previous_year_fallback():
    assert price_cause([plate(2025, 1, '100'), plate(2025, 7, '100.0')], 2026) == ('not_reproduced', 2025)


def test_current_year_conflict_does_not_fall_back_to_previous_year():
    rows = [plate(2025, 1, '100'), plate(2026, 1, '110'), plate(2026, 7, '120')]
    assert price_cause(rows, 2026) == ('between_reference_months_only', 2026)
