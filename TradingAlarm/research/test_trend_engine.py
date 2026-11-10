import unittest
import numpy as np
import pandas as pd
from trend_engine import frame,features,signals,structure_change_v2,backtest

def fixture():
    dates=pd.bdate_range('2019-01-01',periods=600)
    rng=np.random.default_rng(9)
    close=100*np.exp(np.cumsum(rng.normal(.0004,.015,len(dates))))
    return frame([{'date':str(d.date()),'open':c*.998,'high':c*1.02,'low':c*.98,'close':c} for d,c in zip(dates,close)])

class CausalTests(unittest.TestCase):
    def test_future_data_cannot_change_past(self):
        a=fixture()
        b=a.copy()
        b.loc[b.index[450]:,['open','high','low','close']]*=7
        pd.testing.assert_frame_equal(signals(a).iloc[:450],signals(b).iloc[:450])
        pd.testing.assert_frame_equal(structure_change_v2(a).iloc[:450],structure_change_v2(b).iloc[:450])

    def test_signal_does_not_trade_same_day(self):
        df=fixture()
        target=pd.Series(0.,index=df.index)
        target.iloc[300:]=1
        _,path=backtest(df,target,cost_bps=0)
        self.assertEqual(path.loc[df.index[300],'position'],0)
        self.assertEqual(path.loc[df.index[301],'position'],1)
        self.assertAlmostEqual(path.loc[df.index[301],'return'],1/.998-1)

    def test_cost_and_cash_accounting(self):
        df=fixture()
        target=pd.Series(0.,index=df.index)
        metrics,path=backtest(df,target,cost_bps=30)
        self.assertEqual(metrics['total_return'],0)
        target[:]=1.
        a,_=backtest(df,target,cost_bps=0)
        b,_=backtest(df,target,cost_bps=30)
        self.assertAlmostEqual((1+b['total_return'])/(1+a['total_return']),.997)

    def test_scale_invariance(self):
        a=fixture()
        b=a.copy()*100
        np.testing.assert_allclose(features(a).score,features(b).score,atol=1e-10,equal_nan=True)

if __name__=='__main__':
    unittest.main()
