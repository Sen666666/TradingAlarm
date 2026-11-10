import unittest
from fetch_stock_states import validate
class StateWindowTests(unittest.TestCase):
 def row(self):return dict(date='2024-01-02',code='sz.000001',adjustflag='3',tradestatus='1',isST='0')
 def test_identity_and_date_guards(self):
  validate([self.row()],'000001.SZ',2024)
  for key,value in [('code','sz.000002'),('adjustflag','2'),('date','2023-12-29'),('tradestatus',''),('isST','unknown')]:
   r=self.row();r[key]=value
   with self.assertRaises(ValueError):validate([r],'000001.SZ',2024)
 def test_empty_and_duplicate_windows_rejected(self):
  for rows in [[],[self.row(),self.row()]]:
   with self.assertRaises(ValueError):validate(rows,'000001.SZ',2024)
if __name__=='__main__':unittest.main()
