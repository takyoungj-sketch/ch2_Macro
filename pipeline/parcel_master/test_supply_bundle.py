import json
import tempfile
import unittest
from pathlib import Path

from ledger_supply_bundle import FrozenListLookup,sha,verify_manifest


class SupplyBundleTests(unittest.TestCase):
    def seed(self,root):
        reports=('cheongju_product_numeric_baseline.json','cheongju_product_field_extension.json',
                 'cheongju_numeric_supply_shadow.json','cheongju_supply_regression_replay.json')
        scripts=('freeze_cheongju_product_numeric.py','extend_cheongju_product_fields.py','cheongju_numeric_supply_shadow.py',
                 'replay_cheongju_supply_regressions.py','run_cheongju_product_supply.py','ledger_supply_artifacts.py')
        mapping={}
        for folder,names in [('docs/lab',reports),('pipeline/parcel_master',scripts)]:
            target=root/folder;target.mkdir(parents=True)
            for name in names:(target/name).write_text('fixed input',encoding='utf-8')
            mapping[folder]={name:sha(target/name) for name in names}
        report={'production_apply':False,'checks':{name:True for name in reports},
                'report_sha256':mapping['docs/lab'],'script_sha256':mapping['pipeline/parcel_master']}
        path=root/'docs/lab/cheongju_product_supply_pipeline.json'
        path.write_text(json.dumps(report),encoding='utf-8')
        return path,report

    def test_reports_and_implementation_must_match_completed_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.seed(root);verify_manifest(root)
            path=root/'pipeline/parcel_master/run_cheongju_product_supply.py';path.write_text('changed')
            with self.assertRaisesRegex(ValueError,'bundle changed'):verify_manifest(root)

    def test_mixed_reports_and_failed_or_incomplete_checks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,report=self.seed(root)
            one=root/'docs/lab/cheongju_numeric_supply_shadow.json';one.write_text('new generation')
            with self.assertRaisesRegex(ValueError,'bundle changed'):verify_manifest(root)
            report['report_sha256'][one.name]=sha(one);report['checks'][one.name]=False
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'successfully'):verify_manifest(root)
            report['checks'].pop(one.name);path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'successfully'):verify_manifest(root)

    def test_unknown_lookup_is_not_silently_emulated(self):
        lookup=FrozenListLookup([],[])
        with self.assertRaisesRegex(ValueError,'Unsupported'):lookup.execute('DELETE FROM collective_building_attributes')
        with self.assertRaisesRegex(ValueError,'Unsupported'):lookup.execute('SELECT to_regclass(:t)',{'t':'public.unrelated'})

    def test_price_lookup_keeps_asset_pair_and_newest_year(self):
        rows=[{'building_key':'shared','asset_type':asset,'assessed_land_price_year':year} for asset,year in
              [('apartment',2025),('apartment',2026),('officetel',2024)]]
        sql=('SELECT DISTINCT ON (building_key, asset_type) building_key, asset_type, assessed_land_price, '
             'assessed_land_price_year FROM collective_building_assessed_land_price WHERE building_key = ANY(:keys) '
             'ORDER BY building_key, asset_type, assessed_land_price_year DESC NULLS LAST')
        got=FrozenListLookup([],rows).execute(sql,{'keys':['shared']}).mappings().all()
        self.assertEqual([(r['asset_type'],r['assessed_land_price_year']) for r in got],[('apartment',2026),('officetel',2024)])
        self.assertEqual(rows[0]['assessed_land_price_year'],2025)
