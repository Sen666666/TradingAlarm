import unittest
import numpy as np
import pandas as pd
from trend_strength_model import online_regimes,strength_frame

class StrengthTests(unittest.TestCase):
    def test_can_jump_on_abrupt_reversal(self):
        r=online_regimes(np.r_[np.ones(40),-8.])
        self.assertGreater(r.strength.iloc[-2],9)
        self.assertLess(r.strength.iloc[-1],3)
    def test_flat_is_neutral(self):
        r=online_regimes(np.zeros((50,2)))
        np.testing.assert_allclose(r.strength,5.)
    def test_volume_shock_changes_regime_not_direction_by_itself(self):
        x=np.zeros((40,2));x[-1,1]=20.
        r=online_regimes(x)
        np.testing.assert_allclose(r.strength,5.)
        self.assertGreater(r.reset_probability.iloc[-1],.9)
    def test_price_volume_scale_and_future_independence(self):
        rng=np.random.default_rng(7);idx=pd.bdate_range('2024-01-01',periods=100);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,100))),index=idx);v=pd.Series(np.exp(rng.normal(8,1,100)),index=idx)
        a=strength_frame(p,p,v);b=strength_frame(p*10,p*10,v*100)
        np.testing.assert_allclose(a,b,rtol=1e-9,atol=1e-9,equal_nan=True)
        pd.testing.assert_frame_equal(a.iloc[:70],strength_frame(p.iloc[:70],p.iloc[:70],v.iloc[:70]))

if __name__=='__main__':unittest.main()
