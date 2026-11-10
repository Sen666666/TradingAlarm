import unittest
import numpy as np
import pandas as pd
from rms_direction_strength import rms_direction_frame
from range_direction_strength import range_frame
class Tests(unittest.TestCase):
 def test_matched_sign_and_reduced_magnitude_prefix_units(self):
  ix=pd.bdate_range('2020-01-01',periods=180);c=pd.Series(np.exp(np.random.default_rng(4).normal(0,.025,180).cumsum()),index=ix);v=pd.Series(np.arange(180)+10.,index=ix);ohlc=pd.DataFrame({'high':c,'low':c,'close':c})
  for joint in [False,True]:
   a=rms_direction_frame(c,v,joint);b=range_frame(ohlc,v,joint,True);mask=a.balance.notna()&b.balance.notna()
   np.testing.assert_array_equal(np.sign(a.balance[mask]),np.sign(b.balance[mask]));self.assertTrue((a.balance[mask].abs()<=b.balance[mask].abs()+1e-12).all())
   pd.testing.assert_frame_equal(a.iloc[:100],rms_direction_frame(c.iloc[:100],v.iloc[:100],joint));np.testing.assert_allclose(a,rms_direction_frame(c*100,v*1000,joint),atol=1e-10,rtol=1e-9,equal_nan=True)
if __name__=='__main__':unittest.main()
