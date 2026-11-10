import unittest
import numpy as np
import pandas as pd
from trend_strength_model import online_linear_regimes,strength_frame

class LinearStrengthTests(unittest.TestCase):
    def test_posterior_matches_independent_batch_regression(self):
        y=np.linspace(.8,-.4,30);x=np.column_stack([np.ones(30),np.arange(30)/21]);precision=np.eye(2)+x.T@x;cov=np.linalg.inv(precision);beta=cov@x.T@y
        r=online_linear_regimes(y,hazard=1e-30).iloc[-1]
        self.assertAlmostEqual(r.drift,float(x[-1]@beta),places=10)
        self.assertAlmostEqual(r.drift_sd,float(np.sqrt(x[-1]@cov@x[-1])),places=10)
        self.assertAlmostEqual(r.drift_slope,float(beta[1]/21),places=10)
        self.assertLess(r.drift_slope,0)
    def test_jump_and_prefix(self):
        x=np.r_[np.ones(40),-8.];a=online_linear_regimes(x)
        self.assertGreater(a.strength.iloc[-2],9);self.assertLess(a.strength.iloc[-1],3)
        pd.testing.assert_frame_equal(a.iloc[:30],online_linear_regimes(x[:30]))
    def test_scale_and_price_volume_prefix(self):
        rng=np.random.default_rng(8);i=pd.bdate_range('2024-01-01',periods=100);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,100))),index=i);v=pd.Series(np.exp(rng.normal(8,1,100)),index=i)
        a=strength_frame(p,p,v,estimator='linear');b=strength_frame(p*10,p*10,v*100,estimator='linear')
        np.testing.assert_allclose(a,b,rtol=1e-8,atol=1e-8,equal_nan=True)
        pd.testing.assert_frame_equal(a.iloc[:70],strength_frame(p.iloc[:70],p.iloc[:70],v.iloc[:70],estimator='linear'))

if __name__=='__main__':unittest.main()
