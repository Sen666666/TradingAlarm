import unittest
import numpy as np
import pandas as pd
from geometric_strength import fit_endpoint,geometric_frame
from geometric_exit_audit import linear_velocity
class Tests(unittest.TestCase):
    def test_independent_slope(self):
        rng=np.random.default_rng(45);y=np.cumsum(rng.normal(size=21));v=np.exp(rng.normal(size=21))
        slope,accel=fit_endpoint(y,v,degree=1)
        self.assertAlmostEqual(slope,linear_velocity(y,v));self.assertEqual(accel,0)
    def test_prefix(self):
        rng=np.random.default_rng(9);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.01,100))));v=pd.Series(np.exp(rng.normal(size=100)))
        f=geometric_frame(p,p,v,degree=1)
        pd.testing.assert_frame_equal(f[:70],geometric_frame(p[:70],p[:70],v[:70],degree=1))
        np.testing.assert_allclose(f,geometric_frame(p*10,p*10,v*5,degree=1),atol=1e-11,equal_nan=True)
if __name__=='__main__':unittest.main()
