import unittest
import pandas as pd
from short_half_state import short_half_state
class Tests(unittest.TestCase):
 def test_entry_preserved_and_no_readd(self):
  b=pd.Series([0,1,1,1,1,0,1,1]);f=pd.Series([0,-1,1,-1,2,2,-1,0])
  self.assertEqual(short_half_state(b,f).tolist(),[0,1,1,.5,.5,0,1,.5])
 def test_prefix_and_missing(self):
  b=pd.Series([0,1,1,1,1,0]);f=pd.Series([0,1,float('nan'),0,float('nan'),1]);full=short_half_state(b,f)
  self.assertEqual(full.tolist(),[0,1,1,.5,.5,0])
  for i in range(1,len(b)+1):pd.testing.assert_series_equal(short_half_state(b.iloc[:i],f.iloc[:i]),full.iloc[:i])
if __name__=='__main__':unittest.main()
