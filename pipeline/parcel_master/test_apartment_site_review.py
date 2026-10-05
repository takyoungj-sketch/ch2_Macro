import unittest
from audit_cheongju_apartment_site_review import compare_sites, shadow_gate


class SiteEvidenceTest(unittest.TestCase):
    def site(self, pnu, code, name, approval, road, months):
        return {'pnu':pnu,'kapt_codes':[code] if code else [],'names':[name] if name else [],
                'approval_dates':[approval] if approval else [],'road_addresses':[road] if road else [],
                'contract_months':months,'communal_housing_title_count':1,'title_approval_dates':[approval]}

    def pair(self):
        return (self.site('p1','c1','단지1','19900101','도로1',['2020-01','2021-02']),
                self.site('p2','c2','단지2','19920101','도로2',['2021-02','2022-03']))

    def test_independent_signals_support_but_never_certify(self):
        r=compare_sites(*self.pair())
        self.assertEqual(r['assessment'],'distinct_sites_supported_membership_unverified')
        self.assertEqual(r['common_contract_months'],['2021-02'])
        self.assertFalse(r['physical_membership_certified'])
        self.assertFalse(r['code_change_history_verified'])

    def test_missing_source_evidence_cannot_support(self):
        for field in ('kapt_codes','names','approval_dates','road_addresses'):
            with self.subTest(field=field):
                a,b=self.pair(); b[field]=[]
                self.assertEqual(compare_sites(a,b)['assessment'],'insufficient_or_conflicting_site_evidence')

    def test_shared_code_blocks_distinct_site_signal(self):
        a,b=self.pair(); b['kapt_codes']=['c1','c2']
        self.assertFalse(compare_sites(a,b)['signals']['disjoint_nonempty_kapt_codes'])

    def test_different_codes_alone_do_not_certify_same_address(self):
        a,b=self.pair(); b['names']=a['names']; b['approval_dates']=a['approval_dates']; b['road_addresses']=a['road_addresses']
        self.assertEqual(compare_sites(a,b)['assessment'],'insufficient_or_conflicting_site_evidence')

    def test_disjoint_observation_months_hold_for_history_review(self):
        a,b=self.pair(); b['contract_months']=['2022-01']
        self.assertEqual(compare_sites(a,b)['assessment'],'insufficient_or_conflicting_site_evidence')

    def test_no_communal_housing_titles_hold_for_source_review(self):
        a,b=self.pair(); b['communal_housing_title_count']=0
        self.assertEqual(compare_sites(a,b)['assessment'],'insufficient_or_conflicting_site_evidence')

    def test_unreplayed_approval_dates_require_review(self):
        a,b=self.pair(); b['title_approval_dates']=['20260101']
        self.assertEqual(compare_sites(a,b)['assessment'],'insufficient_or_conflicting_site_evidence')

    def test_shadow_gate_conserves_transactions_without_inheriting_mixed_prices(self):
        r=shadow_gate([{'transactions':3},{'transactions':7}])
        self.assertEqual(r['transactions'],10)
        self.assertEqual(r['address_partitions'],2)
        for field in ('new_object_key','inherited_price_mart','inherited_building_attributes'): self.assertIsNone(r[field])
        self.assertFalse(r['production_apply'])


if __name__=='__main__': unittest.main()
