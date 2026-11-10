import unittest
import numpy as np
import pandas as pd
from segmented_trend_strength import segment_fit,segmented_frame
class Tests(unittest.TestCase):
    def test_line_and_reversal(self):
        x=np.arange(21);f=segment_fit(.01*x);self.assertEqual(f['knot'],-1);self.assertAlmostEqual(f['velocity'],.01)
        f=segment_fit(.01*x-.04*np.maximum(x-12,0));self.assertEqual(f['knot'],12);self.assertAlmostEqual(f['velocity'],-.03)
    def test_prefix_units_flat(self):
        rng=np.random.default_rng(1);c=pd.Series(np.exp(rng.normal(0,.03,80).cumsum()));v=pd.Series(rng.uniform(1,100,80))
        a=segmented_frame(c,v);pd.testing.assert_frame_equal(a.iloc[:55],segmented_frame(c.iloc[:55],v.iloc[:55]))
        np.testing.assert_allclose(a,segmented_frame(c*100,v*10),atol=1e-11,equal_nan=True)
        self.assertTrue(segmented_frame(v*0+1,v).strength.dropna().eq(5).all())
if __name__=='__main__':unittest.main()
