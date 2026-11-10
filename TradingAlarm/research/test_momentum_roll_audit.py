import unittest
import numpy as np
import pandas as pd
from momentum_roll_audit import flips
class Tests(unittest.TestCase):
 def test_roll_only_entry_and_current_only_entry(self):
  # h2: negative oldreturn expires while newdayisflat; sign becomespositive.
  c=pd.Series(np.exp([0,-.2,-.1,-.1]));f=flips(c,2);self.assertEqual(f.iloc[-1]['kind'],'roll_only');self.assertEqual(f.iloc[-1]['side'],'enter')
  c=pd.Series(np.exp([0,0,-.1,.1]));f=flips(c,2);self.assertEqual(f.iloc[-1]['kind'],'new_only')
 def test_prefix_and_price_units(self):
  c=pd.Series(np.exp(np.random.default_rng(9).normal(0,.03,150).cumsum()));a=flips(c,21);b=flips(c.iloc[:90],21);pd.testing.assert_frame_equal(a.loc[:89],b);self.assertEqual(a.kind.tolist(),flips(c*100,21).kind.tolist())
if __name__=='__main__':unittest.main()
