import unittest
import pandas as pd
from first_pullback_audit import first_events,labels
class Tests(unittest.TestCase):
 def test_first_only_and_exclude_unknown_initial_episode(self):
  b=pd.Series([1,1,0,1,1,1,1,0,1,1]);f=pd.Series([-1,1,-1,2,-1,-2,-1,2,-1,-2])
  self.assertEqual(first_events(b,f).tolist(),[False,False,False,False,True,False,False,False,True,False])
 def test_complete_label_horizon_only(self):
  d=pd.date_range('2026-01-01',periods=4);c=pd.Series([10,12,9,11],index=d)
  self.assertIsNone(labels(c,d[2],2));v=labels(c,d[0],3);self.assertAlmostEqual(v['forward_return'],.1);self.assertAlmostEqual(v['forward_mfe'],.2);self.assertAlmostEqual(v['forward_mae'],-.1)
if __name__=='__main__':unittest.main()
