import unittest
import numpy as np
import pandas as pd
from stock_smooth_momentum import smooth_feature
class SmoothTests(unittest.TestCase):
 def test_sign_score_and_skip_recent_window(self):
  c=pd.Series(np.arange(200.)+100);a=pd.Series(True,index=c.index)
  self.assertEqual(smooth_feature(c,a).iloc[150],-1)
  c.iloc[130:]=1
  self.assertEqual(smooth_feature(c,a).iloc[150],-1)
 def test_missing_bar_invalidates_window(self):
  c=pd.Series(np.arange(200.)+100);a=pd.Series(True,index=c.index);a.iloc[70]=False
  self.assertTrue(pd.isna(smooth_feature(c,a).iloc[150]))
if __name__=='__main__':unittest.main()
