import unittest
import numpy as np
import pandas as pd
from global_signal_transfer import run_period


class GlobalSignalTests(unittest.TestCase):
    def fixture(self,extra=False):
        dates=pd.bdate_range('2007-01-02',periods=6)
        events=[dict(ex_date=str(dates[i].date()),amount=v) for i,v in [(1,2.),(2,3.),(3,5.)]]
        if extra:events.append(dict(ex_date=str(dates[4].date()),amount=100.))
        cash=pd.Series(0.,index=dates)
        for e in events:cash.loc[e['ex_date']]+=e['amount']
        raw=pd.DataFrame(dict(open=100.,high=101.,low=99.,close=100.,volume=1000.),index=dates)
        f=pd.DataFrame(dict(date=dates,open=100+cash.cumsum(),signal_close=100+cash.cumsum(),
            observed_bar=True,positive_volume=True,atr20=1.,breakout55=[99.]+[999.]*5,sma200=90.,
            exit_signal=[False,False,True,False,False,False]),index=dates)
        return raw,events,f

    def test_exdate_entitlement_and_raw_price_fees(self):
        raw,e,f=self.fixture();r=run_period('test',raw,e,f,'2007-01-01','2007-01-31')[0]
        self.assertEqual(r['distribution_entitlement_per_unit'],8.)
        self.assertEqual(r['economic_pnl_before_cost_per_unit'],8.)
        self.assertAlmostEqual(r['R_cost15'],(8.-.3)/4.)

    def test_future_distribution_does_not_change_closed_trade(self):
        a=run_period('test',*self.fixture(),'2007-01-01','2007-01-31')
        b=run_period('test',*self.fixture(True),'2007-01-01','2007-01-31')
        self.assertEqual(a,b)


if __name__=='__main__':unittest.main()
