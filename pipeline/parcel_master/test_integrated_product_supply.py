import unittest
from compare_cheongju_integrated_product_supply import compare_price


class PriceComparisonTests(unittest.TestCase):
    def test_equal_numbers_do_not_hide_different_year(self):
        self.assertEqual(compare_price({'assessed_land_price_year':2025,'assessed_land_price':'100'},
                         {'price_year':2026,'raw_price':'100','status':'positive_known_year'}),
                         'different_price_year_not_comparable')

    def test_unavailable_source_does_not_reuse_existing_price(self):
        baseline={'assessed_land_price_year':2026,'assessed_land_price':'100'}
        for candidate in (None, {'status':'unknown_price_year'}):
            self.assertEqual(compare_price(baseline,candidate),'selected_source_price_unavailable')

    def test_decimal_comparison_and_invalid_prices(self):
        baseline={'assessed_land_price_year':2026,'assessed_land_price':'100.00'}
        source={'price_year':2026,'raw_price':'100','status':'positive_known_year'}
        self.assertEqual(compare_price(baseline,source),'same_year_equal')
        self.assertEqual(compare_price(baseline,{**source,'raw_price':'101'}),'same_year_changed')
        self.assertEqual(compare_price({**baseline,'assessed_land_price':'NaN'},source),'invalid_existing_or_source_price')
