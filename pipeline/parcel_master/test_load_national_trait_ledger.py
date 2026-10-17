import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from parcel_master.load_national_trait_ledger import (
    RECORD,
    RECORD_DTYPE,
    _completed_from_bootstrap,
    classify_records,
    load,
)

HEADER = (
    "고유번호,법정동코드,법정동명,대장구분코드,대장구분명,지번,토지일련번호,"
    "기준연도,기준월,지목코드,지목명,토지면적,용도지역코드1,용도지역명1,"
    "용도지역코드2,용도지역명2,토지이용상황코드,토지이용상황,지형높이코드,지형높이,"
    "지형형상코드,지형형상,도로접면코드,도로접면,공시지가,데이터기준일자"
)


def _row(pnu: str, asof: str, price: str, year: str = "2026", month: str = "1") -> str:
    fields = [""] * 26
    fields[0] = pnu
    fields[7] = year
    fields[8] = month
    fields[24] = price
    fields[25] = asof
    return ",".join(fields)


def _zip(path: Path, rows: list[str], header: str = HEADER) -> None:
    payload = (header + "\n" + "\n".join(rows) + "\n").encode("cp949")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("plate.csv", payload)


class NationalTraitLedgerTests(unittest.TestCase):
    def test_record_layout_matches_numpy(self):
        self.assertEqual(RECORD.size, RECORD_DTYPE.itemsize)
        raw = io.BytesIO()
        raw.write(RECORD.pack(4311110100100010001, 20260512, 2026, 1, b"\x01" * 16))
        raw.seek(0)
        loaded = np.frombuffer(raw.getvalue(), dtype=RECORD_DTYPE)
        self.assertEqual(int(loaded[0]["pnu"]), 4311110100100010001)
        self.assertEqual(int(loaded[0]["asof"]), 20260512)
        self.assertEqual(int(loaded[0]["year"]), 2026)
        self.assertEqual(int(loaded[0]["month"]), 1)

    def test_identical_rows_collapse_and_conflicts_stay_out(self):
        rows = np.array(
            [
                (1, 20260512, 2026, 1, 5, 0),
                (1, 20260512, 2026, 1, 5, 0),
                (1, 20260512, 2026, 1, 9, 0),
                (1, 20260512, 2016, 1, 4, 0),
                (2, 20260512, 2026, 1, 5, 0),
                (2, 20260720, 2026, 1, 5, 0),
            ],
            dtype=RECORD_DTYPE,
        )
        classified = classify_records(rows)
        self.assertEqual(classified["identical"], 1)
        self.assertEqual(classified["clean_keys"], 3)
        self.assertEqual(classified["conflict_keys"], 1)
        self.assertEqual(classified["conflict_variants"], 2)
        plate = classified["clean"][20260512]
        self.assertFalse(np.any((plate["pnu"] == 1) & (plate["year"] == 2026)))
        self.assertTrue(np.any((plate["pnu"] == 1) & (plate["year"] == 2016)))

    def test_zip_load_keeps_each_asof_and_isolates_conflicts(self):
        pnu_a = "4311110100100010001"
        pnu_b = "4311110100100020001"
        held = "4311110100100000001"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            _zip(
                src / "a.zip",
                [
                    _row(pnu_a, "2026-05-12", "10"),
                    _row(pnu_a, "2026-05-12", "10"),
                    _row(pnu_a, "2026-05-12", "8", year="2016"),
                    _row(pnu_b, "2026-05-12", "5"),
                    _row(pnu_a, "2026-07-20", "7"),
                ],
            )
            _zip(
                src / "b.zip",
                [
                    _row(pnu_a, "2026-05-12", "99"),
                    _row(held, "2026-05-12", "1"),
                ],
            )
            report = load(
                src=src,
                db_path=root / "ledger.sqlite",
                work_dir=root / "work",
                shard_count=4,
                report_path=None,
            )
        self.assertTrue(report["ok"])
        self.assertEqual(report["stored_observations"], 3)
        self.assertEqual(report["unique_pnu"], 2)
        self.assertEqual(report["collapsed_identical"], 1)
        self.assertEqual(report["conflict_keys"], 1)
        self.assertEqual(report["conflict_variants"], 2)
        self.assertEqual(report["conflict_stored"], 2)
        self.assertEqual(report["asofs"], ["2026-05-12", "2026-07-20"])
        self.assertEqual(report["held"]["noncanonical_zero_main_lot"], 1)

    def test_bootstrap_log_keeps_only_finished_files(self):
        names = ["a.zip", "b.zip", "c.zip"]
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "build_year_month.log"
            text = "load a.zip rows=4 stored=3\nload b.zip rows=5000000 stored=9\n"
            log.write_bytes(text.encode("utf-16"))
            done, stored = _completed_from_bootstrap(log, names)
        self.assertEqual(done, ["a.zip"])
        self.assertEqual(stored, 3)

    def test_resume_keeps_the_database_and_skips_finished_files(self):
        pnu_a = "4311110100100010001"
        pnu_b = "4311110100100020001"
        pnu_c = "4311110100100030001"
        held = "4311110100100000001"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            _zip(
                src / "a.zip",
                [
                    _row(pnu_a, "2026-05-12", "10"),
                    _row(pnu_a, "2026-05-12", "10"),
                    _row(pnu_a, "2026-05-12", "8", year="2016"),
                    _row(pnu_b, "2026-05-12", "5"),
                    _row(pnu_a, "2026-07-20", "7"),
                ],
            )
            _zip(src / "b.zip", [_row(pnu_a, "2026-05-12", "99"), _row(held, "2026-05-12", "1")])
            _zip(
                src / "c.zip",
                [_row(pnu_c, "2026-05-12", "3"), _row(pnu_b, "2026-05-12", "5")],
            )
            db_path = root / "ledger.sqlite"
            work = root / "work"
            report = load(src=src, db_path=db_path, work_dir=work, shard_count=4, report_path=None)
            self.assertTrue(report["ok"])
            self.assertEqual(report["stored_observations"], 4)
            marker = sqlite3.connect(db_path)
            marker.execute("CREATE TABLE resume_marker (n INTEGER)")
            marker.execute("INSERT INTO resume_marker VALUES (7)")
            marker.commit()
            marker.close()
            state_path = work / "loaded_files.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["files"] = ["a.zip", "b.zip"]
            state_path.write_text(json.dumps(state), encoding="utf-8")
            again = load(src=src, db_path=db_path, work_dir=work, shard_count=4, report_path=None)
            kept = sqlite3.connect(db_path)
            mark = kept.execute("SELECT n FROM resume_marker").fetchone()[0]
            rows = kept.execute("SELECT COUNT(*) FROM parcel_observation").fetchone()[0]
            kept.close()
        self.assertEqual(mark, 7)
        self.assertEqual(rows, 4)
        self.assertTrue(again["ok"])
        self.assertEqual(again["stored_observations"], 4)
        self.assertEqual(again["unique_pnu"], 3)
        self.assertEqual(again["collapsed_identical"], 2)
        self.assertEqual(again["conflict_stored"], 2)


if __name__ == "__main__":
    unittest.main()
