import unittest
import pandas as pd
from monthly_ah_engine import allocation_weights,run
from test_monthly_ah import MonthlyAHTests


class SizingTests(unittest.TestCase):
    def asset(self):
        a=MonthlyAHTests().asset()
        f=a['signal'].copy();f.loc[:,'close']=100.;f.loc[:,'high']=105.;f.loc[:,'low']=95.
        return dict(a,signal=f)

    def test_units_warmup_scale_and_future(self):
        a=self.asset();w=allocation_weights({'A':a},'atr_risk_cap')['A']
        self.assertTrue(w.iloc[:20].eq(0).all())
        self.assertAlmostEqual(w.iloc[20],.2)  # .04 / (2 * 10 / 100)
        b=dict(a,signal=a['signal']*10)
        pd.testing.assert_series_equal(w,allocation_weights({'A':b},'atr_risk_cap')['A'])
        b['signal'].iloc[100:]*=5
        pd.testing.assert_series_equal(w.iloc[:100],allocation_weights({'A':b},'atr_risk_cap')['A'].iloc[:100])

    def test_decision_uses_prior_bar_and_holds_shares(self):
        a=self.asset();idx=a['raw'].index;start=idx[280]
        signals={'A':pd.Series(1.,index=idx)}
        a['signal'].loc[start:,'high']=1000.
        _,_,orders,decisions=run({'A':a},str(start.date()),str(idx[-1].date()),policy='score_change',
                              cadence='daily',signals=signals,allocation='atr_risk_cap',fx_override=pd.Series(1.,index=idx))
        prior_price=a['raw'].loc[idx[279],'close'];lot=a['lot']
        expected=int(.2*1e6/prior_price/lot)*lot
        self.assertEqual(decisions[0]['targets']['A'],expected)
        self.assertTrue(all(o['units']>0 for o in orders))
        self.assertEqual(sum(o['units'] for o in orders),expected)


if __name__=='__main__':unittest.main()
