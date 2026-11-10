import unittest
import pandas as pd
import numpy as np
from trend_entry_horizon_attribution import decompose
class AttributionTests(unittest.TestCase):
 def test_signal_alignment_and_reentry(self):
  c=pd.Series([100.,110.,99.,118.8]);e=pd.Series([1.,0.,1.,0.])
  r=decompose(c,e,0,3)
  self.assertAlmostEqual(r['signal_return'],.32)
  self.assertAlmostEqual(r['hold_return'],.188)
  self.assertAlmostEqual(r['flat_log'],np.log(.9))
 def test_flat_and_full(self):
  c=pd.Series([100.,80.,120.])
  self.assertAlmostEqual(decompose(c,pd.Series([0.,0.,0.]),0,2)['signal_return'],0)
  self.assertAlmostEqual(decompose(c,pd.Series([1.,1.,1.]),0,2)['signal_return'],.2)
if __name__=='__main__':unittest.main()
