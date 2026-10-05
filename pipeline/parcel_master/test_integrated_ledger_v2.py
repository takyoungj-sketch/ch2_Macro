import copy
import unittest

from ledger_identity_v2 import VERSION, identify
from integrated_ledger_v2 import NAMESPACE, connect, consumer, fingerprint, ingest, restore


class IntegratedTests(unittest.TestCase):
    def test_original_pk_and_processed_snapshot_must_match_release(self):
        for field,value in [('mgmt_pk','different'),('snapshot','2025-07')]:
            db=connect(':memory:');b,p=self.inputs();b['a']['attributes'][field]=value
            with self.assertRaises(ValueError):
                ingest(db,'bad',1,b,p,self.manifest(b,p))
            self.assertEqual(db.execute('SELECT count(*) FROM release').fetchone()[0],0)
        db=connect(':memory:');b,p=self.inputs();b['a']['raw']['mgmt_pk']='different'
        with self.assertRaises(ValueError):
            ingest(db,'bad',1,b,p,self.manifest(b,p))

    def inputs(self, gb='0', bun='12', price='100', year='2026'):
        raw = {'raw_identity_fields':['43111','12000',gb,bun,'0'],
               'raw_gross_area':'20.00','raw_title_area':'10','main_aux_code':'0'}
        b = {'a': {'raw':raw,'attributes':{'gross_area':'20','title_land_area':'10'}}}
        pnu = '4311112000100120000'
        traits = {pnu:{'raw':{'pnu':pnu,'bjd':pnu[:10],'year':year,'price':price,
                             'area':'10','trait_asof':'2026-05-13'}}}
        return b, traits

    def manifest(self, b, p, snapshot='2026-07'):
        return {'identity_rule':VERSION,'pk_namespace':NAMESPACE,'title_snapshot':snapshot,
                'trait_year':2026,'expected_buildings':len(b),'expected_traits':len(p),
                'districts':['43111','43112','43113','43114'],
                'sources':{k:{'sha256':str(i)*64,'base_date':None,'collected_at':None}
                           for i,k in enumerate(['title','traits','processed_building'],1)}}

    def setup_release(self, **kwargs):
        db=connect(':memory:');b,p=self.inputs(**kwargs);m=self.manifest(b,p)
        ingest(db,'first',1,b,p,m);return db,b,p,m

    def test_identity_rule_exceptions_preserve_originals(self):
        for gb,bun,state in [('0','0000','noncanonical_zero_main_lot'),('2','12','block_without_canonical_pnu'),
                             ('9','12','unknown_land_type'),('0','','invalid_main_lot')]:
            db,b,p,m=self.setup_release(gb=gb,bun=bun)
            r=consumer(db,'a')
            self.assertEqual(r['identity_status'],state);self.assertIsNone(r['address_pnu'])
            self.assertIsNone(r['traits']['value']);self.assertIsNone(r['price']['value']['value_krw_per_m2'])
            self.assertEqual(r['building']['value']['raw'],b['a']['raw'])
            self.assertEqual(db.execute('SELECT count(*) FROM address_relation').fetchone()[0],0)

    def test_mountain_and_missing_sub_lot_are_not_guessed(self):
        self.assertEqual(identify(['43111','12000','1','12','0'])['pnu'],'4311112000200120000')
        for fields in [['43111','0','0','12','0'],['43111','12000','0','12',''],['43111','12000','0','１２','0']]:
            self.assertIsNone(identify(fields)['pnu'])

    def test_source_consumer_permission_contract(self):
        db,b,p,m=self.setup_release();r=consumer(db,'a')
        self.assertTrue(r['observed_in_selected_release'])
        self.assertEqual(r['price']['value']['value_krw_per_m2'],'100')
        self.assertTrue(r['price']['permissions']['candidate_research'])
        for field in ['building','traits','price']:
            for permission in ['product_enrichment','quantity_aggregation','regression']:
                self.assertFalse(r[field]['permissions'][permission])

    def test_idempotent_replay_and_modified_release_rejection(self):
        db,b,p,m=self.setup_release();before=fingerprint(db)
        self.assertFalse(ingest(db,'first',1,b,p,m));self.assertEqual(fingerprint(db),before)
        p=copy.deepcopy(p);p[next(iter(p))]['raw']['price']='200'
        with self.assertRaises(ValueError):ingest(db,'first',1,b,p,m)
        self.assertEqual(fingerprint(db),before)

    def test_every_partial_stage_including_publication_rolls_back(self):
        for phase in ['sources','traits','buildings','published']:
            db,b,p,m=self.setup_release();before=fingerprint(db)
            with self.assertRaises(RuntimeError):ingest(db,'next',2,b,p,m,fail_at=phase)
            self.assertEqual(fingerprint(db),before)

    def test_missing_latest_building_is_last_seen_not_current_observation(self):
        db,b,p,m=self.setup_release();empty={};n=self.manifest(empty,p)
        ingest(db,'next',2,empty,p,n);r=consumer(db,'a')
        self.assertFalse(r['observed_in_selected_release']);self.assertEqual(r['last_seen_release'],'first')
        self.assertFalse(r['building']['permissions']['candidate_research'])
        self.assertIsNone(r['traits']['value']);self.assertEqual(r['price']['trust_state'],'last_seen_not_observed')

    def test_missing_latest_trait_does_not_fallback_to_old_price(self):
        db,b,p,m=self.setup_release();n=self.manifest(b,{})
        ingest(db,'next',2,b,{},n);r=consumer(db,'a')
        self.assertEqual(r['price']['trust_state'],'not_observed_in_selected_snapshot')
        self.assertEqual(r['price']['last_seen'],'first')
        self.assertEqual(db.execute('SELECT last_seen_release FROM current_parcel').fetchone()[0],'first')

    def test_full_release_restore_preserves_observations_and_current_outputs(self):
        db,b,p,m=self.setup_release();first=consumer(db,'a');p=copy.deepcopy(p)
        p[next(iter(p))]['raw']['price']='200';ingest(db,'next',2,b,p,m)
        before=fingerprint(db);latest=consumer(db,'a')
        restore(db,'first');self.assertEqual(consumer(db,'a'),first)
        self.assertEqual(db.execute('SELECT count(*) FROM price_observation').fetchone()[0],2)
        with self.assertRaises(ValueError):ingest(db,'third',3,b,p,m)
        restore(db,'next');self.assertEqual(consumer(db,'a'),latest);self.assertEqual(fingerprint(db),before)

    def test_price_change_does_not_create_new_trait_content_version(self):
        db,b,p,m=self.setup_release();p=copy.deepcopy(p);p[next(iter(p))]['raw']['price']='200'
        ingest(db,'next',2,b,p,m)
        self.assertEqual(db.execute('SELECT count(*) FROM parcel_version').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT count(*) FROM price_observation').fetchone()[0],2)

    def test_price_quality_states_preserved(self):
        for price,year,state in [('***','2026','source_overflow'),('0','2026','missing_or_nonpositive'),
                                 ('100','','unknown_price_year')]:
            db,b,p,m=self.setup_release(price=price,year=year)
            self.assertEqual(consumer(db,'a')['price']['trust_state'],state)
            self.assertFalse(consumer(db,'a')['price']['permissions']['candidate_research'])

    def test_namespace_count_year_and_original_dbf_conflicts_rejected(self):
        db=connect(':memory:');b,p=self.inputs();m=self.manifest(b,p)
        for field,value in [('expected_buildings',2),('pk_namespace','other'),('identity_rule','old')]:
            with self.assertRaises(ValueError):ingest(db,'first',1,b,p,{**m,field:value})
        p=copy.deepcopy(p);p[next(iter(p))]['raw']['year']='2025'
        with self.assertRaises(ValueError):ingest(db,'first',1,b,p,m)
        p=self.inputs()[1];p[next(iter(p))]['original_dbf']={'raw_fields':{'A1':'bad','A2':'bad'},'raw_record_hash':'0'*64}
        with self.assertRaises(ValueError):ingest(db,'first',1,b,p,m)

    def test_source_and_processed_overlap_must_agree(self):
        db=connect(':memory:');b,p=self.inputs();b['a']['attributes']['gross_area']='30'
        with self.assertRaises(ValueError):ingest(db,'first',1,b,p,self.manifest(b,p))

    def test_existing_zero_area_to_missing_preserves_both_and_quality(self):
        db=connect(':memory:');b,p=self.inputs()
        b['a']['raw']['raw_gross_area']='0';b['a']['attributes']['gross_area']=''
        ingest(db,'first',1,b,p,self.manifest(b,p))
        v=consumer(db,'a')['building']['value']
        self.assertEqual(v['raw']['raw_gross_area'],'0');self.assertEqual(v['attributes']['gross_area'],'')
        self.assertEqual(v['attribute_quality']['gross_area'],'source_zero_processed_missing')

    def test_input_immutability_and_foreign_keys(self):
        b,p=self.inputs();before=copy.deepcopy((b,p));db=connect(':memory:')
        ingest(db,'first',1,b,p,self.manifest(b,p));self.assertEqual((b,p),before)
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])


if __name__=='__main__':unittest.main()
