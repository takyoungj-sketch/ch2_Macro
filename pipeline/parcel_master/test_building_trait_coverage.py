import unittest

import pandas as pd

from pilot_cheongju_building_trait_coverage import summarize


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.pnu = '4311110100100010000'
        self.other = '4311110100100020000'
        self.traits = pd.DataFrame([{'pnu': self.pnu, 'price': '0'}])

    def frame(self, entries):
        return pd.DataFrame(entries, columns=['mgmt_pk', 'pnu', 'beopjungri_code'])

    def test_multiple_buildings_do_not_duplicate_price_parcels(self):
        frame = self.frame([('a', self.pnu, self.pnu[:10]), ('b', self.pnu, self.pnu[:10])])
        result, _, _ = summarize(frame, self.traits)
        self.assertEqual(result['building_rows_matched'], 2)
        self.assertEqual(result['matched_parcels'], 1)
        self.assertEqual(result['matched_parcels_without_positive_price'], 1)
        self.assertEqual(result['parcels_with_multiple_management_pks'], 1)

    def test_identity_conflict_cannot_match_existing_pnu(self):
        frame = self.frame([('a', self.pnu, '4311210100'), ('b', 'bad', '4311110100'),
                            ('c', self.other, self.other[:10])])
        result, matched, unmatched = summarize(frame, self.traits)
        self.assertFalse(matched.any())
        self.assertEqual(int(unmatched.sum()), 1)
        self.assertEqual(result['invalid_pnu_rows'], 1)
        self.assertEqual(result['pnu_bjd_conflict_rows'], 1)
        self.assertEqual(result['valid_identity_unmatched_rows'], 1)

    def test_absent_building_group_has_no_fabricated_rate(self):
        result, _, _ = summarize(self.frame([]), self.traits)
        self.assertIsNone(result['parcel_match_pct'])
        self.assertEqual(result['matched_parcels'], 0)


if __name__ == '__main__':
    unittest.main()
