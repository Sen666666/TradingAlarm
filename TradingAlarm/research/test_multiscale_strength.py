import unittest
import numpy as np
import pandas as pd
from multiscale_trend_strength import multiscale_frame
class Checks(unittest.TestCase):
    def test_causal_and_units(self):
        rng=np.random.default_rng(718);ix=pd.date_range('2020-01-01',periods=160)
        p=pd.Series(np.exp(np.cumsum(rng.normal(.001,.02,160))),index=ix);v=pd.Series(rng.uniform(10,100,160),index=ix)
        f=multiscale_frame(p,v)
        pd.testing.assert_frame_equal(f.iloc[:100],multiscale_frame(p.iloc[:100],v.iloc[:100]))
        np.testing.assert_allclose(f,multiscale_frame(p*100,v*50),atol=1e-10,equal_nan=True)
        self.assertTrue(f.strength.dropna().between(0,10).all())
    def test_known_paths(self):
        ix=pd.date_range('2020-01-01',periods=100);v=pd.Series(1.,index=ix)
        for drift,expected in [(0,5),(.01,10),(-.01,0)]:
            p=pd.Series(np.exp(np.arange(100)*drift),index=ix)
            self.assertAlmostEqual(multiscale_frame(p,v).strength.iloc[-1],expected,delta=.05)
if __name__=='__main__':unittest.main()
