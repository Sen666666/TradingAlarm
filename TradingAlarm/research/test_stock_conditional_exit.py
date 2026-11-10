import unittest
import numpy as np
from stock_conditional_exit import outcome
class ExitTests(unittest.TestCase):
 def test_decision_executes_later(self):
  c=np.arange(140.)+100;a=np.ones(140,dtype=bool);t=np.zeros(140,dtype=bool)
  r=outcome(c,a,t,0,'cap10');self.assertAlmostEqual(r['return'],.11);self.assertEqual(r['held_sessions'],11)
  c[12:]=1;self.assertEqual(r,outcome(c,a,t,0,'cap10'))
 def test_weak_exit_and_missing_quote(self):
  c=np.full(140,100.);a=np.ones(140,dtype=bool);t=np.zeros(140,dtype=bool)
  self.assertEqual(outcome(c,a,t,0,'weak10')['held_sessions'],11)
  a[11]=False;self.assertEqual(outcome(c,a,t,0,'weak10')['status'],'exit_missing')
 def test_profitable_position_extends_until_trend(self):
  c=np.arange(140.)+100;a=np.ones(140,dtype=bool);t=np.zeros(140,dtype=bool);t[30]=True
  self.assertEqual(outcome(c,a,t,0,'weak10')['held_sessions'],31)
if __name__=='__main__':unittest.main()
