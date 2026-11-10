import unittest
import numpy as np
import pandas as pd
from geometric_strength import fit_endpoint,geometric_frame
class Tests(unittest.TestCase):
    def test_quadratic(self):
        t=np.arange(-20,1);y=4+.003*t+.5*.0002*t*t
        for v in (None,np.linspace(1,5,21)):
            np.testing.assert_allclose(fit_endpoint(y,v),[.003,.0002],atol=1e-14)
    def test_units_and_prefix(self):
        rng=np.random.default_rng(42);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,100))));v=pd.Series(np.exp(rng.normal(5,1,100)))
        f=geometric_frame(p,p,v)
        pd.testing.assert_frame_equal(f.iloc[:70],geometric_frame(p[:70],p[:70],v[:70]))
        np.testing.assert_allclose(f,geometric_frame(p*13,p*13,v*7),atol=1e-11,equal_nan=True)
    def test_direction_and_flat(self):
        p=pd.Series(np.exp(np.arange(60)*.01));v=p*0+1
        up=geometric_frame(p,p,v).strength
        down=geometric_frame(1/p,1/p,v).strength
        self.assertTrue(up.iloc[:21].isna().all())
        np.testing.assert_allclose((up+down).iloc[21:],10)
        self.assertGreater(up.iloc[-1],9)
        self.assertEqual(geometric_frame(v,v,v).strength.iloc[-1],5)
    def test_reversal_not_repainted(self):
        p=pd.Series(np.exp(np.r_[np.arange(60)*.01,.59-.25]));v=p*0+1
        s=geometric_frame(p,p,v).strength
        self.assertGreater(s.iloc[-2],9)
        self.assertLess(s.iloc[-1],5)
if __name__=='__main__':unittest.main()
