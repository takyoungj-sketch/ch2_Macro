import unittest
import pandas as pd
from pilot_validation import snapshot_cutoff, encode_category


class PilotValidationTest(unittest.TestCase):
    def test_later_parcel_delays_whole_universe(self):
        rows = {'a': {'trait_asof': '2024-01-01', 'plan_asof': '2024-02-01'},
                'b': {'trait_asof': '2024-03-01', 'plan_asof': '2024-02-01'}}
        self.assertEqual(snapshot_cutoff(rows), '2024-03-01')

    def test_missing_date_cannot_create_false_unique_candidate(self):
        self.assertIsNone(snapshot_cutoff({'a': {'trait_asof': '', 'plan_asof': '2024-02-01'}}))
        self.assertIsNone(snapshot_cutoff({}))

    def test_unseen_uses_estimable_rare_pool(self):
        train, test, audit = encode_category(pd.Series(['A'] * 30 + ['B']), pd.Series(['C']))
        self.assertEqual(test.iloc[0], 'OTHER')
        self.assertIn('OTHER', set(train))
        self.assertEqual(audit['fallback_policy'], 'training_rare_pool')

    def test_no_pool_fallback_is_explicit_and_seen_in_training(self):
        train, test, audit = encode_category(pd.Series(['A'] * 30 + ['B'] * 31), pd.Series(['C']))
        self.assertEqual(test.iloc[0], 'B')
        self.assertIn(test.iloc[0], set(train))
        self.assertEqual(audit['unseen'], 1)
        self.assertEqual(audit['fallback_policy'], 'training_mode_no_estimable_pool')


if __name__ == '__main__':
    unittest.main()
