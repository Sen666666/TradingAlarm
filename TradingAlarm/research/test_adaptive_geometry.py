import unittest
import numpy as np
import pandas as pd
from adaptive_geometric_strength import fit_experts,update_weights,adaptive_frame
from geometric_strength import fit_endpoint
class Tests(unittest.TestCase):
    def test_exact_likelihood(self):
        result=update_weights([.5,.5],[0,2],1)
        np.testing.assert_allclose(result,[1/(1+np.exp(-2)),1/(1+np.exp(2))])
        np.testing.assert_allclose(update_weights([1,0],[0,0],1),[1-1/42,1/42])
        self.assertTrue(np.isfinite(update_weights([1,0],[100,-200],0)).all())
    def test_expert_fits(self):
        t=np.arange(-20,1);y=3+.01*t+.5*.002*t*t
        v,p=fit_experts(y)
        self.assertAlmostEqual(p[1],3+.01+.001)
        self.assertAlmostEqual(v[1],.01)
        self.assertAlmostEqual(v[0],fit_endpoint(y,degree=1)[0])
    def test_prefix_units_and_weights(self):
        rng=np.random.default_rng(11);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,120))));v=pd.Series(np.exp(rng.normal(5,1,120)))
        f=adaptive_frame(p,p,v)
        pd.testing.assert_frame_equal(f[:90],adaptive_frame(p[:90],p[:90],v[:90]))
        np.testing.assert_allclose(f,adaptive_frame(p*100,p*100,v*7),atol=1e-10,equal_nan=True)
        np.testing.assert_allclose(f[['linear_weight','quadratic_weight']].dropna().sum(axis=1),1)
        valid=f.dropna();self.assertTrue((valid.velocity>=valid[['linear_velocity','quadratic_velocity']].min(axis=1)-1e-12).all())
        self.assertTrue((valid.velocity<=valid[['linear_velocity','quadratic_velocity']].max(axis=1)+1e-12).all())
if __name__=='__main__':unittest.main()
