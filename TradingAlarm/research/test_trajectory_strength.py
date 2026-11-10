import unittest
import numpy as np
import pandas as pd
from trajectory_strength import features,path_target,fit,predict

class Tests(unittest.TestCase):
    def test_prefix_and_units(self):
        rng=np.random.default_rng(4);c=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,150))));v=pd.Series(np.exp(rng.normal(10,1,150)))
        f=features(c,c,v)
        pd.testing.assert_frame_equal(f.iloc[:100],features(c[:100],c[:100],v[:100]))
        np.testing.assert_allclose(f,features(c*100,c*100,v*1000),atol=1e-10,equal_nan=True)
    def test_target(self):
        c=pd.Series(np.exp(np.arange(60)*.01));t=path_target(c)
        np.testing.assert_allclose(t.iloc[:-21],1)
        self.assertTrue(t.iloc[-21:].isna().all())
        np.testing.assert_allclose(path_target(c*0+1).iloc[:-21],0)
        np.testing.assert_allclose(path_target(1/c).iloc[:-21],-1)
    def test_ridge_normal_equations(self):
        rng=np.random.default_rng(8);x=rng.normal(size=(80,4));y=rng.normal(size=80);w=np.arange(1,81,dtype=float);w/=w.sum()
        m=fit(x,y,w);z=(x-m['mean'])/m['scale'];b=np.asarray(m['coef'])
        np.testing.assert_allclose(z.T@(w*(predict(m,x)-y))+.1*b,0,atol=1e-12)
        self.assertAlmostEqual(float(w@(predict(m,x)-y)),0)
if __name__=='__main__':unittest.main()
