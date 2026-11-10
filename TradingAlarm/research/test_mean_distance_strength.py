import unittest
import numpy as np
import pandas as pd
from mean_distance_strength import distance_frame
class Tests(unittest.TestCase):
 def test_plain_ema_agreement_and_prefix_units(self):
  ix=pd.bdate_range('2020-01-01',periods=150);c=pd.Series(np.exp(np.random.default_rng(4).normal(0,.03,150).cumsum()),index=ix);v=pd.Series(np.arange(150)+1.,index=ix)
  a=distance_frame(c,v);expected=(c.ewm(span=20,adjust=False).mean()>c.ewm(span=60,adjust=False).mean()).astype(float);pd.testing.assert_series_equal(a.target.iloc[59:],expected.iloc[59:],check_names=False)
  joint=distance_frame(c,v,True);pd.testing.assert_frame_equal(joint.iloc[:100],distance_frame(c.iloc[:100],v.iloc[:100],True));np.testing.assert_allclose(joint,distance_frame(c*100,v*1000,True),rtol=1e-9,atol=1e-10,equal_nan=True)
if __name__=='__main__':unittest.main()
