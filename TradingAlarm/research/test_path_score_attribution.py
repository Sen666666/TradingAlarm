import unittest
import numpy as np
import pandas as pd
from path_score_attribution import decompose
class Tests(unittest.TestCase):
    def test_identity(self):
        rng=np.random.default_rng(32);ix=pd.date_range('2020-01-01',periods=100);y=pd.Series(np.cumsum(rng.normal(0,.02,100)),index=ix);b=y.ewm(alpha=.1,adjust=False).mean();f=decompose(np.exp(y),b)
        np.testing.assert_allclose(f.delta_z.dropna(),f[['price_component','baseline_component','normalization_component']].sum(axis=1).loc[f.delta_z.notna()],atol=1e-12)
    def test_stationary_price_cannot_cross_baseline(self):
        for distance in [-1.,-.1,.1,1.]:
            for alpha in [.01,.2,.5]:
                y=0.;b=-distance;new=b+alpha*(y-b)
                self.assertEqual(np.sign(y-new),np.sign(distance))
if __name__=='__main__':unittest.main()
