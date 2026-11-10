import unittest
import numpy as np
import pandas as pd
from hk_holding_horizon import capped_breakout
from trend_engine import baselines
class HorizonTests(unittest.TestCase):
 def sample(self):
  idx=pd.bdate_range('2020-01-01',periods=200);c=np.arange(200.)+100
  return pd.DataFrame({'close':c,'high':c+.1,'low':c-.1},index=idx)
 def test_exact_ten_session_cap_and_no_same_close_reentry(self):
  p=capped_breakout(self.sample(),10)
  self.assertEqual(p.iloc[55:65].tolist(),[1.]*10)
  self.assertEqual(p.iloc[65],0)
  self.assertEqual(p.iloc[66],1)
 def test_no_cap_identical_and_future_independent(self):
  f=self.sample();p=capped_breakout(f,20)
  pd.testing.assert_series_equal(capped_breakout(f),baselines(f).donchian55_20,check_names=False)
  f.iloc[150:]*=.1
  pd.testing.assert_series_equal(p.iloc[:150],capped_breakout(f,20).iloc[:150])
if __name__=='__main__':unittest.main()
