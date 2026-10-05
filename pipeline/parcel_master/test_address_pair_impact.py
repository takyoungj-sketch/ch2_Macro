import unittest

from audit_cheongju_address_pair_impact import classify_row, build_report, queries


class AddressPairImpactTests(unittest.TestCase):
    def stats(self, **extra):
        return {'id': 1, 'product_key': 'key', 'asset_type': 'rowhouse',
                'window_years': 7, 'as_of_month': '2026-09-01',
                'stored_count': 2, 'beopjungri_code': '4311122222',
                'lot_number': '99', **extra}

    def group(self, bjd, lot, **extra):
        return {'beopjungri_code': bjd, 'lot_number': lot,
                'max_beopjungri_code': '4311122222', 'max_lot_number': '99',
                'transactions': 1, 'district_codes': ['43111'], **extra}

    def test_synthetic_pair_without_price_mart_is_detected(self):
        groups = [self.group('4311111111', '99'), self.group('4311122222', '10')]
        row = classify_row('residential', self.stats(), groups)
        self.assertIn('stored_address_tuple_not_observed', row['flags'])
        self.assertIn('component_max_tuple_not_observed', row['flags'])
        self.assertTrue(row['component_max_reproduces_stored'])
        self.assertEqual(row['distinct_observed_cheongju_pnus'], 2)
        self.assertIsNone(row['new_representative_assignment'])

    def test_observed_raw_tuple_does_not_certify_a_parcel(self):
        row = classify_row('residential', self.stats(lot_number='9**'), [
            self.group('4311122222', '9**', transactions=2, max_lot_number='9**')])
        self.assertTrue(row['stored_tuple_observed'])
        self.assertIn('stored_address_not_strictly_parseable_as_cheongju_pnu', row['flags'])
        self.assertEqual(row['independent_membership_verification'], 'unverified')

    def test_price_mart_on_synthetic_address_is_flagged_without_replacement(self):
        groups = [self.group('4311111111', '99'), self.group('4311122222', '10')]
        row = classify_row('residential', self.stats(representative_pnu='4311122222100990000'), groups)
        self.assertIn('price_mart_uses_unobserved_stats_pnu', row['flags'])
        self.assertIsNone(row['new_representative_assignment'])
        safe = classify_row('residential', self.stats(representative_pnu='4311111111100990000'), groups)
        self.assertNotIn('price_mart_uses_unobserved_stats_pnu', safe['flags'])

    def test_no_transactions_is_not_a_synthetic_max_error(self):
        row = classify_row('residential', self.stats(), [])
        self.assertIsNone(row['component_max_reproduces_stored'])
        self.assertNotIn('component_max_tuple_not_observed', row['flags'])
        self.assertIn('no_current_eligible_window_transactions', row['flags'])

    def test_current_drift_is_separate_from_max_reproduction(self):
        row = classify_row('residential', self.stats(stored_count=3, lot_number='88'), [
            self.group('4311122222', '99', transactions=2)])
        self.assertFalse(row['component_max_reproduces_stored'])
        self.assertTrue(row['component_max_tuple_observed'])
        self.assertIn('stored_count_differs_from_current_eligible_count', row['flags'])

    def test_cross_district_key_is_not_forced_into_one_district(self):
        row = classify_row('residential', self.stats(), [
            self.group('4311122222', '99', transactions=2, district_codes=['43111', '43112'])])
        self.assertEqual(row['district'], 'multiple_districts')

    def test_windows_do_not_inflate_consumer_key_count(self):
        group = [self.group('4311122222', '99', transactions=2)]
        a = classify_row('residential', self.stats(), group)
        b = classify_row('residential', self.stats(id=2, window_years=1), group)
        p = build_report({'residential': [b, a]}, {})['products']['residential']
        self.assertEqual(p['all_latest_windows']['stats_rows'], 2)
        self.assertEqual(p['latest_longest_window']['stats_rows'], 1)
        self.assertEqual(p['latest_longest_window']['unique_product_keys'], 1)

    def test_commercial_compares_road_tuple_without_assigning_pnu(self):
        stats = self.stats(addr1='충북', addr2='청주시', addr3='A동', addr4='B리', road_name='로')
        groups = [{'addr1': '충북', 'addr2': '청주시', 'addr3': 'A동', 'addr4': 'A리', 'road_name': '로',
                   'max_addr1': '충북', 'max_addr2': '청주시', 'max_addr3': 'A동',
                   'max_addr4': 'B리', 'max_road_name': '로', 'transactions': 1, 'district_codes': ['43111']},
                  {'addr1': '충북', 'addr2': '청주시', 'addr3': '0동', 'addr4': 'B리', 'road_name': '로',
                   'max_addr1': '충북', 'max_addr2': '청주시', 'max_addr3': 'A동',
                   'max_addr4': 'B리', 'max_road_name': '로', 'transactions': 1, 'district_codes': ['43111']}]
        row = classify_row('commercial', stats, groups)
        self.assertIn('component_max_tuple_not_observed', row['flags'])
        self.assertNotIn('strict_stats_pnu', row)
        self.assertIsNone(row['new_representative_assignment'])

    def test_query_keeps_outside_city_members_of_city_keys(self):
        for product in ('residential', 'commercial'):
            _, sql = queries(product)
            eligible = sql.split('eligible AS MATERIALIZED (', 1)[1].split('), grouped AS', 1)[0]
            self.assertNotIn(':districts', eligible)
            self.assertIn('t.is_valid=true', eligible)
            self.assertIn('t.unit_price>0', eligible)
            self.assertIn('BETWEEN s.period_start AND s.period_end', sql)


if __name__ == '__main__':
    unittest.main()
