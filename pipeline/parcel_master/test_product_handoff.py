import copy
import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ledger_product_handoff as handoff
from test_ledger_operations import package
from ledger_operations import Operations,scope_hash
from ledger_supply_artifacts import write_gzip_atomic,write_json_atomic
from ledger_supply_bundle import sha
from integrated_ledger_v2 import digest
from extend_cheongju_product_fields import EXTENSION,product_row
from cheongju_numeric_supply_shadow import projected_attributes
from parcel_master.paths import TITLE_COLS


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();parent=Path(self.tmp.name)
        self.ops=Operations(parent/'operations_test',allowed_parent=parent)
        p=package(self.ops,'base','2024-09');meta=json.loads(p.read_text());meta['manifest']['field_extension']=EXTENSION
        meta['scope_sha256']=scope_hash(meta['manifest'])
        rows={}
        with gzip.open(p.parent/'buildings.json.gz','rt') as f:rows=json.load(f)
        for pk,r in rows.items():
            fields={k:'' for k in TITLE_COLS};fields.update({'pk':pk,'ledger_kind':'집합','sigungu_code':'43111','bjd_code':'12000',
                'plat_gb':'0','bun':r['raw']['raw_identity_fields'][3],'ji':'0','main_purpose':'아파트',
                'households':'10','floors_above':'5','park_self_in':'10','approve_date':'20000101','struct_name':'철근콘크리트구조','dong_name':'101동'})
            r['raw'].update({'product_fields':fields,'product_fields_policy':EXTENSION})
        write_gzip_atomic(p.parent/'buildings.json.gz',rows)
        meta['payloads']['buildings'].update({'sha256':sha(p.parent/'buildings.json.gz'),'content_sha256':digest(rows)})
        write_json_atomic(p,meta);s=self.ops.stage(p);self.ops.publish('base',s['impact_sha256'],0)
        candidate=projected_attributes([product_row(rows['a']['raw']['product_fields'],'2024-09')],'apartment')
        self.assertIsNotNone(candidate)
        old={**candidate,'building_key':'key','asset_type':'apartment','match_rule':'title_pnu','snapshot_ym':'202409'}
        stats={'building_key':'key','asset_type':'apartment','beopjungri_code':'4311112000','lot_number':'12'}
        self.frozen={'collective':{'residential_stats':[stats],'attributes':[old],
            'prices':[{'building_key':'key','asset_type':'apartment','representative_pnu':'4311112000100120000','assessed_land_price':100,'assessed_land_price_year':2024}],
            'residential_transactions':[],'commercial_stats':[{'cluster_key':'road'}],'commercial_transactions':[]},'built':{'transactions':[]}}
        self.paired={'baseline_sha256':'b'*64,'residential':[{'stats':stats,'legacy_attributes':old,'compatible_attributes':copy.deepcopy(old),
             'legacy_price':100,'compatible_price':'100','review_hold':False}],'built':[],
             'commercial_stats':self.frozen['collective']['commercial_stats'],'commercial_transactions':[]}
        self.audit={'consumer_contract_sha256':'c'*64,'acceptance_sha256':'d'*64,'source_manifest_sha256':'e'*64}
        self.mocks=[patch.object(handoff,'open_ledger',lambda p:sqlite3.connect(Path(p).as_uri()+'?mode=ro',uri=True)),
                    patch.object(handoff,'evidence',return_value=self.audit),
                    patch.object(handoff,'load_verified_supply',return_value=(self.frozen,self.paired,'e'*64))]
        for m in self.mocks:m.start()

    def tearDown(self):
        for m in reversed(self.mocks):m.stop()
        self.ops.close();self.tmp.cleanup()

    def test_selected_db_recomputes_values_and_binding_refs(self):
        receipt=handoff.build(self.ops,'unused','one');verified,payload=handoff.load(self.ops,'unused')
        self.assertEqual(receipt,verified);self.assertEqual(receipt['counts']['title_source_keys'],1)
        self.assertEqual(receipt['counts']['price_source_keys'],1)
        row=payload['residential'][0]
        self.assertEqual(row['attributes']['source']['observation_refs'][0]['pk'],'a')
        self.assertEqual(row['price']['source']['observation_refs'][0]['pnu'],'4311112000100120000')
        self.assertFalse(row['price']['permissions']['product_enrichment'])

    def test_failed_product_pointer_preserves_previous_handoff(self):
        handoff.build(self.ops,'unused','one');before=self.ops.state()
        with self.assertRaises(RuntimeError):handoff.build(self.ops,'unused','two',fail_at='pointer')
        self.assertEqual(self.ops.db.execute('SELECT active_id FROM product_control').fetchone()[0],'one')
        self.assertEqual(self.ops.state(),before);handoff.load(self.ops,'unused')

    def test_source_revision_and_evidence_changes_block_read(self):
        handoff.build(self.ops,'unused','one')
        self.audit['acceptance_sha256']='f'*64
        with self.assertRaises(ValueError):handoff.load(self.ops,'unused')
        self.audit['acceptance_sha256']='d'*64
        self.ops.db.execute('UPDATE control SET revision=revision+1');self.ops.db.commit()
        with self.assertRaises(ValueError):handoff.load(self.ops,'unused')

    def test_changed_projection_and_mixed_baseline_block_handoff(self):
        self.paired['residential'][0]['compatible_attributes']['households']=999
        with self.assertRaises(ValueError):handoff.build(self.ops,'unused','bad')
        self.paired['residential'][0]['compatible_attributes']=copy.deepcopy(self.paired['residential'][0]['legacy_attributes'])
        self.paired['commercial_stats']=[]
        with self.assertRaises(ValueError):handoff.build(self.ops,'unused','mixed')
        self.assertIsNone(self.ops.db.execute('SELECT active_id FROM product_control').fetchone()[0])

    def test_tampered_artifact_and_receipt_block_read(self):
        handoff.build(self.ops,'unused','one');folder=self.ops.root/'handoffs/one'
        p=folder/'product.json.gz';original=p.read_bytes();p.write_bytes(original+b'changed')
        with self.assertRaises(ValueError):handoff.load(self.ops,'unused')
        p.write_bytes(original);(folder/'receipt.json').write_text('{}')
        with self.assertRaises(ValueError):handoff.load(self.ops,'unused')

    def test_held_title_binding_retains_baseline(self):
        self.paired['residential'][0]['review_hold']=True
        receipt=handoff.build(self.ops,'unused','one');_,payload=handoff.load(self.ops,'unused')
        self.assertEqual(receipt['counts']['title_source_keys'],0)
        self.assertNotIn('release_id',payload['residential'][0]['attributes']['source'])

    def test_source_changes_while_building_reject_product_publication(self):
        original=handoff.project
        def changed(*args):
            value=original(*args)
            self.ops.db.execute('UPDATE control SET revision=revision+1');self.ops.db.commit()
            return value
        with patch.object(handoff,'project',side_effect=changed):
            with self.assertRaises(ValueError):handoff.build(self.ops,'unused','stale')
        self.assertIsNone(self.ops.db.execute('SELECT active_id FROM product_control').fetchone()[0])


if __name__=='__main__':unittest.main()
