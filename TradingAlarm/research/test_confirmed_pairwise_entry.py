import unittest
import numpy as np
import pandas as pd
from confirmed_pairwise_entry import confirmed_exposure,confirmed_frame
class Tests(unittest.TestCase):
    def test_crossing_rejection_exit_and_no_delayed_entry(self):
        s=pd.Series([4.,9.,9.,4.,9.,6.,4.])
        p=pd.Series([-1.,-1.,1.,1.,1.,-1.,-1.])
        self.assertEqual(confirmed_exposure(s,p).tolist(),[0,0,0,0,1,1,0])
    def test_prefix_units_and_sustained_trend(self):
        idx=pd.date_range('2020-01-01',periods=90)
        c=pd.Series(np.exp(np.arange(90)*.01),index=idx);v=pd.Series(100.,index=idx)
        f=confirmed_frame(c,v)
        self.assertEqual(f.target.iloc[-1],1.)
        pd.testing.assert_frame_equal(f.iloc[:55],confirmed_frame(c.iloc[:55],v.iloc[:55]))
        np.testing.assert_allclose(f.strength,confirmed_frame(c*100,v*10).strength,equal_nan=True)
        np.testing.assert_array_equal(f.target,confirmed_frame(c*100,v*10).target)
if __name__=='__main__':unittest.main()
