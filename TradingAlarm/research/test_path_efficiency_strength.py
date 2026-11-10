import unittest
import numpy as np
import pandas as pd
from path_efficiency_strength import path_efficiency_frame
class Tests(unittest.TestCase):
    def test_causal_units_constantvolume(self):
        rng=np.random.default_rng(55);ix=pd.date_range('2020-01-01',periods=100);p=pd.Series(np.exp(np.cumsum(rng.normal(.001,.02,100))),index=ix);v=pd.Series(1.,index=ix)
        f=path_efficiency_frame(p,v)
        pd.testing.assert_frame_equal(f.iloc[:70],path_efficiency_frame(p.iloc[:70],v.iloc[:70]))
        pd.testing.assert_frame_equal(f,path_efficiency_frame(p,v,True))
        q=path_efficiency_frame(p*100,v*100);q.log_baseline-=np.log(100)
        np.testing.assert_allclose(f,q,atol=1e-10,equal_nan=True)
    def test_known_paths(self):
        ix=pd.date_range('2020-01-01',periods=80);v=pd.Series(1.,index=ix)
        f=path_efficiency_frame(pd.Series(np.exp(np.arange(80)*.01),index=ix),v)
        np.testing.assert_allclose(f.efficiency.dropna(),1);np.testing.assert_allclose(f.alpha.dropna(),4/9)
        flat=path_efficiency_frame(v,v);np.testing.assert_allclose(flat.strength.dropna(),5)
        p=pd.Series(np.exp((np.arange(80)%2)*.01),index=ix);osc=path_efficiency_frame(p,v);np.testing.assert_allclose(osc.efficiency.dropna(),0,atol=1e-12)
if __name__=='__main__':unittest.main()
