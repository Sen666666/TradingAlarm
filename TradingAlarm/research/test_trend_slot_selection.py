import unittest
import pandas as pd
from trend_slot_selection import TrendSlots
class Tests(unittest.TestCase):
 def setUp(self):
  self.d=pd.Timestamp('2024-01-01');self.strength={s:pd.Series([v,100-v],index=[self.d,self.d+pd.Timedelta(days=1)]) for s,v in [('a',9),('b',8),('c',7)]}
 def test_no_future_rank_and_pending_reserves(self):
  pick=TrendSlots(self.strength,slots=1);scores=dict.fromkeys(self.strength,1.);qty=dict.fromkeys(scores,0.)
  self.assertEqual(pick(self.d,scores,qty,{}),{'a':1.,'b':0.,'c':0.})
  self.assertEqual(pick(self.d,scores,qty,{'b':{'target':100}}),{'a':0.,'b':1.,'c':0.})
 def test_exit_holding_reserves_until_sold(self):
  pick=TrendSlots(self.strength,slots=1);self.assertEqual(pick(self.d,{'a':0.,'b':1.,'c':1.},{'a':100.,'b':0.,'c':0.},{}),dict.fromkeys(self.strength,0.))
 def test_group_cap_and_gate_only_on_entry(self):
  groups={(self.d,s):('x' if s!='c' else 'y') for s in self.strength};pick=TrendSlots(self.strength,groups=groups,gates={(self.d,'x'):True,(self.d,'y'):True},slots=3,group_slots=1)
  self.assertEqual(pick(self.d,dict.fromkeys(self.strength,1.),dict.fromkeys(self.strength,0.),{}),{'a':1.,'b':0.,'c':1.})
  pick.gates={};self.assertEqual(pick(self.d,dict.fromkeys(self.strength,1.),{'a':100.,'b':0.,'c':0.},{}),{'a':1.,'b':0.,'c':0.})
if __name__=='__main__':unittest.main()
