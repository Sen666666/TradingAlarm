import unittest
import numpy as np
import pandas as pd
from trend_capture_audit import decompose
class Tests(unittest.TestCase):
 def test_exact_wealth_identity_and_flat_days(self):
  a=pd.Series([.2,-.1,.03]);b=pd.Series([.1,-.2,0.]);rows,error=decompose(a,b)
  self.assertLess(error,1e-12);self.assertAlmostEqual(sum(x['relative_log_contribution'] for x in rows),np.log((1+a).prod()/(1+b).prod()))
  self.assertEqual(rows[-1]['days'],1);self.assertIsNone(rows[-1]['participation'])
  with self.assertRaises(ValueError):decompose(a,b.set_axis([1,2,3]))
if __name__=='__main__':unittest.main()
