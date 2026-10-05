import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audit_cheongju_priority_price_mart import price_agrees, proposal, scan_title_addresses


class PriorityReviewTests(unittest.TestCase):
    def test_matching_source_price_does_not_promote_membership(self):
        raw = [{'기준연도':'2026','공시지가':'767,900'}]
        self.assertTrue(price_agrees(raw,2026,'767900.00'))
        result = proposal({'p1','p2'},'synthetic',[],[],True)
        self.assertIsNone(result['proposed_representative_pnu'])
        self.assertFalse(result['production_apply'])
        self.assertEqual(result['candidate_membership_status'],'unverified')

    def test_source_price_year_and_value_are_both_required(self):
        raw = [{'기준연도':'2025','공시지가':'100'}, {'기준연도':'2026','공시지가':'*'}]
        self.assertFalse(price_agrees(raw,2026,100))
        self.assertFalse(price_agrees([{'기준연도':'2026','공시지가':'101'}],2026,100))

    def test_existing_kapt_outside_observed_addresses_is_a_conflict(self):
        result = proposal({'p1','p2'},'synthetic',['synthetic'],['k1'],True)
        self.assertIn('existing_kapt_pnu_outside_observed_transaction_candidates',result['reasons'])
        self.assertIsNone(result['proposed_representative_pnu'])

    def test_kapt_representative_on_one_candidate_does_not_pick_it(self):
        result = proposal({'p1','p2'},'synthetic',['p1'],['k1'],True)
        self.assertNotIn('existing_kapt_pnu_outside_observed_transaction_candidates',result['reasons'])
        self.assertEqual(result['candidate_pnus'],['p1','p2'])
        self.assertIsNone(result['proposed_representative_pnu'])

    def test_two_distinct_kapt_codes_require_membership_review(self):
        result = proposal({'p1','p2'},'synthetic',[],['k1','k2','k1'],False)
        self.assertIn('multiple_kapt_codes_on_observed_addresses',result['reasons'])
        self.assertIn('no_existing_building_attribute_row',result['reasons'])
        self.assertEqual(result['status'],'review_required')

    def test_multiple_legal_dongs_requires_object_partition_review_first(self):
        result = proposal({'p1','p2'},'synthetic',[],[],True,['4311111111','4311122222'])
        self.assertIn('named_object_key_spans_multiple_legal_dongs',result['reasons'])
        self.assertEqual(result['proposed_action'],'review_object_key_partitions_before_representative_change')
        self.assertIsNone(result['proposed_representative_pnu'])

    def test_same_legal_dong_does_not_prove_one_site(self):
        result = proposal({'p1','p2'},'synthetic',[],[],True,['4311111111','4311111111'])
        self.assertNotIn('named_object_key_spans_multiple_legal_dongs',result['reasons'])
        self.assertEqual(result['candidate_membership_status'],'unverified')

    def test_title_scan_preserves_unresolved_source_identity_by_pk(self):
        values=['']*76
        values[0]='pk'; values[7]='원문 건물명'
        values[8:13]=['43111','11111','2','12','0']
        values[35]='단독주택'
        with TemporaryDirectory() as folder:
            path=Path(folder)/'title.txt'
            path.write_text('|'.join(values)+'\n',encoding='utf-8')
            rows,meta=scan_title_addresses(path,{'4311111111100120000'},{'pk'})
        self.assertIsNone(rows['pk'][0]['pnu'])
        self.assertEqual(rows['pk'][0]['raw_identity'][2],'2')
        self.assertEqual(rows['pk'][0]['building_name'],'원문 건물명')
        self.assertEqual(meta['rows'],1)


if __name__=='__main__':
    unittest.main()
