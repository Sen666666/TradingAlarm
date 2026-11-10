import unittest
import pandas as pd
from stock_shadow_portfolio import simulate
class DailyExitTests(unittest.TestCase):
 def test_exit_waits_for_quote_and_blocks_same_day_rebuy(self):
  dates=pd.bdate_range('2020-01-01',periods=300);p=pd.DataFrame({'a':100.},index=dates);active=p.notna();active.iloc[1:3]=False;sell=active.copy()*False;sell.iloc[1]=True
  p.iloc[3]=80;audit=[];m,path=simulate(p,active,{dates[0]:['a'],dates[3]:['a']},20,audit=audit,sell_signals=sell)
  self.assertEqual(path.positions.iloc[2],1);self.assertEqual(path.positions.iloc[3],0)
  exits=[r for r in audit if r.get('reason')=='daily_trend_exit'];self.assertEqual(len(exits),1);self.assertEqual(exits[0]['date'],dates[3]);self.assertAlmostEqual(exits[0]['value'],80000)
  self.assertEqual(m['pending_exit_days'],2)
 def test_empty_exit_signal_reproduces_baseline(self):
  dates=pd.bdate_range('2020-01-01',periods=300);p=pd.DataFrame({'a':100.},index=dates);a=p.notna();schedule={dates[0]:['a'],dates[30]:[]}
  m,first=simulate(p,a,schedule,20);n,second=simulate(p,a,schedule,20,sell_signals=a*False)
  self.assertEqual(m,n);pd.testing.assert_frame_equal(first,second)
if __name__=='__main__':unittest.main()
