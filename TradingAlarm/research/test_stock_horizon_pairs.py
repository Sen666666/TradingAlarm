import unittest
import pandas as pd
from stock_horizon_pairs import summarize
class PairedTests(unittest.TestCase):
 def test_same_rows_and_missingness_explicit(self):
  d=pd.DataFrame({'date':pd.to_datetime(['2020-01-01']*2+['2020-02-01']),'symbol':['a','b','c'],'forward_10':[.1,100,.2],'forward_21':[.2,None,.3],'forward_63':[.3,.4,.5],'forward_126':[.8,.9,1.]})
  r=summarize(d)
  self.assertEqual(r['paired'],2);self.assertEqual(r['excluded_missing_any'],1)
  self.assertAlmostEqual(r['mean_10'],.15);self.assertEqual(r['tail_unique_symbols'],2)
  self.assertAlmostEqual(r['long_minus_10'],.75)
if __name__=='__main__':unittest.main()
