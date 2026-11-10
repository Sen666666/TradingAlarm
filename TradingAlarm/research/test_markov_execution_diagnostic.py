import unittest
import numpy as np
import pandas as pd
from monthly_ah_engine import run
from markov_execution_diagnostic import components, order_groups


class ExecutionDiagnosticTests(unittest.TestCase):
    def test_pending_reversal_cancels_delayed_entry(self):
        dates=pd.bdate_range('2025-01-01',periods=30)
        raw=pd.DataFrame(dict(open=100.,high=101.,low=99.,close=100.,volume=1e8),index=dates)
        assets={'X':dict(raw=raw,signal=raw,currency='CNY',lot=1,splits=[],dividends=[])}
        signal=pd.Series(0.,index=dates);signal.iloc[23]=1.
        args=dict(assets=assets,start=str(dates[22].date()),end=str(dates[-1].date()),policy='score_change',cadence='daily',signals={'X':signal},fx_override=pd.Series(1.,index=dates))
        _,_,base,_=run(**args,delay=0)
        _,_,delayed,_=run(**args,delay=1)
        self.assertEqual(len(base),2)
        self.assertEqual(delayed,[])

    def test_decomposition_and_partial_fills(self):
        v=components(100,101,99,102)
        self.assertAlmostEqual(v['open_to_open'],np.log(102/101))
        orders=[dict(symbol='X',signal_date='2026-01-01',units=q,fee=1,date='2026-01-02') for q in [100,200,-100]]
        g=order_groups(orders)
        self.assertEqual(g['X','2026-01-01','entry']['units'],300)
        self.assertEqual(len(g),2)


if __name__=='__main__':unittest.main()
