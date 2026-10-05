import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from integrated_ledger_v2 import CONTRACT,NAMESPACE,consumer,digest
from ledger_identity_v2 import VERSION
from ledger_operations import PACKAGE,Operations,scope_hash,unique_object
from ledger_supply_bundle import sha
from ledger_supply_artifacts import write_gzip_atomic,write_json_atomic
from ledger_product_transition import conditions


def package(ops,batch,month,missing=False):
    pnu='4311112000100120000'
    buildings={'a':{'raw':{'raw_identity_fields':['43111','12000','0','12','0']},'attributes':{'gross_area':'20'}}}
    if not missing:buildings['b']={'raw':{'raw_identity_fields':['43111','12000','0','13','0']},'attributes':{'gross_area':'30'}}
    traits={pnu:{'raw':{'pnu':pnu,'bjd':pnu[:10],'year':month[:4],'price':'100','area':'10','trait_asof':month+'-01'}}}
    manifest={'identity_rule':VERSION,'pk_namespace':NAMESPACE,'title_snapshot':month,'trait_year':int(month[:4]),
       'districts':['43111','43112','43113','43114'],'expected_buildings':len(buildings),'expected_traits':len(traits),
       'cohort':'test_same_scope','scope_sha256':'f'*64,'temporal_policy':'same_year_research_only',
       'sources':{k:{'sha256':str(i)*64,'base_date':None,'collected_at':None} for i,k in enumerate(('title','traits','processed_building'),1)}}
    folder=ops.root/'inbox'/batch;folder.mkdir(parents=True)
    value={'package':PACKAGE,'batch_id':batch,'consumer_contract':CONTRACT,'coverage':'full_snapshot','manifest':manifest,
           'scope_sha256':scope_hash(manifest),'evidence_kind':'historical_rehearsal','payloads':{}}
    for name,rows in [('buildings',buildings),('traits',traits)]:
        p=folder/(name+'.json.gz');write_gzip_atomic(p,rows)
        value['payloads'][name]={'file':p.name,'sha256':sha(p),'content_sha256':digest(rows),'rows':len(rows)}
    path=folder/'package.json';write_json_atomic(path,value);return path


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();parent=Path(self.temp.name)
        self.ops=Operations(parent/'operations_test',allowed_parent=parent)
        self.path=package(self.ops,'base','2024-09');self.base=self.ops.stage(self.path)
        self.ops.publish('base',self.base['impact_sha256'],0)

    def tearDown(self):self.ops.close();self.temp.cleanup()

    def test_staging_does_not_change_active_pointer_and_absence_is_last_seen(self):
        before=self.ops.active();stage=self.ops.stage(package(self.ops,'next','2025-07',True))
        self.assertEqual(self.ops.active(),before)
        self.assertEqual(stage,self.ops.stage(self.ops.root/'inbox/next/package.json'))
        db=sqlite3.connect((self.ops.root/'candidates/next/ledger.sqlite').as_uri()+'?mode=ro',uri=True)
        row=consumer(db,'b');db.close()
        self.assertFalse(row['observed_in_selected_release']);self.assertIsNone(row['traits']['value'])
        self.assertFalse(row['price']['permissions']['product_enrichment'])

    def test_review_hash_and_compare_and_swap_prevent_stale_publication(self):
        a=self.ops.stage(package(self.ops,'next','2025-07'))
        b=self.ops.stage(package(self.ops,'other','2025-08'))
        with self.assertRaises(ValueError):self.ops.publish('next','0'*64,1)
        self.assertTrue(self.ops.publish('next',a['impact_sha256'],1))
        before=self.ops.state()
        with self.assertRaises(ValueError):self.ops.publish('other',b['impact_sha256'],1)
        self.assertEqual(self.ops.state(),before)
        self.assertFalse(self.ops.publish('next',a['impact_sha256'],1))

    def test_failed_ingest_publication_and_restore_leave_pointer_unchanged(self):
        path=package(self.ops,'next','2025-07');before=self.ops.state()
        with self.assertRaises(RuntimeError):self.ops.stage(path,fail_at='published')
        self.assertEqual(self.ops.state(),before)
        self.assertFalse((self.ops.root/'candidates/next').exists())
        stage=self.ops.stage(path)
        with self.assertRaises(RuntimeError):self.ops.publish('next',stage['impact_sha256'],1,fail_at='pointer')
        self.assertEqual(self.ops.state(),before)
        self.ops.publish('next',stage['impact_sha256'],1);latest=self.ops.state()
        with self.assertRaises(RuntimeError):self.ops.restore('base',2,fail_at='pointer')
        self.assertEqual(self.ops.state(),latest)
        self.ops.restore('base',2)
        with self.assertRaises(ValueError):self.ops.stage(package(self.ops,'later','2026-07'))
        self.ops.restore('next',3);self.assertEqual(self.ops.state()['active_id'],'next')

    def test_modified_payload_database_and_impact_cannot_be_published(self):
        stage=self.ops.stage(package(self.ops,'next','2025-07'));before=self.ops.state()
        path=self.ops.root/'inbox/next/buildings.json.gz';original=path.read_bytes();path.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.ops.publish('next',stage['impact_sha256'],1)
        path.write_bytes(original)
        database=self.ops.root/'candidates/next/ledger.sqlite';original_db=database.read_bytes();database.write_bytes(original_db+b'changed')
        with self.assertRaises(ValueError):self.ops.publish('next',stage['impact_sha256'],1)
        database.write_bytes(original_db)
        target=self.ops.root/'candidates/next/impact.json';target.write_text('{}')
        with self.assertRaises(ValueError):self.ops.publish('next',stage['impact_sha256'],1)
        self.assertEqual(self.ops.state(),before)

    def test_old_month_changed_scope_and_escaping_paths_are_rejected(self):
        with self.assertRaises(ValueError):self.ops.stage(package(self.ops,'old','2024-09'))
        path=package(self.ops,'next','2025-07');value=json.loads(path.read_text())
        value['manifest']['cohort']='different';value['scope_sha256']=scope_hash(value['manifest']);write_json_atomic(path,value)
        with self.assertRaises(ValueError):self.ops.stage(path)
        with self.assertRaises(ValueError):self.ops.stage(self.ops.root.parent/'outside.json')
        with self.assertRaises(ValueError):json.loads('{"id":1,"id":2}',object_pairs_hook=unique_object)

    def test_regression_adoption_is_not_required_for_scoped_product_handoff(self):
        evidence={'actual_next_month_update_tested':True,'tcp_nginx_browser_tested':True}
        contract={'default_permissions':{'product_enrichment':True,'quantity_aggregation':False,'regression':False}}
        self.assertEqual(conditions(evidence,contract,publication_bound=True),[])
        contract['default_permissions']['product_enrichment']=False
        self.assertIn('consumer_contract_does_not_authorize_new_product_use',conditions(evidence,contract,publication_bound=True))
