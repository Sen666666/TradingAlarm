import unittest
import numpy as np
from trend_entry_impulse_audit import snapshot
class Tests(unittest.TestCase):
    def test_attribution_and_price_volume_unit_invariance(self):
        y=np.r_[np.zeros(19),.05,.1];c=np.exp(y);v=np.ones(21);w=[.5,.5]
        a=snapshot(c,v,w);b=snapshot(c*1000,v*100,w)
        self.assertAlmostEqual(a['last2_velocity_fraction'],1.)
        for k in a:self.assertAlmostEqual(a[k],b[k],places=9)
        flat=snapshot(np.ones(21),v,w);self.assertEqual(flat['velocity'],0);self.assertIsNone(flat['last2_velocity_fraction'])
if __name__=='__main__':unittest.main()
