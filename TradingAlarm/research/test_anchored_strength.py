import unittest
import numpy as np
import pandas as pd
from anchored_trend_strength import anchored_strength_frame
class Tests(unittest.TestCase):
    def test_prefix_units_and_weights(self):
        rng=np.random.default_rng(912);ix=pd.date_range('2020-01-01',periods=150);p=pd.Series(np.exp(np.cumsum(rng.normal(.002,.02,150))),index=ix);v=pd.Series(rng.uniform(1,10,150),index=ix)
        for neutral in (False,True):
            f=anchored_strength_frame(p,v,neutral)
            pd.testing.assert_frame_equal(f.iloc[:100],anchored_strength_frame(p.iloc[:100],v.iloc[:100],neutral))
            np.testing.assert_allclose(f,anchored_strength_frame(p*100,v*100,neutral),atol=1e-10,equal_nan=True)
            np.testing.assert_allclose(f.dropna().iloc[:,1:].sum(axis=1),1)
            self.assertTrue(f.strength.dropna().between(0,10).all())
    def test_initial_and_exact_update(self):
        ix=pd.date_range('2020-01-01',periods=30);p=pd.Series(np.exp(np.arange(30)*.01),index=ix);v=pd.Series(1.,index=ix)
        f=anchored_strength_frame(p,v,True)
        np.testing.assert_allclose(f.iloc[21,1:],1/3)
        w=np.array([1,1,np.exp(-.5)]);w/=w.sum()
        np.testing.assert_allclose(f.iloc[22,1:],w)
if __name__=='__main__':unittest.main()
