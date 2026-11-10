import unittest
import pandas as pd
import numpy as np
from swing_structure_strength import swing_frame
class Tests(unittest.TestCase):
    def test_prefix_units_and_confirmations(self):
        rng=np.random.default_rng(62);ix=pd.date_range('2020-01-01',periods=250);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.03,250))),index=ix);f,e=swing_frame(p);g,ge=swing_frame(p.iloc[:150]);pd.testing.assert_frame_equal(f.iloc[:150],g)
        self.assertEqual([x for x in e if x['confirmation_date']<=str(ix[149].date())],ge)
        q,qe=swing_frame(p*100);np.testing.assert_allclose(f.strength,q.strength,equal_nan=True,atol=1e-10)
        self.assertTrue(all(x['pivot_date']<x['confirmation_date'] for x in e));self.assertTrue(f.strength.dropna().between(0,10).all())
    def test_uninterrupted_trend_is_not_falsely_confirmed(self):
        p=pd.Series(np.exp(np.arange(100)*.01),index=pd.date_range('2020-01-01',periods=100))
        f,e=swing_frame(p)
        self.assertEqual(len(e),1)
        self.assertEqual(e[0]['kind'],'low')
        np.testing.assert_allclose(f.strength.dropna(),5)
if __name__=='__main__':unittest.main()
