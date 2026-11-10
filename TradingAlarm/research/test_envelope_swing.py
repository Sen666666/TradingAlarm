import unittest
import numpy as np
import pandas as pd
from swing_structure_strength import swing_frame,envelope_view
class Tests(unittest.TestCase):
    def test_partial_leg_does_not_erase_boundaries(self):
        highs=[10.,12.];lows=[6.,8.]
        for value in [8.1,9.,11.9]:self.assertEqual(envelope_view(highs,lows,value,1),(highs,lows))
        for value in [11.9,10.,8.1]:self.assertEqual(envelope_view(highs,lows,value,-1),(highs,lows))
        self.assertEqual(envelope_view(highs,lows,13.,1),([10.,13.],lows))
        self.assertEqual(highs,[10.,12.])
    def test_causal_and_event_parity(self):
        rng=np.random.default_rng(611);ix=pd.date_range('2020-01-01',periods=250);p=pd.Series(np.exp(np.cumsum(rng.normal(.001,.03,250))),index=ix)
        f,e=swing_frame(p,envelope=True);old,oe=swing_frame(p);self.assertEqual(e,oe)
        g,_=swing_frame(p.iloc[:150],envelope=True);pd.testing.assert_frame_equal(g,f.iloc[:150])
        u,_=swing_frame(p*100,envelope=True);np.testing.assert_allclose(u.strength,f.strength,atol=1e-10,equal_nan=True)
if __name__=='__main__':unittest.main()
