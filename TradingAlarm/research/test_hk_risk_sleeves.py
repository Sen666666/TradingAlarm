import unittest
import numpy as np
import pandas as pd
from hk_risk_sleeves import targets
class SleeveTests(unittest.TestCase):
 def sample(self):
  idx=pd.bdate_range('2021-01-01',periods=500);p=np.arange(500.)+100
  return pd.DataFrame({'open':p,'close':p,'high':p+.5,'low':p-.5},index=idx)
 def test_reset_bounded_and_future_independent(self):
  f=self.sample();p=targets(f,True,True)
  self.assertTrue(p.loc[:'2021-12-30'].eq(0).all());self.assertTrue(p.between(0,1).all())
  f.iloc[400:]*=.5;pd.testing.assert_series_equal(p.iloc[:400],targets(f,True,True).iloc[:400])
 def test_initial_fraction_frozen_while_held(self):
  p=targets(self.sample(),True,False);v=p[p.gt(0)]
  self.assertGreater(len(v),100);self.assertEqual(v.nunique(),1)
if __name__=='__main__':unittest.main()
