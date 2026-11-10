import unittest
import numpy as np
import pandas as pd
from trend_opportunity_states import path_states


class PathStateTests(unittest.TestCase):
    def test_causality_scale_and_quadrants(self):
        p=pd.Series(np.exp(np.arange(120)*.01));v=pd.Series(100.,index=p.index)
        f=path_states(p,v)
        self.assertTrue(f.regime.eq('up_up').all());self.assertTrue(f.activity.eq('above_median').all())
        pd.testing.assert_frame_equal(f.iloc[:27],path_states(p.iloc[:90],v.iloc[:90]))
        g=path_states(p*10,v*100)
        np.testing.assert_allclose(f[['r21','r63','relative_volume']],g[['r21','r63','relative_volume']])
        self.assertTrue(path_states(1/p,v).regime.eq('down_down').all())


if __name__=='__main__':unittest.main()
