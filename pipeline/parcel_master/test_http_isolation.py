import copy
import unittest

from ledger_http_isolation import annual_counts,fixture_rows,pagination_check,table_name


class HTTPIsolationTests(unittest.TestCase):
    def test_table_names_are_closed_allowlist(self):
        self.assertEqual(table_name('built_transactions'),'built_transactions')
        for name in ('public.built_transactions','built_transactions; DROP TABLE x','unrelated'):
            with self.assertRaises(ValueError):table_name(name)

    def test_pagination_rejects_lost_or_repeated_asset_keys(self):
        rows=[{'building_key':'shared','asset_type':'apartment'},{'building_key':'shared','asset_type':'officetel'}]
        self.assertTrue(pagination_check(rows,2,'building_key'))
        with self.assertRaises(ValueError):pagination_check(rows,3,'building_key')
        with self.assertRaises(ValueError):pagination_check([rows[0],rows[0]],2,'building_key')

    def test_annual_gate_counts_do_not_merge_asset_pairs(self):
        rows=[{'building_key':'shared','asset_type':asset,'contract_year':2026} for asset in ('apartment','apartment','officetel')]
        self.assertEqual(annual_counts(rows),[
            {'building_key':'shared','asset_type':'apartment','contract_year':2026,'count':2},
            {'building_key':'shared','asset_type':'officetel','contract_year':2026,'count':1}])

    def test_fixture_replacement_keeps_frozen_baseline_and_original_metadata(self):
        old={'building_key':'a','asset_type':'apartment','snapshot_ym':'202607','households':1,'match_rule':'title_pnu'}
        price={'building_key':'a','asset_type':'apartment','assessed_land_price':'100.00','assessed_land_price_year':2026,'representative_pnu':'old'}
        frozen={'collective':{'attributes':[old],'prices':[price],'residential_stats':[],
               'residential_transactions':[],'commercial_stats':[],'commercial_transactions':[]},'built':{'transactions':[]}}
        paired={'residential':[{'stats':{'building_key':'a','asset_type':'apartment'},
                  'compatible_attributes':{**old,'households':2},'compatible_price':'100.000'}],'built':[]}
        before=copy.deepcopy(frozen)
        compatible,_=fixture_rows(frozen,paired,'compatible',[])
        self.assertEqual(compatible['collective_building_attributes'][0]['households'],2)
        self.assertEqual(compatible['collective_building_assessed_land_price'][0]['representative_pnu'],'old')
        self.assertEqual(frozen,before)
        with self.assertRaises(ValueError):fixture_rows(frozen,paired,'invalid',[])
