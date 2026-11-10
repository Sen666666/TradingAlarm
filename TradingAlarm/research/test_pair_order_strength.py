import unittest
import numpy as np
import pandas as pd
from pair_order_strength import order_balance,order_frame
class Tests(unittest.TestCase):
    def test_order_extremes_and_invariance(self):
        x=np.arange(1.,22.);v=np.arange(1.,22.)
        self.assertEqual(order_balance(x,v),1.)
        self.assertEqual(order_balance(-x,v),-1.)
        self.assertEqual(order_balance(np.ones(21),v),0.)
        y=np.random.default_rng(1).uniform(1,10,21)
        self.assertAlmostEqual(order_balance(y,v),order_balance(y**3,v*100))
    def test_prefix_missing_and_bound(self):
        rng=np.random.default_rng(2);c=pd.Series(np.exp(rng.normal(0,.03,100).cumsum()));v=pd.Series(rng.uniform(1,100,100));v.iloc[30]=0
        a=order_frame(c,v);b=order_frame(c.iloc[:60],v.iloc[:60])
        pd.testing.assert_frame_equal(a.iloc[:60],b)
        self.assertTrue(np.isnan(a.strength.iloc[30]))
        self.assertTrue(a.balance.dropna().between(-1,1).all())
if __name__=='__main__':unittest.main()
