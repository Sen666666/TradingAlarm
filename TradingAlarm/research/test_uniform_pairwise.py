import unittest
import numpy as np
import pandas as pd
from pairwise_trend_strength import pair_slope,pairwise_frame
class Tests(unittest.TestCase):
    def test_exact_unweighted_median(self):
        y=np.random.default_rng(42).normal(size=21).cumsum();i,j=np.triu_indices(21,1)
        self.assertAlmostEqual(pair_slope(y,recency=False),np.median((y[j]-y[i])/(j-i)))
        self.assertAlmostEqual(pair_slope(-y,recency=False),-pair_slope(y,recency=False))
    def test_prefix_and_units(self):
        rng=np.random.default_rng(4);c=pd.Series(np.exp(rng.normal(0,.03,80).cumsum()));v=pd.Series(rng.uniform(1,100,80))
        a=pairwise_frame(c,v,recency=False)
        pd.testing.assert_frame_equal(a.iloc[:60],pairwise_frame(c.iloc[:60],v.iloc[:60],recency=False))
        np.testing.assert_allclose(a,pairwise_frame(c*100,v*10,recency=False),equal_nan=True,atol=1e-12)
if __name__=='__main__':unittest.main()
