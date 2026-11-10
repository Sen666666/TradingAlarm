import unittest
import numpy as np,pandas as pd
from policies import project,trigger
from engine import backtest,SCENARIOS

def raw(grades):
 ds=pd.date_range('2020-01-01',periods=len(grades));return pd.DataFrame(dict(level=np.array(grades)-1,ready=np.array(grades)>0,structure=np.array(grades)>=4,structure_id=[1 if x>=4 else None for x in grades],floor=[9. if x>=4 else np.nan for x in grades],structural_invalidated=0),index=ds)
class Rules(unittest.TestCase):
 def test_adjacent_vs_jump(self):
  self.assertFalse(trigger(3,6,'E34'));self.assertFalse(trigger(3,6,'E45'));self.assertTrue(trigger(3,6,'C4'));self.assertTrue(trigger(3,6,'C5'))
 def test_unknown_not_synthetic_crossing(self):
  self.assertFalse(trigger(0,5,'C4'));self.assertFalse(trigger(0,5,'C5'))
 def test_exact_34_does_not_accept_45(self):
  s=project(raw([3,4,5,5]),'E34','S');self.assertEqual(s.buy_event.tolist(),[0,1,0,0])
 def test_exact_45(self):
  s=project(raw([3,4,5,4,5]),'E45','S');self.assertEqual(s.buy_event.tolist(),[0,0,1,0,1])
 def test_six_arms_only_after_reached(self):
  s=project(raw([3,4,5,4,6,5]),'E34','X6');self.assertEqual(s.target.tolist(),[0,1,1,1,1,0]);self.assertEqual(s.exit_reason.iloc[-1],'cool_below_6')
 def test_seven_can_exit_before_structure(self):
  s=project(raw([3,4,6,7,6]),'C4','X7');self.assertEqual(s.target.tolist(),[0,1,1,1,0])
 def test_seven_not_reached_still_has_structural_exit(self):
  s=project(raw([3,4,5,2]),'E34','X7');self.assertEqual(s.exited.tolist(),[0,0,0,1])
 def test_invalidated_cannot_reenter_same_day(self):
  r=raw([3,4,3,5]);r.loc[r.index[3],'structural_invalidated']=1;s=project(r,'C4','S');self.assertEqual(s.entered.iloc[-1],0)
 def test_gap_cancel_requires_new_buy_event(self):
  ds=pd.date_range('2020-01-01',periods=7);d=pd.DataFrame(dict(open=[10,10,8,10,10,10,10],close=10,high=11,low=7,volume=100),index=ds)
  s=pd.DataFrame(dict(target=[0,1,1,1,1,1,1],entered=[0,1,0,0,0,0,0],floor=9.,exit_line=9.,entry_kind='',exit_reason='',buy_event=[0,1,0,0,1,0,0]),index=ds)
  _,_,_,fills,orders=backtest(d,s,dict(active=False,floor=None),'X',SCENARIOS['base'],entry_event_column='buy_event')
  self.assertEqual(fills.loc[fills.side=='buy','date'].tolist(),[str(ds[5].date())]);self.assertTrue((orders.action=='cancel_gap').any())
 def test_legacy_default_keeps_legacy_retry(self):
  ds=pd.date_range('2020-01-01',periods=5);d=pd.DataFrame(dict(open=[10,10,8,10,10],close=10,high=11,low=7,volume=100),index=ds);s=pd.DataFrame(dict(target=[0,1,1,1,1],entered=[0,1,0,0,0],floor=9.,exit_line=9.,entry_kind='',exit_reason=''),index=ds)
  _,_,_,f,_=backtest(d,s,dict(active=False,floor=None),'X',SCENARIOS['base']);self.assertEqual(f.loc[f.side=='buy','date'].tolist(),[str(ds[3].date())])
if __name__=='__main__':unittest.main()
