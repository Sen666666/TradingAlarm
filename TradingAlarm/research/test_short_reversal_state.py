import unittest
import pandas as pd
from short_reversal_state import short_reversal_state
class Tests(unittest.TestCase):
 def test_no_reentry_until_original_new_episode(self):
  b=pd.Series([0,1,1,1,1,0,1,1]);f=pd.Series([1,1,-1,2,3,2,2,0])
  self.assertEqual(short_reversal_state(b,f).tolist(),[0,1,0,0,0,0,1,0])
 def test_prefix_and_missing_direction(self):
  b=pd.Series([0,1,1,1,0,1]);f=pd.Series([1,1,float('nan'),-1,2,3]);full=short_reversal_state(b,f)
  self.assertEqual(full.iloc[2],1)
  for i in range(1,len(b)+1):pd.testing.assert_series_equal(short_reversal_state(b.iloc[:i],f.iloc[:i]),full.iloc[:i])
 def test_rejected_initial_direction_cannot_late_enter(self):
  self.assertEqual(short_reversal_state(pd.Series([1,1,0,1]),pd.Series([-1,2,2,2])).tolist(),[0,0,0,1])
if __name__=='__main__':unittest.main()
