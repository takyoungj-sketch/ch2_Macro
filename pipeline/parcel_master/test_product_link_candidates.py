import unittest
from audit_cheongju_product_link_candidates import address_pnu,recovered_pnu,candidate_context


class ProductCandidateTests(unittest.TestCase):
    def test_strict_recovered_identity(self):
        self.assertEqual(recovered_pnu('4311112345|12-0','4311112345'),'4311112345100120000')
        self.assertIsNone(recovered_pnu('4311212345|12','4311112345'))
        self.assertIsNone(address_pnu('4311112345','12345'))
        self.assertIsNone(address_pnu('4311112345','12**'))
        self.assertEqual(address_pnu('4311112345','산12')[10],'2')

    def test_multiple_and_blocked_never_promote(self):
        index={'p':[{'mgmt_pk':'a','ledger_kind':'일반'},{'mgmt_pk':'b','ledger_kind':'집합'}]}
        result=candidate_context('p',index,{'a':'unknown_land_type'})
        self.assertEqual(result['candidate_status'],'single_title_candidate')
        self.assertEqual(result['blocked_title_candidate_pks'],['a'])
        self.assertEqual(result['new_assignment'],'none')
        self.assertEqual(result['independent_match_verification'],'unverified')
        self.assertEqual(candidate_context('p',index,{})['candidate_status'],'multiple_title_candidates')


if __name__=='__main__': unittest.main()
