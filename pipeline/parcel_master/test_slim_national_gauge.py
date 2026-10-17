import unittest

from parcel_master.slim_national_gauge import column_indexes, parse_row, projected_bytes


HEADER = (
    "고유번호,법정동코드,법정동명,대장구분코드,대장구분명,지번,토지일련번호,"
    "기준연도,기준월,지목코드,지목명,토지면적,용도지역코드1,용도지역명1,"
    "용도지역코드2,용도지역명2,토지이용상황코드,토지이용상황,지형높이코드,지형높이,"
    "지형형상코드,지형형상,도로접면코드,도로접면,공시지가,데이터기준일자"
).split(",")


class SlimGaugeTests(unittest.TestCase):
    def test_year_alias_and_target_row(self):
        indexes = column_indexes(["기준년도" if name == "기준연도" else name for name in HEADER])
        parts = [""] * len(HEADER)
        parts[0] = "4311110100100010001"
        parts[7] = "2026"
        parts[8] = "1"
        parts[24] = "100"
        parts[25] = "2026-05-12"
        parsed = parse_row(parts, indexes)
        self.assertEqual(parsed[0], "4311110100100010001")
        self.assertEqual(parsed[1], "2026-05-12")
        self.assertEqual(parsed[2], "2026")

    def test_other_asof_is_skipped(self):
        indexes = column_indexes(HEADER)
        parts = ["4311110100100010001", *([""] * 24), "2017-10-17"]
        self.assertIsNone(parse_row(parts, indexes))

    def test_full_source_projection_exceeds_planning_band(self):
        projected = projected_bytes(4_524_145_133)
        self.assertGreater(projected, 20 * 1024**3)


if __name__ == "__main__":
    unittest.main()
