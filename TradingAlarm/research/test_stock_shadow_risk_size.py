import unittest
import numpy as np
import pandas as pd
from stock_shadow_risk_size import risk_weights
from stock_shadow_portfolio import simulate
class RiskSizeTests(unittest.TestCase):
 def test_formula_cap_and_unknown(self):
  w=risk_weights(pd.DataFrame({'a':[.01,.025,.05,0,np.nan]})).a
  np.testing.assert_allclose(w,[.1,.05,.025,0,0])
 def test_explicit_equal_weights_preserve_baseline(self):
  dates=pd.bdate_range('2020-01-01',periods=300);p=pd.DataFrame({'a':100.},index=dates);a=p.notna();s={dates[0]:['a'],dates[30]:[]}
  m,path=simulate(p,a,s,20);n,q=simulate(p,a,s,20,target_weights=p*.001)
  self.assertEqual(m,n);pd.testing.assert_frame_equal(path,q)
 def test_levered_targets_rejected(self):
  dates=pd.bdate_range('2020-01-01',periods=300);p=pd.DataFrame({'a':100.,'b':100.},index=dates)
  with self.assertRaises(ValueError):simulate(p,p.notna(),{dates[0]:['a','b']},20,target_weights=p*.006)
if __name__=='__main__':unittest.main()
