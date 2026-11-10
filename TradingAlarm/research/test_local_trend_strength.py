import unittest
import numpy as np
import pandas as pd
from local_trend_strength import local_trend_frame


class LocalTrendTests(unittest.TestCase):
    def test_prefix_and_units(self):
        rng=np.random.default_rng(471); idx=pd.bdate_range('2020-01-01',periods=250)
        p=pd.Series(np.exp(np.cumsum(rng.normal(.001,.02,250))),index=idx)
        v=pd.Series(rng.lognormal(8,1,250),index=idx)
        for joint in [False,True]:
            f=local_trend_frame(p,v,joint)
            pd.testing.assert_frame_equal(f.iloc[:160],local_trend_frame(p.iloc[:160],v.iloc[:160],joint))
            g=local_trend_frame(p*100,v*1000,joint)
            np.testing.assert_allclose(f.strength,g.strength,atol=1e-10)
            self.assertGreaterEqual(f.min_cov_eigenvalue.min(),0)
            self.assertTrue(f.strength.dropna().between(0,10).all())

    def test_linear_path_and_shock(self):
        p=pd.Series(np.exp(np.arange(200)*.01));v=pd.Series(1.,index=p.index)
        f=local_trend_frame(p,v)
        self.assertAlmostEqual(f.velocity.iloc[-1],.01,places=5)
        shocked=p.copy();shocked.iloc[-1]*=.8
        g=local_trend_frame(shocked,v)
        self.assertLess(g.velocity.iloc[-1],f.velocity.iloc[-1])
        pd.testing.assert_frame_equal(f.iloc[:-1],g.iloc[:-1])


if __name__=='__main__':unittest.main()
