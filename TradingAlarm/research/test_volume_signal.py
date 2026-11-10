import unittest
import numpy as np
import pandas as pd
from strategy_signals import build_signals

class VolumeTests(unittest.TestCase):
    def asset(self):
        close=np.r_[np.full(70,100.),105.,108.,110.,111.,112.];f=pd.DataFrame({'close':close,'high':close+1,'low':close-1,'volume':100.},index=pd.bdate_range('2024-01-01',periods=len(close)))
        f.iloc[70,f.columns.get_loc('volume')]=1.
        return {'raw':f.copy(),'signal':f.copy()}
    def test_gate_only_controls_entry(self):
        a=self.asset();a['raw'].iloc[72:,a['raw'].columns.get_loc('volume')]=1.
        base=build_signals({'X':a},'channel21_63_initial2atr')['X'];g=build_signals({'X':a},'channel21_63_volume')['X']
        self.assertEqual(base.iloc[70],1.)
        self.assertEqual(g.iloc[70],0.)
        self.assertTrue(g.iloc[71:].eq(1.).all())
    def test_volume_units_and_future_independence(self):
        a=self.asset();g=build_signals({'X':a},'channel21_63_volume')['X'];a['raw']['volume']*=100
        pd.testing.assert_series_equal(g,build_signals({'X':a},'channel21_63_volume')['X'])
        a['raw'].iloc[72:,a['raw'].columns.get_loc('volume')]=1e10
        pd.testing.assert_series_equal(g.iloc[:72],build_signals({'X':a},'channel21_63_volume')['X'].iloc[:72])

if __name__=='__main__':unittest.main()
