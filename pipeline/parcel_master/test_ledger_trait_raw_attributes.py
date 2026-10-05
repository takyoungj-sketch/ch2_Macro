import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from ledger_trait_raw_attributes import scan


class RawAttributeTests(unittest.TestCase):
    def fixture(self, path, bjd='4311112345', truncate=False):
        fields=(('A1',19),('A2',10),('A18',16)); hl=32+32*len(fields)+1; rl=1+sum(n for _,n in fields)
        header=bytearray(32); struct.pack_into('<I',header,4,1); struct.pack_into('<HH',header,8,hl,rl)
        descriptors=b''
        for name,length in fields:
            field=bytearray(32); field[:len(name)]=name.encode(); field[11]=ord('C'); field[16]=length
            descriptors+=field
        record=b' '+b'4311112345100120000'+bjd.encode()+'평지'.encode('cp949').ljust(16,b' ')
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('source.dbf',bytes(header)+descriptors+b'\r'+(record[:-1] if truncate else record))

    def test_all_fields_and_encoding_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.zip'; self.fixture(path)
            rows,meta=scan(path,{'4311112345100120000'})
            self.assertEqual(set(rows['4311112345100120000']),{'A1','A2','A18'})
            self.assertEqual(rows['4311112345100120000']['A18'],'평지')
            self.assertEqual(meta['encoding'],'cp949')

    def test_conflicting_identity_and_truncation_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.zip'
            for kwargs in ({'bjd':'4311212345'},{'truncate':True}):
                self.fixture(path,**kwargs)
                with self.assertRaises(ValueError): scan(path,{'4311112345100120000'})


if __name__=='__main__': unittest.main()
