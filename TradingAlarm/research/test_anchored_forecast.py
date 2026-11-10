import unittest
import numpy as np
import pandas as pd
from anchored_forecast_diagnostic import anchored_frame
class Tests(unittest.TestCase):
    def test_prefix_units(self):
        rng=np.random.default_rng(129);ix=pd.date_range('2020-01-01',periods=100);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,100))),index=ix);v=pd.Series(rng.uniform(1,20,100),index=ix)
        f=anchored_frame(p,v)
        pd.testing.assert_frame_equal(f.iloc[:75],anchored_frame(p.iloc[:75],v.iloc[:75]))
        np.testing.assert_allclose(f,anchored_frame(p*100,v*100),atol=1e-10,equal_nan=True)
    def test_exact_trends_and_jump(self):
        ix=pd.date_range('2020-01-01',periods=80);x=np.arange(80);v=pd.Series(1.,index=ix);p=pd.Series(np.exp(.01*x),index=ix)
        np.testing.assert_allclose(anchored_frame(p,v).dropna(),0,atol=1e-10)
        q=p.copy();q.iloc[-1]*=np.exp(-.1)
        np.testing.assert_allclose(anchored_frame(q,v).iloc[-1],-10,atol=1e-10)
        curved=pd.Series(np.exp(.0001*x*x),index=ix)
        np.testing.assert_allclose(anchored_frame(curved,v).anchored_quadratic_z.dropna(),0,atol=1e-10)
if __name__=='__main__':unittest.main()
