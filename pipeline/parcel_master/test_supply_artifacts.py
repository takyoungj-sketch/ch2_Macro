import gzip
import json
import tempfile
import unittest
from pathlib import Path
from ledger_supply_artifacts import write_gzip_atomic,write_json_atomic


class SupplyArtifactTests(unittest.TestCase):
    def test_failed_serialization_preserves_previous_artifact_and_removes_pending_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'supply.json.gz';write_gzip_atomic(path,{'published':'old'});original=path.read_bytes()
            with self.assertRaises(TypeError):write_gzip_atomic(path,{'published':'new','bad':object()})
            self.assertEqual(path.read_bytes(),original);self.assertEqual(list(Path(folder).iterdir()),[path])
            with gzip.open(path,'rt',encoding='utf-8') as file:self.assertEqual(json.load(file),{'published':'old'})

    def test_nonfinite_report_cannot_replace_previous_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'manifest.json';write_json_atomic(path,{'ok':True});original=path.read_bytes()
            with self.assertRaises(ValueError):write_json_atomic(path,{'bad':float('nan')})
            self.assertEqual(path.read_bytes(),original);self.assertEqual(list(Path(folder).iterdir()),[path])
