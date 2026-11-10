import unittest
import numpy as np
import pandas as pd
import test_monthly_ah as fixtures
from strategy_signals import build_signals
from monthly_ah_engine import run

class StagedTests(unittest.TestCase):
    def test_confirmation_latches_and_future_does_not_change_past(self):
        close=np.r_[np.full(70,100.),105.,107.,111.,108.,107.];f=pd.DataFrame(dict(close=close,high=close+1,low=close-1),index=pd.bdate_range('2024-01-01',periods=len(close)))
        s=build_signals({'A':{'signal':f}},'channel21_63_staged')['A']
        self.assertEqual(s.iloc[70],.5);self.assertEqual(s.iloc[71],.5);self.assertTrue(s.iloc[72:].eq(1).all())
        pd.testing.assert_series_equal(s,build_signals({'A':{'signal':f*10}},'channel21_63_staged')['A'])
        f.iloc[73:]*=.5
        pd.testing.assert_series_equal(s.iloc[:73],build_signals({'A':{'signal':f}},'channel21_63_staged')['A'].iloc[:73])
    def test_promotion_cannot_sell_when_risk_weight_falls(self):
        a=fixtures.MonthlyAHTests().asset();idx=a['raw'].index;signal=pd.Series(0.,index=idx);signal.iloc[279]=.5;signal.iloc[280:283]=1.
        a['signal'].loc[idx[280]:,'high']=a['signal'].close.max()*100
        _,_,orders,decisions=run({'A':a},str(idx[280].date()),str(idx[284].date()),policy='score_change',cadence='daily',signals={'A':signal},allocation='atr_risk_cap',fx_override=pd.Series(1.,index=idx))
        self.assertGreater(orders[0]['units'],0)
        self.assertFalse(any(o['units']<0 and o['date']==str(idx[281].date()) for o in orders))
        self.assertEqual(decisions[1]['targets']['A'],orders[0]['units'])

if __name__=='__main__':unittest.main()
