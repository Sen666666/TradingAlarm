import unittest
import pandas as pd
import numpy as np
from asymmetric_pairwise import asymmetric_exposure,asymmetric_frame
from geometric_strength import strength_exposure
class Tests(unittest.TestCase):
    def test_fast_exit_no_reentry_until_recross(self):
        slow=pd.Series([4.,9.,9.,9.,4.,9.,9.]);fast=pd.Series([4.,9.,4.,9.,6.,9.,4.])
        self.assertEqual(asymmetric_exposure(slow,fast).tolist(),[0,1,0,0,0,1,0])
    def test_identical_scores_match_original(self):
        s=pd.Series([np.nan,4.,9.,7.,4.,9.,2.])
        pd.testing.assert_series_equal(asymmetric_exposure(s,s),strength_exposure(s))
    def test_negative_fast_blocks_entry(self):
        s=pd.Series([4.,9.,9.]);f=pd.Series([6.,4.,9.])
        self.assertEqual(asymmetric_exposure(s,f).tolist(),[0,0,0])
    def test_prefix_and_units(self):
        r=np.random.default_rng(3);c=pd.Series(np.exp(r.normal(0,.03,100).cumsum()));v=pd.Series(r.uniform(1,100,100))
        a=asymmetric_frame(c,v)
        pd.testing.assert_frame_equal(a.iloc[:60],asymmetric_frame(c.iloc[:60],v.iloc[:60]))
        np.testing.assert_allclose(a,asymmetric_frame(c*100,v*10),atol=1e-12,equal_nan=True)
if __name__=='__main__':unittest.main()
