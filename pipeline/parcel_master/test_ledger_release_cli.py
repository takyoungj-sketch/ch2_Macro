import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrated_ledger_v2 import connect
from ledger_release_cli import open_ledger


class ReleaseCliTests(unittest.TestCase):
    def test_default_inspection_is_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'integrated.sqlite'
            connect(path).close()
            with patch('ledger_release_cli.RESEARCH',Path(directory)):
                db=open_ledger(path)
                with self.assertRaises(sqlite3.OperationalError):
                    db.execute('DELETE FROM building')
                db.close()

    def test_wrong_schema_and_outside_path_are_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.sqlite'
            db=sqlite3.connect(path);db.execute('CREATE TABLE frozen(value TEXT)');db.commit();db.close()
            original=path.read_bytes()
            with patch('ledger_release_cli.RESEARCH',Path(directory)):
                with self.assertRaises(ValueError):open_ledger(path,writable=True)
            with patch('ledger_release_cli.RESEARCH',Path(directory)/'other'):
                with self.assertRaises(ValueError):open_ledger(path,writable=True)
            self.assertEqual(path.read_bytes(),original)
