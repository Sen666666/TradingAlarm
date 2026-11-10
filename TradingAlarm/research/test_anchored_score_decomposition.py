import unittest
import numpy as np
from anchored_score_decomposition import decompose
class Tests(unittest.TestCase):
    def test_exact_and_classes(self):
        for conditional,w,label in [(-1,.5,'nonpositive_direction'),(.5,.5,'direction_below_entry'),(1.5,.5,'neutral_attenuation'),(3,.5,'actual_score_above_entry')]:
            d=decompose(5+5*np.tanh(conditional*(1-w)),w)
            self.assertAlmostEqual(d['conditional_velocity'],conditional);self.assertEqual(d['category'],label)
    def test_invalid(self):
        for score,w in [(10,.5),(5,1),(float('nan'),.1)]:
            with self.assertRaises(ValueError):decompose(score,w)
if __name__=='__main__':unittest.main()
