import unittest
from dataclasses import replace
from stock_execution import OpenState,next_open_guard


class StockExecutionTests(unittest.TestCase):
    def state(self):
        return OpenState('2020-01-03',10.,True,'2020-01-03',11.,9.,state_verified=True)

    def check(self,state,side='buy',**kwargs):
        return next_open_guard(state,side,'2020-01-02',**kwargs)

    def test_stale_limits_and_unknown_states_never_fill(self):
        self.assertFalse(self.check(replace(self.state(),limits_date='2020-01-02')).allowed)
        self.assertFalse(self.check(replace(self.state(),trading=None)).allowed)
        self.assertFalse(self.check(replace(self.state(),state_verified=False)).allowed)

    def test_limit_queue_not_assumed_fill(self):
        self.assertFalse(self.check(replace(self.state(),raw_open=11.)).allowed)
        self.assertFalse(self.check(replace(self.state(),raw_open=9.),'sell',sellable_quantity=100).allowed)
        self.assertTrue(self.check(replace(self.state(),raw_open=9.)).allowed)

    def test_t_plus_one_inventory_and_signal_lag(self):
        self.assertFalse(self.check(self.state(),'sell',sellable_quantity=0).allowed)
        self.assertTrue(self.check(self.state(),'sell',sellable_quantity=100).allowed)
        self.assertFalse(next_open_guard(self.state(),'buy','2020-01-03').allowed)

    def test_suspended_stock_cannot_exit_at_old_price(self):
        self.assertEqual(self.check(replace(self.state(),trading=False),'sell',sellable_quantity=100).reason,'suspended')

    def test_slippage_does_not_create_impossible_execution(self):
        self.assertFalse(self.check(replace(self.state(),raw_open=10.99),slippage_bps=20).allowed)

    def test_unlimited_requires_explicit_dated_state(self):
        self.assertFalse(self.check(replace(self.state(),upper_limit=None,lower_limit=None)).allowed)
        unlimited=replace(self.state(),upper_limit=None,lower_limit=None,explicitly_unlimited=True)
        self.assertTrue(self.check(unlimited).allowed)


if __name__=='__main__':unittest.main()
