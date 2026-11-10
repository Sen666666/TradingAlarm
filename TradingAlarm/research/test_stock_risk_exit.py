import unittest
import numpy as np
from stock_risk_exit import outcome
class RiskExitTests(unittest.TestCase):
 def test_gap_after_stop_is_not_filled_at_stop_price(self):
  c=np.full(140,100.);c[5]=95;c[6]=80;a=np.ones(140,dtype=bool);t=np.zeros(140,dtype=bool)
  r=outcome(c,a,t,0,'initial2atr',2,99)
  self.assertAlmostEqual(r['return'],-.2);self.assertEqual(r['held_sessions'],6)
  c[7:]=1000;self.assertEqual(r,outcome(c,a,t,0,'initial2atr',2,99))
 def test_trailing_uses_observed_peak_and_next_quote(self):
  c=np.full(140,100.);c[2]=120;c[3]=110;c[4]=109;a=np.ones(140,dtype=bool);t=np.zeros(140,dtype=bool)
  r=outcome(c,a,t,0,'trailing4atr',2,99)
  self.assertEqual(r['held_sessions'],4);self.assertAlmostEqual(r['return'],.09)
  a[4]=False;self.assertEqual(outcome(c,a,t,0,'trailing4atr',2,99)['status'],'exit_missing')
 def test_failed_breakout_uses_frozen_level(self):
  c=np.full(140,100.);c[3]=98;c[4]=97;a=np.ones(140,dtype=bool);t=np.zeros(140,dtype=bool)
  self.assertEqual(outcome(c,a,t,0,'failed_breakout',2,99)['held_sessions'],4)
if __name__=='__main__':unittest.main()
