import unittest
from audit_cheongju_remaining_object_review import review_category, code_context


class RemainingReviewTest(unittest.TestCase):
    def row(self,legal=2,codes=0):return {'distinct_legal_dongs':legal,'decision':{'distinct_kapt_codes':codes}}
    def test_block_addresses_are_not_silently_assigned_parcels(self):
        r=review_category(self.row(),[{'address_identity':['raw','4311112400','BL-B1']}])
        self.assertEqual(r['category'],'development_block_identity_unresolved')
        self.assertIsNone(r['new_representative_pnu'])
        self.assertFalse(r['production_apply'])
    def test_cross_legal_dong_membership_is_still_unverified(self):
        r=review_category(self.row(),[{'address_identity':['pnu','p1']},{'address_identity':['pnu','p2']}])
        self.assertEqual(r['category'],'cross_legal_dong_observed_addresses_membership_review')
        self.assertEqual(r['membership_status'],'unverified')
    def test_shared_parcel_multiple_codes_is_independent_of_cross_dong(self):
        r=review_category(self.row(1,2),[{'address_identity':['pnu','p1']}])
        self.assertEqual(r['category'],'shared_parcel_multiple_management_codes_no_auto_split')
        self.assertIsNone(r['new_object_key'])
    def test_same_approval_is_not_alias_certification(self):
        r=code_context([{'단지코드':'a','사용승인일':'20000101'},{'단지코드':'b','사용승인일':'20000101'}])
        self.assertEqual(r['common_approval_dates_across_codes'],['20000101'])
        self.assertFalse(r['alias_certified']);self.assertFalse(r['auto_merge']);self.assertFalse(r['auto_split'])
    def test_missing_approval_is_not_shared_date(self):
        r=code_context([{'단지코드':'a','사용승인일':'20000101'},{'단지코드':'b','사용승인일':''}])
        self.assertEqual(r['common_approval_dates_across_codes'],[])
    def test_duplicate_basic_rows_preserve_distinct_code_count(self):
        row={'단지코드':'a','사용승인일':'20000101'}
        self.assertEqual(code_context([row,row])['distinct_codes'],1)


if __name__=='__main__':unittest.main()
