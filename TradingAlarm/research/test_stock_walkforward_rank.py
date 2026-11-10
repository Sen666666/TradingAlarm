import unittest
import numpy as np
import pandas as pd
from stock_walkforward_rank import FEATURES,fit,training_rows
class WalkTests(unittest.TestCase):
 def sample(self):
  d=pd.DataFrame({'date':pd.to_datetime(['2020-01-01']*5+['2020-02-01']*5),'label_end':pd.to_datetime(['2020-02-03']*5+['2020-03-03']*5),'forward_21':np.arange(10.)/100})
  for i,c in enumerate(FEATURES):d[c]=np.linspace(-.5,.5,10)*(i+1)/5
  return d
 def test_label_must_be_strictly_mature(self):
  d=self.sample();self.assertEqual(len(training_rows(d,pd.Timestamp('2020-02-03'))),0)
  self.assertEqual(len(training_rows(d,pd.Timestamp('2020-02-04'))),5)
 def test_future_labels_cannot_change_coefficients(self):
  d=self.sample();dt=pd.Timestamp('2020-02-04');a=fit(training_rows(d,dt));d.loc[5:,'forward_21']=100
  np.testing.assert_array_equal(a,fit(training_rows(d,dt)))
if __name__=='__main__':unittest.main()
