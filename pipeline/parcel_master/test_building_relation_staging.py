import tempfile
import unittest
from pathlib import Path

from building_relation_staging import connect, ingest, restore, state_fingerprint, DISTRICTS


def inputs(snapshot='2025-07'):
    buildings = [{'mgmt_pk': d, 'snapshot': snapshot, 'pnu': d+'00000100010000',
                  'beopjungri_code': d+'00000', 'gross_area': '100.0'} for d in sorted(DISTRICTS)]
    traits = [{'pnu': b['pnu'], 'bjd': b['beopjungri_code'], 'year': '2025', 'price': '100', 'area': '200'} for b in buildings]
    manifest = {'source_districts': sorted(DISTRICTS), 'building_sha256': 'a'*64, 'trait_sha256': 'b'*64,
                'scope_sha256': 'c'*64, 'expected_buildings': 4, 'expected_traits': 4, 'trait_year': 2025}
    return buildings, traits, manifest


class RelationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.tmp.name)/'relations.sqlite')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_replay_is_immutable_and_tamper_rejected(self):
        b,p,m = inputs(); ingest(self.db,'2025-07',b,p,m)
        before = state_fingerprint(self.db)
        self.assertTrue(ingest(self.db,'2025-07',b,p,m)['idempotent_replay'])
        self.assertEqual(before,state_fingerprint(self.db))
        p[0]['price']='101'
        with self.assertRaises(ValueError): ingest(self.db,'2025-07',b,p,m)
        self.assertEqual(before,state_fingerprint(self.db))

    def test_pnu_change_is_relation_not_building_attribute_change(self):
        b,p,m = inputs(); ingest(self.db,'2025-07',b,p,m)
        b,p,m = inputs('2026-07'); b[0]['pnu']=b[0]['pnu'][:-4]+'0001'
        r=ingest(self.db,'2026-07',b,p,m)
        self.assertEqual(r['address_changed'],1)
        self.assertEqual(r['attribute_changed'],0)
        self.assertEqual(r['relations_without_traits'],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM building_version').fetchone()[0],4)
        self.assertEqual(self.db.execute('SELECT count(*) FROM address_relation_observation').fetchone()[0],8)

    def test_missing_preserved_and_restore_keeps_history(self):
        b,p,m = inputs(); b.append({**b[0],'mgmt_pk':'extra'}); m['expected_buildings']=5
        ingest(self.db,'2025-07',b,p,m)
        b,p,m=inputs('2026-07'); r=ingest(self.db,'2026-07',b,p,m)
        self.assertEqual(r['missing_not_deleted'],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM current_building').fetchone()[0],5)
        before=self.db.execute('SELECT count(*) FROM building_observation').fetchone()[0]
        restore(self.db,'2025-07'); restore(self.db,'2026-07')
        self.assertEqual(self.db.execute('SELECT count(*) FROM building_observation').fetchone()[0],before)

    def test_failure_rolls_back_every_table(self):
        b,p,m=inputs(); ingest(self.db,'2025-07',b,p,m); before=state_fingerprint(self.db)
        b,p,m=inputs('2026-07'); b[0]['gross_area']='101'; p[0]['price']='102'
        with self.assertRaises(RuntimeError): ingest(self.db,'2026-07',b,p,m,fail_after=2)
        self.assertEqual(before,state_fingerprint(self.db))

    def test_conflicting_identity_rejected_before_write(self):
        b,p,m=inputs(); b[0]['beopjungri_code']='4311100001'
        with self.assertRaises(ValueError): ingest(self.db,'2025-07',b,p,m)
        self.assertEqual(self.db.execute('SELECT count(*) FROM source_snapshot').fetchone()[0],0)

    def test_older_batch_rejected_after_restore(self):
        b,p,m=inputs(); ingest(self.db,'2025-07',b,p,m)
        b,p,m=inputs('2026-07'); ingest(self.db,'2026-07',b,p,m); restore(self.db,'2025-07')
        b,p,m=inputs('2025-08')
        with self.assertRaises(ValueError): ingest(self.db,'2025-08',b,p,m)

    def test_missing_price_year_is_preserved_and_prices_are_separate(self):
        b,p,m=inputs(); p[0]['year']=''; ingest(self.db,'2025-07',b,p,m)
        year,status=self.db.execute("SELECT price_year,status FROM assessed_price_observation WHERE pnu=?",(p[0]['pnu'],)).fetchone()
        self.assertIsNone(year)
        self.assertEqual(status,'unknown_price_year')
        b,p,m=inputs('2026-07'); p[0]['price']='200'; ingest(self.db,'2026-07',b,p,m)
        self.assertEqual(self.db.execute('SELECT count(*) FROM parcel_version').fetchone()[0],4)
        self.assertEqual(self.db.execute('SELECT count(*) FROM assessed_price_observation').fetchone()[0],8)


if __name__=='__main__': unittest.main()
