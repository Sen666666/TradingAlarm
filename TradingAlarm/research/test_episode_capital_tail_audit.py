import unittest
from episode_capital_tail_audit import attach_cash
class Tests(unittest.TestCase):
    def test_partial_fills_fees_and_sell_not_in_denominator(self):
        e=[dict(symbol='A',entry_date='2022-01-01',exit_date='2022-01-03',trade_fees=6.,pnl=20.)]
        o=[dict(symbol='A',date='2022-01-01',units=2,raw_open=10,fx=2,fee=1),dict(symbol='A',date='2022-01-02',units=3,raw_open=10,fx=2,fee=2),dict(symbol='A',date='2022-01-03',units=-5,raw_open=12.6,fx=2,fee=3)]
        r=attach_cash(e,o)[0];self.assertEqual(r['buy_cash'],103);self.assertEqual(r['return_on_buy_cash'],20/103);self.assertEqual(r['buy_orders'],2)
    def test_ambiguous_or_unassigned_orders_fail(self):
        o=[dict(symbol='B',date='2022-01-01',units=1,raw_open=1,fx=1,fee=0)]
        with self.assertRaises(ValueError):attach_cash([],o)
if __name__=='__main__':unittest.main()
