import unittest
import hashlib

from audit_cheongju_named_object_mix import classify, shadow_partitions, summarize, key_replay_flags


class NamedObjectMixTests(unittest.TestCase):
    def test_nullable_address_fields_do_not_break_key_replay(self):
        raw='apartment|충청북도|청주시|서원구|name:아파트명'
        row={'asset_type':'apartment','addr1':'충청북도','addr2':'청주시','addr3':'서원구',
             'addr4':'동명','building_name':'아파트명','lot_number':'12','road_name':None,
             'building_key':hashlib.sha256(raw.encode()).hexdigest()}
        self.assertEqual(key_replay_flags([row]),[True])
        self.assertIsNone(row['road_name'])

    def test_one_kapt_code_on_one_address_is_not_a_multi_parcel_site(self):
        r=classify(True,{'4311111111'},{'p1','p2'},{'p1':{'k1'}})
        self.assertEqual(r['evidence_class'],'same_legal_dong_single_kapt_code_partial_coverage_unverified')
        self.assertEqual(r['common_kapt_codes_across_all_observed_pnus'],[])
        self.assertEqual(r['pnus_with_kapt_representative_mapping'],1)

    def test_shared_kapt_code_does_not_certify_membership(self):
        r=classify(True,{'4311111111'},{'p1','p2'},{'p1':{'k1'},'p2':{'k1'}})
        self.assertEqual(r['evidence_class'],'same_legal_dong_shared_kapt_code_multi_parcel_unverified')
        self.assertEqual(r['independent_membership_verification'],'unverified')
        self.assertIsNone(r['new_object_key'])

    def test_cross_legal_dong_multiple_codes_requires_review(self):
        r=classify(True,{'4311111111','4311122222'},{'p1','p2'},{'p1':{'k1'},'p2':{'k2'}})
        self.assertEqual(r['evidence_class'],'cross_legal_dong_multiple_kapt_codes_review')
        self.assertFalse(r['production_apply'])
        self.assertIsNone(r['new_representative_pnu'])

    def test_multiple_codes_on_one_parcel_do_not_trigger_a_split(self):
        r=classify(True,{'4311111111'},{'p1'},{'p1':{'k1','k2'}})
        self.assertEqual(r['distinct_kapt_codes'],2)
        self.assertEqual(r['evidence_class'],'single_or_unparseable_address_not_independently_verified')
        self.assertIsNone(r['new_object_key'])

    def test_unnamed_keys_keep_separate_identity_class(self):
        r=classify(False,{'4311111111','4311122222'},{'p1','p2'},{})
        self.assertEqual(r['evidence_class'],'unnamed_key_separate_address_identity')

    def test_shadow_partitions_preserve_invalid_and_canonical_alias_addresses(self):
        groups=[{'beopjungri_code':'4311111111','lot_number':'12','transactions':2},
                {'beopjungri_code':'4311111111','lot_number':'12-0','transactions':3},
                {'beopjungri_code':'4311111111','lot_number':'1**','transactions':4},
                {'beopjungri_code':None,'lot_number':None,'transactions':1}]
        result=shadow_partitions(groups)
        self.assertEqual(len(result),3)
        self.assertEqual(sum(p['transactions'] for p in result),10)
        self.assertEqual(next(p['transactions'] for p in result if p['address_identity'][0]=='pnu'),5)
        self.assertTrue(all(p['new_object_key'] is None for p in result))

    def test_single_legal_dong_multi_pnu_is_separate_from_cross_dong(self):
        rows=[{'named_key':True,'distinct_legal_dongs':1,'distinct_observed_pnus':2,
               'transaction_count':5,'price_mart_present':True,'existing_attribute_tiers':['T'],
               'stored_stats_address_observed':True,'decision':classify(True,{'b'},{'p1','p2'},{})}]
        r=summarize(rows)
        self.assertEqual(r['named_same_legal_dong_multi_pnu_keys'],1)
        self.assertEqual(r['named_cross_legal_dong_keys'],0)


if __name__=='__main__':
    unittest.main()
