import unittest
import pandas as pd
from stock_shadow_market_gate import gated_schedule
class GateTests(unittest.TestCase):
 def test_lag_retry_and_latest_selection(self):
  i=pd.bdate_range('2020-01-01',periods=6);b=pd.Series([.4,.6,.4,.4,.7,.7],index=i)
  s,g=gated_schedule(i[1:],{i[1]:['a'],i[4]:['b']},b)
  self.assertEqual(s[i[1]],[]);self.assertEqual(s[i[2]],['a']);self.assertEqual(s[i[3]],[]);self.assertEqual(s[i[4]],[]);self.assertEqual(s[i[5]],['b'])
  b.iloc[-1]=.1;self.assertEqual(s,gated_schedule(i[1:],{i[1]:['a'],i[4]:['b']},b)[0])
 def test_unknown_state_rejected(self):
  i=pd.bdate_range('2020-01-01',periods=3);b=pd.Series([.4,None,.8],index=i)
  with self.assertRaises(ValueError):gated_schedule(i[1:],{},b)
if __name__=='__main__':unittest.main()
