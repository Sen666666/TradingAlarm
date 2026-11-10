import unittest
import pandas as pd
from stock_shadow_fresh_entry import monthly_schedule
from stock_shadow_portfolio import simulate
class FreshEntryTests(unittest.TestCase):
 def test_selection_execution_delay_is_consistent(self):
  cal=pd.bdate_range('2020-01-01',periods=5);s=pd.DataFrame({'date':[cal[0]],'symbol':['a']})
  self.assertEqual(monthly_schedule(cal,s,2),{cal[2]:['a']})
 def test_ineligible_new_position_stays_cash(self):
  dates=pd.bdate_range('2020-01-01',periods=300);p=pd.DataFrame({'a':100.},index=dates);active=p.notna();allow=active.copy();allow.iloc[0]=False
  audit=[];_,path=simulate(p,active,{dates[0]:['a'],dates[2]:['a']},20,audit=audit,buy_allowed=allow)
  self.assertEqual(path.positions.iloc[0],0);self.assertEqual(path.positions.iloc[2],1)
  self.assertEqual([x['date'] for x in audit if x['kind']=='buy'],[dates[2]])
if __name__=='__main__':unittest.main()
