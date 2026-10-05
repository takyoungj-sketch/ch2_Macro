import unittest
from ledger_consumer_input_preview import price_input


class ConsumerInputTests(unittest.TestCase):
    def test_unknown_identity_never_receives_price(self):
        result=price_input('unknown_land_type',None,(2026,'2026','1000','positive'))
        self.assertIsNone(result['value_krw_per_m2'])
        self.assertEqual(result['status'],'identity_blocked')

    def test_price_quality_and_year_are_independent(self):
        pnu='4311112345100120000'
        for record,status in ((None,'not_observed_in_selected_snapshot'),
                              ((None,'','1000','positive'),'unknown_price_year'),
                              ((2026,'2026','****','source_overflow'),'source_overflow'),
                              ((2026,'2026','0','missing_or_nonpositive'),'missing_or_nonpositive')):
            result=price_input('canonical_address',pnu,record)
            self.assertEqual(result['status'],status)
            self.assertIsNone(result['value_krw_per_m2'])
        result=price_input('canonical_address',pnu,(2026,'2026','1000','positive'))
        self.assertEqual(result['value_krw_per_m2'],'1000')
        self.assertEqual(result['price_year'],2026)


if __name__=='__main__': unittest.main()
