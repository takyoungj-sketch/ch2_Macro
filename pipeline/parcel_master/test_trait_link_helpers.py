import unittest
from trait_link_helpers import area_key, code, lot_matches, unique_rows


class TraitLinkTest(unittest.TestCase):
    def test_rounding_and_invalid_area(self):
        self.assertEqual(area_key('35.05'), '35.1')
        for value in ('NaN', 'Infinity', '', '-1', '0'):
            self.assertIsNone(area_key(value))

    def test_duplicate_does_not_inflate_candidates(self):
        row = {'pnu': '4311110100100010001', 'area': '35'}
        self.assertEqual(len(unique_rows([row, row.copy()])), 1)
        with self.assertRaises(ValueError):
            unique_rows([row, {**row, 'area': '36'}])

    def test_mask_and_mountain_are_separate(self):
        self.assertTrue(lot_matches('4**', '4311110100104420031', '442-31'))
        self.assertFalse(lot_matches('4**', '4311110100204420031', '442-31'))
        self.assertFalse(lot_matches('4*', '4311110100104420031', '442-31'))

    def test_codes_preserve_unknown(self):
        self.assertEqual(code('014'), '14')
        self.assertEqual(code('00'), 'UNKNOWN')
        self.assertEqual(code(''), 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
