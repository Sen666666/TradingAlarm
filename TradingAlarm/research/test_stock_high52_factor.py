import unittest
import pandas as pd
import numpy as np
from stock_high52_factor import high_ratio
class High52Tests(unittest.TestCase):
 def test_warmup_bounds_and_future_independence(self):
  p=pd.Series(np.linspace(10,30,320));a=high_ratio(p)
  self.assertTrue(a.iloc[:251].isna().all());self.assertEqual(a.iloc[251],1.)
  q=p.copy();q.iloc[290:]*=3;pd.testing.assert_series_equal(a.iloc[:290],high_ratio(q).iloc[:290])
 def test_window_rolls_off_old_high_and_scale_invariant(self):
  p=pd.Series([100.]+[50.]*300);a=high_ratio(p)
  self.assertEqual(a.iloc[251],.5);self.assertEqual(a.iloc[252],1.)
  pd.testing.assert_series_equal(a,high_ratio(p*7))
if __name__=='__main__':unittest.main()
