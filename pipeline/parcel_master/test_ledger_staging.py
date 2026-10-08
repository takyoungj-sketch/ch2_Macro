import tempfile
import unittest
from pathlib import Path
from ledger_staging import attributes,connect,ingest,restore,DISTRICTS

def rows():
    return [{'pnu':d+'00000100010001','bjd':d+'00000','lot':'1-1','area':'35.0','price':'100','trait_asof':'2025-08-08'} for d in sorted(DISTRICTS)]

def manifest(n=4):
    return {'source_districts':sorted(DISTRICTS),'sha256':'a'*64,'expected_unique_pnu':n}

class StagingTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=connect(Path(self.tmp.name)/'pilot.sqlite')
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def test_idempotency(self):
        ingest(self.db,'2025',rows(),manifest());r=ingest(self.db,'2025',rows(),manifest())
        self.assertTrue(r['idempotent_replay']);self.assertEqual(self.db.execute('SELECT COUNT(*) FROM versions').fetchone()[0],4)
    def test_failure_preserves_previous_batch(self):
        ingest(self.db,'2025',rows(),manifest());modified=rows();modified[0]['price']='200'
        with self.assertRaises(RuntimeError):ingest(self.db,'2026',modified,manifest(),fail_after=2)
        self.assertEqual(self.db.execute("SELECT value FROM state WHERE key='head'").fetchone()[0],'2025')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM versions').fetchone()[0],4)
    def test_missing_district_is_rejected(self):
        with self.assertRaises(ValueError):ingest(self.db,'2025',rows()[:-1],manifest(3))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0],0)
    def test_restore_and_attribute_history(self):
        ingest(self.db,'2025',rows(),manifest());modified=rows();modified[0]['price']='200'
        r=ingest(self.db,'2026',modified,manifest());self.assertEqual(r['changed'],1)
        restore(self.db,'2025');self.assertEqual(self.db.execute("SELECT value FROM state WHERE key='head'").fetchone()[0],'2025')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM versions').fetchone()[0],5)
    def test_dbf_overflow_preserved(self):
        self.assertEqual(attributes({'price':'*********'})['price'],'*********')
    def test_same_manifest_cannot_hide_changed_payload(self):
        ingest(self.db,'2025',rows(),manifest());modified=rows();modified[0]['price']='200'
        with self.assertRaises(ValueError):ingest(self.db,'2025',modified,manifest())
    def test_older_new_batch_cannot_replace_head(self):
        ingest(self.db,'2025',rows(),manifest())
        with self.assertRaises(ValueError):ingest(self.db,'2024',rows(),manifest())

if __name__=='__main__':unittest.main()
