import unittest
import pandas as pd
from trend_slot_priority_control import priority
class Tests(unittest.TestCase):
 def test_reproducible_independent_of_iteration_and_future(self):
  dates=pd.bdate_range('2024-01-01',periods=5)
  a={(s,d):priority(17300,s,d) for s in ['a','b'] for d in dates}
  b={(s,d):priority(17300,s,d) for d in reversed(dates[:3]) for s in ['b','a']}
  for k,v in b.items():self.assertEqual(v,a[k]);self.assertTrue(0<=v<1)
  self.assertNotEqual(priority(17300,'a',dates[0]),priority(17301,'a',dates[0]))
if __name__=='__main__':unittest.main()
