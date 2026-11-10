import unittest
import numpy as np
import pandas as pd
from trend_exit_disagreement import features,forward_label
class Tests(unittest.TestCase):
 def test_past_only_units_and_horizon(self):
  ix=pd.bdate_range('2024-01-01',periods=90);c=pd.Series(np.exp(np.random.default_rng(2).normal(0,.01,90).cumsum()),index=ix);v=pd.Series(np.arange(90)+1.,index=ix)
  f=features(c,v);pd.testing.assert_frame_equal(f.iloc[:50],features(c.iloc[:50],v.iloc[:50]));np.testing.assert_allclose(f,features(c*100,v*10),rtol=1e-9,atol=1e-10,equal_nan=True)
  self.assertIsNone(forward_label(c,69));self.assertEqual(forward_label(c,68)['label_end'],str(ix[-1].date()))
if __name__=='__main__':unittest.main()
