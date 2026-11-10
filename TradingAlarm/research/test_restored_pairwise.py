import unittest
import pandas as pd
import numpy as np
from asymmetric_pairwise import asymmetric_exposure,asymmetric_frame
class Tests(unittest.TestCase):
    def test_restore_only_when_both_states_qualify(self):
        s=pd.Series([4.,9.,9.,9.,7.,7.,9.]);f=pd.Series([4.,9.,4.,9.,4.,9.,9.])
        self.assertEqual(asymmetric_exposure(s,f,False).tolist(),[0,1,0,1,0,0,1])
        self.assertEqual(asymmetric_exposure(s,f,True).tolist(),[0,1,0,0,0,0,1])
    def test_missing_preserves_and_prefix(self):
        s=pd.Series([9.,np.nan,9.,9.]);f=pd.Series([9.,np.nan,4.,9.])
        self.assertEqual(asymmetric_exposure(s,f,False).tolist(),[1,1,0,1])
        r=np.random.default_rng(123);c=pd.Series(np.exp(r.normal(0,.03,100).cumsum()));v=pd.Series(r.uniform(1,100,100))
        a=asymmetric_frame(c,v,False)
        pd.testing.assert_frame_equal(a.iloc[:60],asymmetric_frame(c.iloc[:60],v.iloc[:60],False))
        np.testing.assert_allclose(a,asymmetric_frame(c*100,v*10,False),equal_nan=True,atol=1e-12)
if __name__=='__main__':unittest.main()
