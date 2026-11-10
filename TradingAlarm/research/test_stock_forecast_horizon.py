import unittest
import pandas as pd
from stock_forecast_horizon import train_sets
class HorizonTrainTests(unittest.TestCase):
 def test_common_training_waits_for_long_label(self):
  d=pd.DataFrame({'date':pd.to_datetime(['2020-01-01','2020-02-01']),'end21':pd.to_datetime(['2020-02-03','2020-03-03']),'end126':pd.to_datetime(['2020-07-01','2020-08-01']),'forward_21':[.1,.2],'forward_126':[.3,.4]})
  short,common=train_sets(d,pd.Timestamp('2020-07-01'));self.assertEqual(len(short),2);self.assertEqual(len(common),0)
  short,common=train_sets(d,pd.Timestamp('2020-07-02'));self.assertEqual(common.index.tolist(),[0])
 def test_both_labels_required_for_matched_rows(self):
  d=pd.DataFrame({'date':pd.to_datetime(['2020-01-01']),'end21':pd.to_datetime(['2020-02-03']),'end126':pd.to_datetime(['2020-07-01']),'forward_21':[float('nan')],'forward_126':[.3]})
  self.assertTrue(train_sets(d,pd.Timestamp('2021-01-01'))[1].empty)
if __name__=='__main__':unittest.main()
