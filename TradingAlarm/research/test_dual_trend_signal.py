import unittest
import numpy as np
import pandas as pd
from strategy_signals import build_signals
class Tests(unittest.TestCase):
 def test_fixed_two_horizons_and_prefix(self):
  ix=pd.bdate_range('2020-01-01',periods=150);c=pd.Series(np.exp(np.r_[np.arange(100)*.01,.99-np.arange(50)*.02]),index=ix)
  def run(x):return build_signals({'a':{'signal':pd.DataFrame({'close':x})}},'dual21_63')['a']
  s=run(c);self.assertTrue(s.iloc[:63].eq(0).all());self.assertTrue(s.isin([0,.5,1]).all());self.assertIn(.5,s.values);pd.testing.assert_series_equal(s.iloc[:120],run(c.iloc[:120]))
if __name__=='__main__':unittest.main()
