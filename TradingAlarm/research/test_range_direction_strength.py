import unittest
import numpy as np
import pandas as pd
from range_direction_strength import range_frame


class RangeTests(unittest.TestCase):
    def test_prefix_units_and_direction(self):
        p=pd.Series(np.exp(np.arange(150)*.01));f=pd.DataFrame(dict(high=p*1.01,low=p*.99,close=p));v=pd.Series(100.,index=p.index)
        for joint in [False,True]:
            x=range_frame(f,v,joint);y=range_frame(f*100,v*10,joint)
            np.testing.assert_allclose(x,y,atol=1e-12)
            pd.testing.assert_frame_equal(x.iloc[:100],range_frame(f.iloc[:100],v.iloc[:100],joint))
            self.assertTrue(x.balance.dropna().eq(1).all())

    def test_flat_and_tied_expansion(self):
        f=pd.DataFrame(dict(high=[101.]*80,low=[99.]*80,close=[100.]*80));v=pd.Series(100.,index=f.index)
        f.loc[79,['high','low']]=[102.,98.]
        x=range_frame(f,v)
        self.assertEqual(x.strength.iloc[-1],5)
        self.assertEqual(x.positive.iloc[-1],0)
        self.assertEqual(x.negative.iloc[-1],0)

    def test_close_control_ignores_range_and_preserves_prefix(self):
        p=pd.Series(np.exp(np.arange(100)*.01));v=pd.Series(100.,index=p.index)
        f=pd.DataFrame(dict(high=p*1.01,low=p*.99,close=p));g=f.copy();g.high*=2;g.low/=2
        x=range_frame(f,v,True,True)
        pd.testing.assert_frame_equal(x,range_frame(g,v,True,True))
        pd.testing.assert_frame_equal(x.iloc[:80],range_frame(f.iloc[:80],v.iloc[:80],True,True))
        self.assertTrue(x.balance.dropna().eq(1).all())


if __name__=='__main__':unittest.main()
