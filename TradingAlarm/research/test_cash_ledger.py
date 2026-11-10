import unittest
import pandas as pd
from cash_ledger import run_ledger,total_return_signal_frame

class DividendTests(unittest.TestCase):
    def setUp(self):
        self.index=pd.bdate_range('2024-01-01',periods=6)
        self.raw=pd.DataFrame({'open':[100,100,90,90,90,90],'high':[100,100,90,90,90,90],'low':[100,100,90,90,90,90],'close':[100,100,90,90,90,90]},index=self.index)
        self.events=[{'ex_date':str(self.index[2].date()),'pay_date':str(self.index[4].date()),'amount':10}]

    def test_entitlement_and_delayed_cash(self):
        target=pd.Series(1.,index=self.index)
        _,p=run_ledger(self.raw,target,self.events,initial=1000,lot=1,cost_bps=0,warmup=0)
        self.assertEqual(p.iloc[2].receivable,100)
        self.assertEqual(p.iloc[2].cash,0)
        self.assertEqual(p.iloc[2].nav,1)
        self.assertEqual(p.iloc[4].dividend_paid,100)
        self.assertEqual(p.iloc[4].receivable,0)

    def test_ex_date_buyer_gets_no_dividend(self):
        target=pd.Series([0,1,1,1,1,1],index=self.index,dtype=float)
        m,p=run_ledger(self.raw,target,self.events,initial=1000,lot=1,cost_bps=0,warmup=0)
        self.assertEqual(m['dividends_accrued'],0)

    def test_ex_date_seller_keeps_dividend(self):
        target=pd.Series([1,0,0,0,0,0],index=self.index,dtype=float)
        m,p=run_ledger(self.raw,target,self.events,initial=1000,lot=1,cost_bps=0,warmup=0)
        self.assertEqual(m['dividends_paid'],100)
        self.assertEqual(p.iloc[-1]['cash'],1000)

    def test_signal_series_removes_cash_distribution_gap(self):
        adjusted=total_return_signal_frame(self.raw,self.events)
        self.assertTrue((adjusted.close==100).all())
        changed=self.raw.copy()
        changed.iloc[-1]*=2
        pd.testing.assert_frame_equal(adjusted.iloc[:-1],total_return_signal_frame(changed,self.events).iloc[:-1])

    def test_lots_cost_and_cash_limits(self):
        target=pd.Series(1.,index=self.index)
        _,p=run_ledger(self.raw,target,self.events,initial=1000,lot=3,cost_bps=100,warmup=0)
        self.assertEqual(p.iloc[1].shares,9)
        self.assertTrue((p.shares%3==0).all())
        self.assertTrue((p.cash>=0).all())

    def test_fractional_target_rebalances_at_next_open(self):
        raw=self.raw.copy()
        raw.loc[:,:]=100
        target=pd.Series([.5,0,0,0,0,0],index=self.index)
        _,p=run_ledger(raw,target,initial=1000,lot=1,cost_bps=0,warmup=0)
        self.assertEqual(p.iloc[0].shares,0)
        self.assertEqual(p.iloc[1].shares,5)
        self.assertEqual(p.iloc[2].shares,0)

    def test_volatility_sizing_is_causal_and_unleveraged(self):
        import numpy as np
        from cross_market import volatility_size
        idx=pd.bdate_range('2020-01-01',periods=100)
        df=pd.DataFrame({'close':100*np.exp(np.cumsum(np.sin(np.arange(100))*.02))},index=idx)
        first=volatility_size(df)
        df.iloc[80:]*=3
        pd.testing.assert_series_equal(first.iloc[:80],volatility_size(df).iloc[:80])
        self.assertTrue(first.between(0,1).all())

if __name__=='__main__': unittest.main()
