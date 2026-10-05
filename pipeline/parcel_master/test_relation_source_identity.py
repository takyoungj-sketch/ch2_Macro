import unittest
from audit_cheongju_relation_source_evidence import pnu_from_fields


class SourceIdentityTests(unittest.TestCase):
    def test_land_and_mountain_are_distinct(self):
        self.assertEqual(pnu_from_fields(['43111','10100','0','1','2'],0),'4311110100100010002')
        self.assertEqual(pnu_from_fields(['43111','10100','1','1','2'],0),'4311110100200010002')

    def test_unknown_land_type_is_not_assumed_land(self):
        self.assertIsNone(pnu_from_fields(['43111','10100','','1','2'],0))

    def test_missing_lot_is_not_assumed_zero(self):
        self.assertIsNone(pnu_from_fields(['43111','10100','0','','2'],0))

    def test_overlong_lot_is_not_truncated(self):
        self.assertIsNone(pnu_from_fields(['43111','10100','0','12345','2'],0))


if __name__=='__main__': unittest.main()
