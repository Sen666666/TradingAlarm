import unittest
import pandas as pd
from monthly_ah_engine import run
from trend_slot_selection import TrendSlots
class Tests(unittest.TestCase):
 def test_unfilled_leader_reserves_slot_then_cancels(self):
  dates=pd.bdate_range('2024-01-01',periods=30);assets={};signals={};strength={}
  for symbol,value in [('a',9.),('b',8.)]:
   raw=pd.DataFrame({'open':10.,'high':11.,'low':9.,'close':10.,'volume':10000000.},index=dates)
   if symbol=='a':raw.loc[dates[22:24],'volume']=0
   assets[symbol]=dict(raw=raw,signal=raw.copy(),currency='CNY',lot=100,splits=[],dividends=[],volume_multiplier=1)
   signals[symbol]=pd.Series(1.,index=dates);strength[symbol]=pd.Series(value,index=dates)
  signals['a'].loc[dates[23]:]=0
  m,p,orders,d=run(assets,str(dates[22].date()),str(dates[25].date()),policy='score_change',signals=signals,cadence='daily',fx_override=pd.Series(1.,index=dates),selection=TrendSlots(strength,slots=1),entry_fraction=.1)
  self.assertFalse(any(o['symbol']=='a' for o in orders));self.assertEqual(orders[0]['symbol'],'b');self.assertEqual(orders[0]['date'],str(dates[24].date()));self.assertTrue((p.cash>=0).all())
if __name__=='__main__':unittest.main()
