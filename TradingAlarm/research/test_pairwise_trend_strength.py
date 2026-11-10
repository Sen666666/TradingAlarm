import unittest
import numpy as np
import pandas as pd
from pairwise_trend_strength import pair_slope,pairwise_frame
class Tests(unittest.TestCase):
    def test_linear_recovery_sign_and_units(self):
        y=np.arange(21)*.01;v=np.arange(1,22)
        self.assertAlmostEqual(pair_slope(y,v),.01)
        q=np.random.default_rng(1).normal(size=21).cumsum()
        self.assertAlmostEqual(pair_slope(-q,v),-pair_slope(q,v))
        self.assertAlmostEqual(pair_slope(q+10,v*100),pair_slope(q,v))
    def test_prefix_and_flat(self):
        ix=pd.bdate_range('2020-01-01',periods=80);c=pd.Series(np.exp(np.random.default_rng(2).normal(0,.01,80).cumsum()),index=ix);v=pd.Series(1.,index=ix)
        a=pairwise_frame(c,v);b=pairwise_frame(c.iloc[:50],v.iloc[:50]);pd.testing.assert_frame_equal(a.iloc[:50],b)
        self.assertTrue(pairwise_frame(v,v).strength.iloc[21:].eq(5).all())
if __name__=='__main__':unittest.main()
