import unittest
import pandas as pd
import numpy as np
from geometric_strength import strength_exposure
class Tests(unittest.TestCase):
 def test_exact_boundary_missing_and_prefix(self):
  down=5-5*np.tanh(1);up=5+5*np.tanh(1)
  s=pd.Series([np.nan,up,5,2,np.nan,down,8,up])
  self.assertEqual(strength_exposure(s).tolist(),[0,1,0,0,0,0,0,1])
  self.assertEqual(strength_exposure(s,down).tolist(),[0,1,1,1,1,0,0,1])
  pd.testing.assert_series_equal(strength_exposure(s,down).iloc[:5],strength_exposure(s.iloc[:5],down))
if __name__=='__main__':unittest.main()
