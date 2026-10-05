import unittest
from ledger_relationship_policy_shadow import representative_shadow,aggregation_gate


class RelationshipPolicyTests(unittest.TestCase):
    def test_independent_max_pair_cannot_be_promoted(self):
        groups=[{'beopjungri_code':'4311111111','lot_number':'99'},
                {'beopjungri_code':'4311122222','lot_number':'10'}]
        result=representative_shadow(groups,'4311111111100990000','4311122222100990000')
        self.assertIn('stats_address_pair_not_observed',result['reasons'])
        self.assertEqual(len(result['observed_pnu_candidates']),2)
        self.assertIsNone(result['new_representative_assignment'])

    def test_single_address_is_still_a_candidate(self):
        pnu='4311111111100990000'
        result=representative_shadow([{'beopjungri_code':'4311111111','lot_number':'99'}],pnu,pnu)
        self.assertEqual(result['status'],'single_observed_address_candidate')
        self.assertEqual(result['independent_verification'],'unverified')

    def test_roles_and_coaddress_do_not_authorize_sums(self):
        self.assertFalse(aggregation_gate(False,True,True,True,False)['aggregate_allowed'])
        self.assertFalse(aggregation_gate(True,True,False,True,True)['aggregate_allowed'])
        self.assertFalse(aggregation_gate(True,True,True,False,True)['aggregate_allowed'])
        self.assertTrue(aggregation_gate(True,True,True,True,True)['aggregate_allowed'])


if __name__=='__main__': unittest.main()
