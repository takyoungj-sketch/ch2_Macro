import unittest

from parcel_master.attribute_ledger import connect, create, ingest_building_rows, ingest_trait_rows


def trait(**overrides):
    row = {
        "pnu": "4311110100100010001",
        "year": "2019",
        "month": "01",
        "jimok_code": "08",
        "jimok_label": "대",
        "area": "100.0",
        "zone1_code": "14",
        "zone1_label": "",
        "zone2_code": "00",
        "use_code": "110",
        "height_code": "02",
        "shape_code": "01",
        "road_code": "08",
        "price": "250000",
        "trait_asof": "2019-08-20",
    }
    row.update(overrides)
    return row


class AttributeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        create(self.db)

    def test_identical_duplicate_collapses_and_keeps_code_without_label(self):
        stats = ingest_trait_rows(
            self.db,
            2019,
            [trait(), trait(), trait(pnu="4311110100200030000")],
            "traits_2019.csv.gz",
        )
        self.assertEqual(stats["collapsed_identical"], 1)
        self.assertEqual(stats["stored"], 2)
        row = self.db.execute(
            "SELECT asof, zone1_code, zone1_label FROM parcel_observation WHERE pnu = ?",
            ("4311110100100010001",),
        ).fetchone()
        self.assertEqual(row["asof"], "2019-08-20")
        self.assertEqual(row["zone1_code"], "14")
        self.assertEqual(row["zone1_label"], "")

    def test_conflicting_duplicate_is_rejected(self):
        with self.assertRaises(ValueError):
            ingest_trait_rows(
                self.db,
                2019,
                [trait(), trait(price="1")],
                "traits_2019.csv.gz",
            )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM parcel_observation").fetchone()[0], 0)

    def test_zero_main_lot_is_not_a_parcel(self):
        stats = ingest_trait_rows(
            self.db,
            2019,
            [trait(pnu="4311110100100000001")],
            "traits_2019.csv.gz",
        )
        self.assertEqual(stats["held"]["noncanonical_zero_main_lot"], 1)
        self.assertEqual(stats["stored"], 0)

    def test_mountain_pnu_is_kept(self):
        stats = ingest_trait_rows(
            self.db,
            2019,
            [trait(pnu="4311110100200010001")],
            "traits_2019.csv.gz",
        )
        self.assertEqual(stats["stored"], 1)

    def test_block_and_zero_lot_buildings_are_held(self):
        rows = [
            {
                "pk": "b1",
                "ledger_kind": "일반",
                "sigungu_code": "43111",
                "bjd_code": "10100",
                "plat_gb": "0",
                "bun": "12",
                "ji": "1",
                "struct_name": "철근콘크리트구조",
                "floors_above": "5",
                "floors_below": "0",
                "gross_area": "100",
                "plat_area": "50",
                "approve_date": "20000101",
            },
            {**{
                "pk": "b2",
                "ledger_kind": "일반",
                "sigungu_code": "43111",
                "bjd_code": "10100",
                "plat_gb": "2",
                "bun": "12",
                "ji": "1",
                "struct_name": "",
                "floors_above": "",
                "floors_below": "",
                "gross_area": "",
                "plat_area": "",
                "approve_date": "",
            }},
            {
                "pk": "b3",
                "ledger_kind": "일반",
                "sigungu_code": "43111",
                "bjd_code": "10100",
                "plat_gb": "0",
                "bun": "0000",
                "ji": "1",
                "struct_name": "",
                "floors_above": "",
                "floors_below": "",
                "gross_area": "",
                "plat_area": "",
                "approve_date": "",
            },
            {
                "pk": "other-city",
                "ledger_kind": "일반",
                "sigungu_code": "30110",
                "bjd_code": "10100",
                "plat_gb": "0",
                "bun": "12",
                "ji": "1",
            },
        ]
        stats = ingest_building_rows(self.db, "2026-07", rows, "title.csv")
        self.assertEqual(stats["stored"], 3)
        self.assertEqual(stats["with_pnu"], 1)
        self.assertEqual(stats["held"]["block_without_canonical_pnu"], 1)
        self.assertEqual(stats["held"]["noncanonical_zero_main_lot"], 1)
        held = self.db.execute(
            "SELECT mgmt_pk FROM building_observation WHERE pnu IS NULL ORDER BY mgmt_pk"
        ).fetchall()
        self.assertEqual([row[0] for row in held], ["b2", "b3"])


if __name__ == "__main__":
    unittest.main()
