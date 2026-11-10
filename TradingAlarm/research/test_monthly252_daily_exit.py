import unittest
import pandas as pd
import test_a_stock_monthly252 as fixtures
from a_stock_monthly252 import simulate


class DailyExitTests(unittest.TestCase):
    def fixture(self):return fixtures.MonthlySignalTests().fixture()

    def test_daily_exit_is_next_open_not_signal_close(self):
        d,o,c,s,a,x=self.fixture();s[d>=pd.Timestamp('2022-01-10')]=False
        old=simulate(d,o,c,s,a,x,[d[-1]],'X')[str(d[-1].date())]
        new=simulate(d,o,c,s,a,x,[d[-1]],'X',daily_exit=True)[str(d[-1].date())]
        self.assertEqual(old[0]['entry_date'],new[0]['entry_date'])
        self.assertEqual(new[0]['exit_date'],'2022-01-11')
        self.assertEqual(old[0]['exit_date'],'2022-02-01')

    def test_sticky_exit_survives_rebound_and_month_replacement(self):
        d,o,c,s,a,x=self.fixture();s[d==pd.Timestamp('2022-01-10')]=False
        x[(d>=pd.Timestamp('2022-01-11'))&(d<pd.Timestamp('2022-02-02'))]=False
        rows=simulate(d,o,c,s,a,x,[d[-1]],'X',delay=1,daily_exit=True)[str(d[-1].date())]
        self.assertEqual(rows[0]['exit_date'],'2022-02-03')
        self.assertEqual(rows[1]['entry_date'],'2022-03-02')

    def test_future_data_does_not_change_earlier_snapshot(self):
        d,o,c,s,a,x=self.fixture();cuts=[pd.Timestamp('2022-01-31'),d[-1]]
        old=simulate(d,o,c,s,a,x,cuts,'X',daily_exit=True)
        s[d>=pd.Timestamp('2022-02-10')]=False;o[d>=pd.Timestamp('2022-02-10')]=20
        new=simulate(d,o,c,s,a,x,cuts,'X',daily_exit=True)
        self.assertEqual(old['2022-01-31'],new['2022-01-31'])
        self.assertEqual(new[str(d[-1].date())][0]['exit_date'],'2022-02-11')

if __name__=='__main__':unittest.main()
