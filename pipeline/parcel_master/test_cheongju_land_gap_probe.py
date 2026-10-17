import unittest

from parcel_master.cheongju_land_gap_probe import explain_gap, plate_difference


def _plate(asof, year, jimok, area, zone, price="10"):
    zones = frozenset({zone}) if zone else frozenset()
    return (asof, year, 1, jimok, area, zones, price)


def _world(plates):
    for rows in plates.values():
        rows.sort()
    index = {}
    by_bjd = {}
    for pnu, rows in plates.items():
        by_bjd.setdefault(pnu[:10], []).append(pnu)
        for row in rows:
            index.setdefault((pnu[:10], row[3], row[4]), set()).add(pnu)
    return index, by_bjd


class GapReasonTests(unittest.TestCase):
    def test_blank_zone_is_separate_from_a_changed_area(self):
        blank = [_plate("2019-08-08", 2019, "대", "100.0", "")]
        self.assertEqual(plate_difference(blank, "대", "100.0", "자녹", "blank"), "zone_blank")
        changed = [_plate("2019-08-08", 2019, "대", "200.0", "자녹")]
        self.assertEqual(plate_difference(changed, "대", "100.0", "자녹", "mapped"), "area_changed")

    def test_single_later_parcel_with_blank_zone(self):
        pnu = "4311110100100120000"
        plates = {
            pnu: [
                _plate("2019-08-08", 2019, "대", "100.0", ""),
                _plate("2024-07-30", 2024, "대", "100.0", "자녹"),
            ]
        }
        index, by_bjd = _world(plates)
        status, reason, earlier = explain_gap(
            beopjungri_code="4311110100",
            land_category="대",
            zone_type="자녹",
            area_sqm="100",
            lot_display="12",
            contract_date="2020-06-01",
            index=index,
            plates=plates,
            by_bjd=by_bjd,
            zone_by_pnu={pnu: {"2019-08-08": "blank", "2024-07-30": "mapped"}},
        )
        self.assertEqual(status, "no_prior_plate")
        self.assertEqual(reason, "zone_blank")
        self.assertFalse(earlier)

    def test_area_change_after_an_earlier_matching_plate(self):
        pnu = "4311110100100120000"
        plates = {
            pnu: [
                _plate("2018-08-08", 2018, "대", "100.0", "자녹"),
                _plate("2019-08-08", 2019, "대", "200.0", "자녹"),
                _plate("2024-07-30", 2024, "대", "100.0", "자녹"),
            ]
        }
        index, by_bjd = _world(plates)
        status, reason, earlier = explain_gap(
            beopjungri_code="4311110100",
            land_category="대",
            zone_type="자녹",
            area_sqm="100",
            lot_display="12",
            contract_date="2020-06-01",
            index=index,
            plates=plates,
            by_bjd=by_bjd,
            zone_by_pnu={pnu: {}},
        )
        self.assertEqual(status, "no_prior_plate")
        self.assertEqual(reason, "area_changed")
        self.assertTrue(earlier)

    def test_first_seen_after_contract_and_unmatched_lot(self):
        pnu = "4311110100100120000"
        plates = {pnu: [_plate("2024-07-30", 2024, "대", "100.0", "자녹")]}
        index, by_bjd = _world(plates)
        status, reason, _earlier = explain_gap(
            beopjungri_code="4311110100",
            land_category="대",
            zone_type="자녹",
            area_sqm="100",
            lot_display="12",
            contract_date="2020-06-01",
            index=index,
            plates=plates,
            by_bjd=by_bjd,
            zone_by_pnu={pnu: {"2024-07-30": "mapped"}},
        )
        self.assertEqual((status, reason), ("no_prior_plate", "first_seen_after_contract"))
        missing, missing_reason, _earlier = explain_gap(
            beopjungri_code="4311110100",
            land_category="대",
            zone_type="자녹",
            area_sqm="100",
            lot_display="99",
            contract_date="2020-06-01",
            index=index,
            plates=plates,
            by_bjd=by_bjd,
            zone_by_pnu={pnu: {}},
        )
        self.assertEqual((missing, missing_reason), ("no_candidate", "lot_unmatched"))


if __name__ == "__main__":
    unittest.main()
