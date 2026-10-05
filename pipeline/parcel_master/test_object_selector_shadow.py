import copy
import unittest

from audit_cheongju_product_link_candidates import address_pnu
from ledger_object_selector_shadow import select_shadow


class SelectorTests(unittest.TestCase):
    def row(self, lots=('1','2'), codes=0):
        bjd='4311112000';parts=[]
        for lot,n in zip(lots,(3,5)):
            g={'stats_id':1,'building_key':'key','asset_type':'apartment','beopjungri_code':bjd,'lot_number':lot,
               'building_name':'이름','addr1':'충청북도','addr2':'청주시','addr3':'상당구','addr4':'금천동','road_name':'도로', 'transactions':n}
            pnu=address_pnu(bjd,lot)
            identity=['pnu',pnu] if pnu else ['raw',bjd,lot]
            parts.append({'address_identity':identity,'transactions':n,'address_groups':[g]})
        return {'building_key':'key','asset_type':'apartment','stats_id':1,'distinct_legal_dongs':1,
                'transaction_count':sum(p['transactions'] for p in parts),'address_review_partitions':parts,
                'observed_pnus':sorted({p['address_identity'][1] for p in parts if p['address_identity'][0]=='pnu'}),
                'stored_stats_address_observed':True,'baseline_price_mart':{'price':123},'existing_attribute_rows':[{'tier':'C'}],
                'decision':{'independent_membership_verification':'unverified','distinct_kapt_codes':codes}}
    def run_row(self,row,stats=None,coverage=None):
        g=row['address_review_partitions'][0]['address_groups'][0]
        if stats is None:stats=[g['beopjungri_code'],g['lot_number']]
        if coverage is None:coverage={p:'titles_present' for p in row['observed_pnus']}
        return select_shadow(row,stats,coverage)

    def test_multiple_addresses_preserve_all_transactions_and_block_enrichment(self):
        r=self.run_row(self.row())
        self.assertEqual(r['status'],'object_scope_review_hold');self.assertEqual(r['transactions'],8)
        self.assertEqual(len(r['candidates']),2)
        for f in ('new_object_key','selected_observed_pair','new_representative_pnu','inherited_price_mart','inherited_building_attributes'):self.assertIsNone(r[f])
        self.assertFalse(r['production_apply'])
    def test_unobserved_component_max_pair_never_becomes_candidate(self):
        row=self.row(('99','10'));g=row['address_review_partitions'][1]['address_groups'][0]
        g['beopjungri_code']='4311112400'
        row['address_review_partitions'][1]['address_identity'][1]=address_pnu(g['beopjungri_code'],'10')
        row['observed_pnus']=sorted(p['address_identity'][1] for p in row['address_review_partitions'])
        row['distinct_legal_dongs']=2;row['stored_stats_address_observed']=False
        r=self.run_row(row,['4311112400','99'])
        self.assertIn('stored_stats_address_pair_not_observed',r['reasons'])
        self.assertNotIn(['4311112400','99'],[p['raw_pair'] for c in r['candidates'] for p in c['observed_pairs']])
    def test_single_address_is_not_membership_certification(self):
        r=self.run_row(self.row(('1',)))
        self.assertEqual(r['status'],'observed_only');self.assertIsNone(r['new_representative_pnu'])
        self.assertFalse(r['membership_verifier_implemented'])
    def test_shared_parcel_codes_do_not_auto_split(self):
        r=self.run_row(self.row(('1',),2))
        self.assertEqual(r['status'],'shared_parcel_management_review');self.assertIsNone(r['new_object_key'])
    def test_raw_block_address_is_retained(self):
        r=self.run_row(self.row(('BL-B1',)))
        self.assertEqual(r['status'],'development_block_identity_unresolved');self.assertEqual(r['transactions'],3)
        self.assertEqual(r['candidates'][0]['observed_pairs'][0]['raw_pair'],['4311112000','BL-B1'])
    def test_alias_lots_preserve_both_raw_pairs_under_one_pnu(self):
        row=self.row(('12','12-0'));a,b=row['address_review_partitions']
        a['address_groups']+=b['address_groups'];a['transactions']+=b['transactions'];row['address_review_partitions']=[a]
        r=self.run_row(row)
        self.assertEqual(len(r['candidates']),1);self.assertEqual(r['transactions'],8)
        self.assertEqual({p['raw_pair'][1] for p in r['candidates'][0]['observed_pairs']},{'12','12-0'})
    def test_input_order_does_not_change_decisions_or_candidate_order(self):
        row=self.row();r=self.run_row(row,stats=['4311112000','1'])
        row['address_review_partitions'].reverse()
        self.assertEqual(self.run_row(row,stats=['4311112000','1']),r)
    def test_input_baselines_remain_unchanged(self):
        row=self.row();before=copy.deepcopy(row);self.run_row(row);self.assertEqual(row,before)
    def test_output_baselines_cannot_mutate_input_evidence(self):
        row=self.row();before=copy.deepcopy(row);r=self.run_row(row)
        r['baseline']['price_mart']['price']=999;r['baseline']['attribute_rows'][0]['tier']='changed'
        self.assertEqual(row,before)
    def test_caller_verified_label_is_rejected_without_source_verifier(self):
        row=self.row();row['decision']['independent_membership_verification']='membership_verified'
        with self.assertRaisesRegex(ValueError,'Source-specific'):self.run_row(row)
    def test_declared_pnu_without_observed_pair_is_rejected(self):
        row=self.row();row['address_review_partitions'][0]['address_identity'][1]=address_pnu('4311112400','999')
        with self.assertRaises(ValueError):self.run_row(row)
    def test_duplicate_groups_and_partitions_are_rejected(self):
        row=self.row();row['address_review_partitions'].append(copy.deepcopy(row['address_review_partitions'][0]))
        with self.assertRaises(ValueError):self.run_row(row)
        row=self.row();p=row['address_review_partitions'][0];p['address_groups'].append(copy.deepcopy(p['address_groups'][0]))
        with self.assertRaises(ValueError):self.run_row(row)
    def test_counts_and_cross_asset_or_window_rows_are_rejected(self):
        for field,value in [('asset_type','rowhouse'),('stats_id',2),('transactions',True),('transactions',-1)]:
            with self.subTest(field=field,value=value):
                row=self.row();row['address_review_partitions'][0]['address_groups'][0][field]=value
                with self.assertRaises(ValueError):self.run_row(row)
        row=self.row();row['transaction_count']=9
        with self.assertRaises(ValueError):self.run_row(row)
    def test_absent_and_unreviewed_sources_are_distinct(self):
        row=self.row(('1',));pnu=row['observed_pnus'][0]
        a=self.run_row(row,coverage={pnu:'no_titles_in_latest_snapshot'});b=self.run_row(row,coverage={})
        self.assertIn('latest_title_source_coverage_missing',a['reasons']);self.assertIn('title_source_not_reviewed',b['reasons'])
        self.assertNotIn('latest_title_source_coverage_missing',b['reasons'])
    def test_commercial_cluster_bypasses_residential_split_rules(self):
        r=select_shadow({'product_key':'cluster'},[],{},'road_cluster')
        self.assertEqual(r['status'],'keep_existing_cluster_identity');self.assertFalse(r['residential_scope_rules_applied'])


if __name__=='__main__':unittest.main()
