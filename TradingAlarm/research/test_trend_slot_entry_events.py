import unittest
import pandas as pd
from trend_slot_selection import TrendSlots
class Tests(unittest.TestCase):
 def setUp(self):
  self.d=pd.Timestamp('2024-01-02');self.strength={s:pd.Series(9.,index=pd.bdate_range(self.d,periods=3)) for s in ['a','b']};self.scores={'a':1.,'b':1.};self.empty={'a':0.,'b':0.}
 def test_missed_event_cannot_be_admitted_later(self):
  pick=TrendSlots(self.strength,slots=1,entry_events={(self.d,'a')})
  self.assertEqual(pick(self.d,self.scores,self.empty,{}),{'a':1.,'b':0.})
  self.assertEqual(pick(self.d+pd.Timedelta(days=1),self.scores,self.empty,{}),self.empty)
 def test_pending_survives_event_expiry_but_not_signal_failure(self):
  pick=TrendSlots(self.strength,slots=1,entry_events={(self.d,'a')});nextday=self.d+pd.Timedelta(days=1)
  self.assertEqual(pick(nextday,self.scores,self.empty,{'a':{'target':100}}),{'a':1.,'b':0.})
  self.assertEqual(pick(nextday,{'a':0.,'b':1.},self.empty,{'a':{'target':100}}),self.empty)
 def test_held_exit_and_group_gate_independent_of_event(self):
  pick=TrendSlots(self.strength,slots=1,groups={(self.d,'a'):'x',(self.d,'b'):'x'},gates={},entry_events={(self.d,'a')})
  self.assertEqual(pick(self.d,self.scores,self.empty,{}),self.empty)
  self.assertEqual(pick(self.d,self.scores,{'a':100.,'b':0.},{}),{'a':1.,'b':0.})
  self.assertEqual(pick(self.d,{'a':0.,'b':1.},{'a':100.,'b':0.},{}),self.empty)
class EngineTests(unittest.TestCase):
 def test_pending_first_cross_fills_after_halt_and_delay(self):
  from monthly_ah_engine import run
  dates=pd.bdate_range('2024-01-01',periods=30)
  raw=pd.DataFrame(dict(open=10.,high=11.,low=9.,close=10.,volume=1e8),index=dates)
  raw.loc[dates[22:24],'volume']=0.
  assets={'a':dict(raw=raw,signal=raw.copy(),currency='CNY',lot=100,splits=[],dividends=[])}
  signals={'a':pd.Series(1.,index=dates)}
  selector=TrendSlots({'a':pd.Series(9.,index=dates)},slots=1,entry_events={(dates[21],'a')})
  _,path,orders,_=run(assets,str(dates[22].date()),str(dates[26].date()),policy='score_change',signals=signals,cadence='daily',fx_override=pd.Series(1.,index=dates),selection=selector,entry_fraction=.1,delay=1)
  self.assertEqual(len(orders),1);self.assertEqual(orders[0]['date'],str(dates[25].date()))
  self.assertEqual(orders[0]['signal_date'],str(dates[21].date()));self.assertTrue(path.cash.ge(0).all())
if __name__=='__main__':unittest.main()
