import unittest
import numpy as np
import pandas as pd
from strategy_signals import slope_geometry,geometry_signal


class GeometryTests(unittest.TestCase):
    def test_flat_and_perfect_log_trend(self):
        self.assertEqual(slope_geometry(pd.Series(np.ones(40)*100)).iloc[-1],0.)
        self.assertGreater(slope_geometry(pd.Series(100*np.exp(np.arange(40)*.01))).iloc[-1],2.)
        self.assertLess(slope_geometry(pd.Series(100*np.exp(-np.arange(40)*.01))).iloc[-1],-2.)
        self.assertTrue(geometry_signal(pd.Series(np.ones(40)*100),0).eq(0).all())

    def test_matches_direct_least_squares(self):
        x=np.arange(21,dtype=float);y=.01*x+.04*np.sin(x)
        price=pd.Series(100*np.exp(y));design=np.column_stack([np.ones(21),x])
        coef=np.linalg.lstsq(design,y,rcond=None)[0];res=y-design@coef
        se=np.sqrt((res@res)/19*np.linalg.inv(design.T@design)[1,1])
        self.assertAlmostEqual(slope_geometry(price).iloc[-1],coef[1]/se,places=10)

    def test_scale_invariance_and_no_future_leak(self):
        x=np.arange(130);p=pd.Series(100*np.exp(.002*x+.04*np.sin(x/6)))
        np.testing.assert_allclose(slope_geometry(p),slope_geometry(p*10000),rtol=1e-10,atol=1e-10,equal_nan=True)
        for exit_score in (0,-2):
            before=geometry_signal(p,exit_score);future=p.copy();future.iloc[90:]*=.1
            pd.testing.assert_series_equal(before.iloc[:90],geometry_signal(future,exit_score).iloc[:90])
            self.assertTrue(before.iloc[:20].eq(0).all())

if __name__=='__main__':unittest.main()
