import unittest
from building_source_staging_v2 import connect, identity, ingest, fingerprint


class SourceV2Tests(unittest.TestCase):
    def row(self, gb='0'):
        fields = ['43111','12345',gb,'12','0']
        return {'raw_identity_fields':fields,'pnu':identity(fields)[0],'main_aux_code':'1',
                'main_aux_label':'부속','related_lot_count':'02','special_land_label':'원문'}

    def test_strict_identity(self):
        self.assertEqual(identity(['43111','12345','0','12','0'])[0],'4311112345100120000')
        self.assertEqual(identity(['43111','12345','1','12','0'])[0],'4311112345200120000')
        for fields in (['43111','12345','2','12','0'],['43111','12345','0','','0'],
                       ['43111','4311212345','0','12','0'],['43111','12345','0','12345','0'],
                       ['43111','12345','0','１２','0']):
            self.assertIsNone(identity(fields)[0])

    def test_unknown_preserved_without_link(self):
        db=connect(':memory:'); records={'x':self.row('2')}
        manifest={'source_sha256':'a'*64,'expected_records':1}
        ingest(db,'2026-07',records,manifest)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM title_observation').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM canonical_address_relation').fetchone()[0],0)
        before=fingerprint(db)
        self.assertFalse(ingest(db,'2026-07',records,manifest))
        self.assertEqual(before,fingerprint(db))
        changed={'x':{**records['x'],'related_lot_count':'03'}}
        with self.assertRaises(ValueError): ingest(db,'2026-07',changed,manifest)
        self.assertEqual(before,fingerprint(db))

    def test_atomic_failure(self):
        db=connect(':memory:'); before=fingerprint(db)
        with self.assertRaises(RuntimeError):
            ingest(db,'2026-07',{'x':self.row()},{'source_sha256':'a'*64,'expected_records':1},fail_after=1)
        self.assertEqual(before,fingerprint(db))


if __name__=='__main__': unittest.main()
