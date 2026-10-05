import unittest
from ledger_trait_input_extension import FIELDS, trait_input
from ledger_staging import attributes
from building_source_staging_v2 import digest


class TraitInputTests(unittest.TestCase):
    def test_blank_label_and_raw_code_preserved(self):
        raw=dict.fromkeys(FIELDS,''); pnu='4311112345100120000'
        raw.update(pnu=pnu,bjd=pnu[:10],jimok_code='001',zone1_code='0',price='****')
        value=attributes(raw); value.pop('price')
        result=trait_input('canonical_address',pnu,raw,digest(value))
        self.assertEqual(result['raw'],raw)
        self.assertEqual(result['raw']['jimok_code'],'001')
        self.assertEqual(result['raw']['jimok_label'],'')
        with self.assertRaises(ValueError): trait_input('canonical_address',pnu,raw,'a'*64)

    def test_identity_blocked_cannot_use_offered_trait(self):
        result=trait_input('unknown_land_type',None,{'price':'999'},'a'*64)
        self.assertIsNone(result['raw'])


if __name__=='__main__': unittest.main()
