import copy
import unittest
from cheongju_numeric_supply_shadow import FIELDS, candidate_replay, compatibility_attributes, equal_value, projected_attributes, strict_pnu, value_contract
from extend_cheongju_product_fields import product_row
from parcel_master.paths import TITLE_COLS


class NumericSupplyTests(unittest.TestCase):
    def test_compatibility_uses_source_values_without_changing_numeric_scale(self):
        old={k:2 for k in FIELDS};old['parking_per_household']='2.000';old['structure_group']='RC'
        candidate={k:2 for k in FIELDS};candidate['structure_group']='RC'
        projected,used=compatibility_attributes(old,candidate,'title_numeric_equal',False)
        self.assertTrue(used);self.assertEqual(projected,old);self.assertEqual(projected['parking_per_household'],'2.000')
        preserved,used=compatibility_attributes(old,candidate,'title_numeric_equal',True)
        self.assertFalse(used);self.assertEqual(preserved,old)
        with self.assertRaises(ValueError):
            compatibility_attributes(old,{**candidate,'households':3},'title_numeric_equal',False)
    def test_zero_main_lot_and_cross_city_are_rejected(self):
        self.assertIsNone(strict_pnu('4311112000','0'))
        self.assertIsNone(strict_pnu('1111012000','12'))
        self.assertEqual(strict_pnu('4311112000','산12-3'),'4311112000200120003')
        fields={k:'' for k in TITLE_COLS};fields.update(sigungu_code='43111',bjd_code='12000',plat_gb='0',bun='0',ji='0')
        with self.assertRaises(ValueError):product_row(fields,'2026-07')

    def test_officetel_households_and_parking_keep_original_meaning(self):
        fields={k:'' for k in TITLE_COLS}
        fields.update(pk='a',ledger_kind='집합',sigungu_code='43111',bjd_code='12000',plat_gb='0',bun='12',ji='0',
                      main_purpose='업무시설',purpose_detail='오피스텔',households='0',ho_cnt='7',
                      park_mech_in='2',park_mech_out='3',park_self_in='4',park_self_out='5',
                      floors_above='10',approve_date='20200101',struct_name='철근콘크리트구조')
        original=copy.deepcopy(fields);row=product_row(fields,'2026-07')
        self.assertEqual(row['households'],0);self.assertEqual(row['ho_cnt'],7)
        projection=projected_attributes([row],'officetel')
        self.assertEqual(projection['households'],7);self.assertEqual(projection['parking_total'],14)
        self.assertEqual(projection['parking_per_household'],2)
        self.assertEqual(fields,original)

    def test_review_hold_never_substitutes_or_mutates_baseline(self):
        old={'households':1,'match_rule':'title_pnu'};candidate={k:2 for k in FIELDS}
        result=candidate_replay(old,candidate,'title_numeric_changed',True)
        self.assertEqual(result,old);result['households']=3;self.assertEqual(old['households'],1)
        self.assertEqual(candidate_replay(old,candidate,'retain_existing_non_title_pnu_source',False),old)
        self.assertEqual(candidate_replay(old,candidate,'title_numeric_equal',False),old)

    def test_candidate_cannot_inject_a_new_identity(self):
        with self.assertRaises(ValueError):
            candidate_replay({'households':1},{**{k:2 for k in FIELDS},'building_key':'new'},'title_numeric_changed',False)

    def test_numeric_comparison_and_contract_do_not_promote_usage(self):
        self.assertTrue(equal_value('100.00',100));self.assertFalse(equal_value(None,0))
        self.assertFalse(equal_value('Infinity','Infinity'))
        v=value_contract({'households':3},{'sha256':'a'*64},None,'unverified','release')
        self.assertFalse(any(v['permissions'][flag] for flag in ('product_enrichment','quantity_aggregation','regression')))
