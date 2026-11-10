import unittest
import numpy as np
import pandas as pd
from graded_trend_exposure import graded_exposure
class Tests(unittest.TestCase):
 def test_jump_exit_half_recovery_and_prefix(self):
  up=5+5*np.tanh(1);down=5-5*np.tanh(1);s=pd.Series([np.nan,up,5,6,np.nan,up,down,4,up,0])
  self.assertEqual(graded_exposure(s).tolist(),[0,1,.5,.5,.5,1,0,0,1,0]);pd.testing.assert_series_equal(graded_exposure(s).iloc[:5],graded_exposure(s.iloc[:5]))
 def test_full_to_half_cannot_buy_after_price_collapse(self):
  from monthly_ah_engine import run
  dates=pd.bdate_range('2024-01-01',periods=30);assets={};signals={}
  for symbol in ['a','b']:
   raw=pd.DataFrame({'open':10.,'high':11.,'low':9.,'close':10.,'volume':100000000.},index=dates)
   if symbol=='a':raw.loc[dates[23]:,['open','high','low','close']]=[1.,1.1,.9,1.]
   assets[symbol]=dict(raw=raw,signal=raw.copy(),currency='CNY',lot=100,splits=[],dividends=[])
   signals[symbol]=pd.Series(1. if symbol=='a' else 0.,index=dates)
  signals['a'].loc[dates[23]:]=.5
  _,_,orders,_=run(assets,str(dates[22].date()),str(dates[25].date()),policy='score_change',signals=signals,cadence='daily',fx_override=pd.Series(1.,index=dates))
  self.assertEqual(len([o for o in orders if o['symbol']=='a' and o['units']>0]),1)
if __name__=='__main__':unittest.main()
