import unittest
import pandas as pd
from stock_shadow_portfolio import simulate
class RetentionTests(unittest.TestCase):
 def test_rank_drop_does_not_sell_and_riskoff_does(self):
  dates=pd.bdate_range('2020-01-01',periods=300);p=pd.DataFrame({'a':100.,'b':100.},index=dates);p.loc[dates[1]:,'a']=150;active=p.notna();audit=[]
  _,path=simulate(p,active,{dates[0]:['a'],dates[1]:['b'],dates[2]:[]},20,audit=audit,retain_positions=True)
  self.assertEqual(path.positions.iloc[1],2);self.assertEqual(path.positions.iloc[2],0)
  self.assertFalse(any(r['kind']=='sell' and r['date']==dates[1] for r in audit))
  self.assertGreater(path.max_position_weight.iloc[1],.1)
 def test_individual_exit_still_applies(self):
  dates=pd.bdate_range('2020-01-01',periods=300);p=pd.DataFrame({'a':100.},index=dates);a=p.notna();sell=a*False;sell.iloc[5]=True
  _,path=simulate(p,a,{dates[0]:['a']},20,retain_positions=True,sell_signals=sell)
  self.assertEqual(path.positions.iloc[5],0)
if __name__=='__main__':unittest.main()
