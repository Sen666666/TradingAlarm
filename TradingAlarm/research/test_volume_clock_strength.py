import unittest
import numpy as np
import pandas as pd
from volume_clock_strength import clock_slope,volume_clock_frame
from pairwise_trend_strength import pairwise_frame
class Tests(unittest.TestCase):
 def test_constant_volume_reduces_to_original(self):
  p=pd.Series(np.exp(np.cumsum(np.random.default_rng(7).normal(0,.02,100))));v=p*0+100
  pd.testing.assert_frame_equal(volume_clock_frame(p,v),pairwise_frame(p,v),check_exact=True)
 def test_clock_linear_path_and_extreme_positive_intervals(self):
  v=np.exp(np.linspace(-8,8,21));t=np.cumsum(v/v.mean());self.assertAlmostEqual(clock_slope(3+.003*t,v),.003,places=12)
  v=np.r_[1e12,np.ones(20)*1e-12];self.assertTrue(np.isfinite(clock_slope(np.arange(21)*.001,v)))
 def test_units_prefix_sign_and_flat(self):
  rng=np.random.default_rng(42);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,90))));v=pd.Series(np.exp(rng.normal(5,1,90)));f=volume_clock_frame(p,v)
  pd.testing.assert_frame_equal(f.iloc[:60],volume_clock_frame(p.iloc[:60],v.iloc[:60]))
  np.testing.assert_allclose(f,volume_clock_frame(p*13,v*700),atol=1e-11,equal_nan=True)
  np.testing.assert_allclose((f.strength+volume_clock_frame(1/p,v).strength).iloc[21:],10,atol=1e-10)
  self.assertTrue(volume_clock_frame(p*0+10,v).strength.iloc[21:].eq(5).all())
if __name__=='__main__':unittest.main()
