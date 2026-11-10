import unittest
import pandas as pd
from fundamental_calendar_plan import calendar_requests
class CalendarPlanTests(unittest.TestCase):
 def test_ignores_future_returns_and_order(self):
  d=pd.DataFrame(dict(symbol=['b','a','a'],date=pd.to_datetime(['2016-05-03','2016-05-03','2016-11-01']),active20=[20,20,20],forward_126=[10.,-1.,8.]))
  _,a=calendar_requests(d);d.forward_126=-999;_,b=calendar_requests(d.iloc[::-1]);pd.testing.assert_frame_equal(a,b)
  self.assertEqual(a.iloc[0].symbol,'a');self.assertEqual((a.iloc[0].year,a.iloc[0].quarter),(2016,1));self.assertFalse(a.duplicated(['symbol','year','quarter']).any())
 def test_no_incomplete_activity_or_other_months(self):
  d=pd.DataFrame(dict(symbol=['a','b'],date=pd.to_datetime(['2016-05-03','2016-06-01']),active20=[19,20]));r,p=calendar_requests(d);self.assertTrue(r.empty);self.assertTrue(p.empty)
if __name__=='__main__':unittest.main()
