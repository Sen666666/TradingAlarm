import unittest
import pandas as pd
from sector_admission_outcomes import label
class Labels(unittest.TestCase):
 def test_future_only_and_horizon(self):
  c=pd.Series([100.,130.,90.,140.],index=pd.date_range('2024-01-01',periods=4));r=label(c,c.index[0],2)
  self.assertAlmostEqual(r['forward_return'],-.1);self.assertAlmostEqual(r['mfe'],.3);self.assertAlmostEqual(r['mae'],-.1)
 def test_missing_or_immature(self):
  c=pd.Series([1.,2.],index=pd.date_range('2024-01-01',periods=2));self.assertIsNone(label(c,c.index[-1],1));self.assertIsNone(label(c,pd.Timestamp('2023-01-01'),1))
if __name__=='__main__':unittest.main()
