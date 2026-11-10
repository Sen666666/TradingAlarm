import unittest
import numpy as np
import pandas as pd
from cumulative_trend_strength import accumulate,cumulative_frame,MU,CAP


class CumulativeTests(unittest.TestCase):
    def test_recursion_symmetry_and_cap(self):
        x=np.r_[np.ones(50),-np.ones(10)]
        f=accumulate(x);g=accumulate(-x)
        self.assertAlmostEqual(f.up_evidence.iloc[0],MU-.5*MU**2)
        self.assertEqual(f.up_evidence.iloc[49],CAP)
        np.testing.assert_allclose(f.strength+g.strength,10)
        self.assertLess(f.strength.iloc[-1],5)
        pd.testing.assert_frame_equal(f.iloc[:40],accumulate(x[:40]))

    def test_units_and_prefix(self):
        rng=np.random.default_rng(205);p=pd.Series(np.exp(np.cumsum(rng.normal(.001,.02,200))));v=pd.Series(rng.lognormal(8,1,200))
        f=cumulative_frame(p,v,True);g=cumulative_frame(p*100,v*1000,True)
        np.testing.assert_allclose(f,g,atol=1e-10)
        pd.testing.assert_frame_equal(f.iloc[:150],cumulative_frame(p.iloc[:150],v.iloc[:150],True))


if __name__=='__main__':unittest.main()
