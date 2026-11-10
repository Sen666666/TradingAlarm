import unittest
import numpy as np
import pandas as pd
from stock_rank_placebo import shuffled_targets
class PlaceboTests(unittest.TestCase):
 def test_date_distribution_missingness_and_reproducibility(self):
  d=pd.DataFrame({'date':pd.to_datetime(['2020-01-01']*4+['2020-02-01']*3),'forward_21':[1.,2.,3.,np.nan,4.,5.,6.]})
  y=shuffled_targets(d,n=5);np.testing.assert_array_equal(y,shuffled_targets(d,n=5))
  self.assertTrue(np.isnan(y[3]).all())
  for j in range(6):
   np.testing.assert_array_equal(np.sort(y[:3,j]),[-1,0,1]);np.testing.assert_array_equal(np.sort(y[4:,j]),[-1,0,1])
 def test_later_labels_do_not_change_earlier_permutations(self):
  d=pd.DataFrame({'date':pd.to_datetime(['2020-01-01']*3+['2020-02-01']*3),'forward_21':range(6)})
  before=shuffled_targets(d,n=5);d.loc[3:,'forward_21']=100
  np.testing.assert_array_equal(before[:3],shuffled_targets(d,n=5)[:3])
if __name__=='__main__':unittest.main()
