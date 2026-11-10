import unittest
import numpy as np
import pandas as pd
from a_stock_monthly252 import simulate


class MonthlySignalTests(unittest.TestCase):
    def fixture(self):
        d=pd.bdate_range('2021-12-30','2022-03-31');n=len(d)
        return d,np.full(n,100.),np.full(n,100.),np.ones(n,dtype=bool),np.ones(n,dtype=bool),np.ones(n,dtype=bool)

    def test_prior_signal_and_delayed_open(self):
        d,o,c,s,a,x=self.fixture()
        out=simulate(d,o,c,s,a,x,[d[-1]],'X',delay=1)[str(d[-1].date())]
        self.assertEqual(out[0]['entry_date'],'2022-01-04')
        self.assertEqual(out[0]['signal_date'],'2021-12-31')
        self.assertEqual(out[0]['status'],'open_at_cutoff')

    def test_daily_pending_delay_survives_unchanged_signal(self):
        d,o,c,s,a,x=self.fixture()
        s[d>=pd.Timestamp('2022-01-10')]=False
        out=simulate(d,o,c,s,a,x,[d[-1]],'X',delay=1,cadence='daily')[str(d[-1].date())]
        self.assertEqual(out[0]['entry_date'],'2022-01-04')
        self.assertEqual(out[0]['exit_date'],'2022-01-12')

    def test_daily_reversal_cancels_unfilled_entry(self):
        d,o,c,s,a,x=self.fixture();s[d>=pd.Timestamp('2022-01-03')]=False
        out=simulate(d,o,c,s,a,x,[d[-1]],'X',delay=1,cadence='daily')[str(d[-1].date())]
        self.assertEqual(out,[])

    def test_no_exit_when_terminal_cannot_trade(self):
        d,o,c,s,a,x=self.fixture();a[d>pd.Timestamp('2022-01-20')]=False;s[d>=pd.Timestamp('2022-01-21')]=False
        out=simulate(d,o,c,s,a,x,[d[-1]],'X')[str(d[-1].date())]
        self.assertEqual(out[0]['status'],'terminal_unknown')
        self.assertIsNone(out[0]['exit_date']);self.assertEqual(out[0]['mark_date'],'2022-01-20')

    def test_future_change_cannot_change_earlier_snapshot(self):
        d,o,c,s,a,x=self.fixture();cuts=[pd.Timestamp('2022-01-31'),d[-1]]
        before=simulate(d,o,c,s,a,x,cuts,'X')
        s[d>=pd.Timestamp('2022-02-10')]=False;o[d>=pd.Timestamp('2022-02-10')]=20
        after=simulate(d,o,c,s,a,x,cuts,'X')
        self.assertEqual(before['2022-01-31'],after['2022-01-31'])
        self.assertEqual(after[str(d[-1].date())][0]['exit_date'],'2022-03-01')

if __name__=='__main__':unittest.main()
