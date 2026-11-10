import unittest
import pandas as pd
from short_half_state import short_half_state
class Tests(unittest.TestCase):
 def test_recovery_and_missing_and_reset(self):
  b=pd.Series([0,1,1,1,1,1,0,1]);f=pd.Series([0,-1,-1,2,float('nan'),0,2,-1]);v=short_half_state(b,f,restore=True)
  self.assertEqual(v.tolist(),[0,1,.5,1,1,.5,0,1])
  for n in range(1,len(b)+1):pd.testing.assert_series_equal(short_half_state(b.iloc[:n],f.iloc[:n],restore=True),v.iloc[:n])
if __name__=='__main__':unittest.main()
