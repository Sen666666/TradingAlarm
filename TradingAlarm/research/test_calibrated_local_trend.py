import unittest
import numpy as np
import pandas as pd
from calibrated_local_trend import calibrated_frame


class CalibratedTests(unittest.TestCase):
    def test_prefix_units_and_past_only_selection(self):
        rng=np.random.default_rng(901);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,600))))
        f=calibrated_frame(p);g=calibrated_frame(p*100)
        np.testing.assert_allclose(f,g,atol=1e-9)
        pd.testing.assert_frame_equal(f.iloc[:410],calibrated_frame(p.iloc[:410]))
        shock=p.copy();shock.iloc[410:]*=3;changed=calibrated_frame(shock)
        self.assertEqual(f.selected.iloc[410],changed.selected.iloc[410])
        self.assertTrue(f.selected.iloc[22:274].eq(0).all())
        self.assertTrue(f.strength.dropna().between(0,10).all())


if __name__=='__main__':unittest.main()
