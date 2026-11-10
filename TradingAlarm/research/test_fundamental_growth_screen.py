import unittest
import pandas as pd
from fundamental_growth_screen import select_pair
class GrowthScreenTests(unittest.TestCase):
 def data(self):
  c=pd.DataFrame(dict(symbol=['a','b','c'],date=pd.to_datetime(['2020-05-04']*3),atr_fraction=[.02,.01,.03],turnover60=[1.,2.,3.],forward_21=[99.,-1.,5.]))
  f=pd.DataFrame(dict(symbol=['a','b','c'],date=c.date,ytd_attributable_growth_vendor=['.2','-.1','0'],latest_vendor_pubDate=['2020-04-30']*3,requested_windows_complete=True))
  return c,f
 def test_current_data_only_and_no_refill(self):
  c,f=self.data();a=select_pair(c,f);self.assertEqual(a['base'].symbol.tolist(),['b','a','c']);self.assertEqual(a['positive_ytd_growth'].symbol.tolist(),['a'])
  c.forward_21=-999;b=select_pair(c,f)
  for k in a:pd.testing.assert_frame_equal(a[k],b[k])
 def test_missing_not_zero_and_publication_boundary(self):
  c,f=self.data()
  with self.assertRaises(ValueError):select_pair(c,f.iloc[:2])
  f.loc[0,'latest_vendor_pubDate']='2020-05-04'
  with self.assertRaises(ValueError):select_pair(c,f)
if __name__=='__main__':unittest.main()
