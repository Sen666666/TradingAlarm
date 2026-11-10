import unittest
import pandas as pd
from monthly_ah_engine import run
from trend_slot_selection import TrendSlots

class Tests(unittest.TestCase):
 def test_late_listing_never_backfills_prices_or_buys_before_signal(self):
  dates=pd.bdate_range('2024-01-01',periods=50);assets={};signals={};strength={}
  for s,idx in [('old',dates),('new',dates[25:])]:
   raw=pd.DataFrame(dict(open=10.,high=11.,low=9.,close=10.,volume=1e8),index=idx)
   assets[s]=dict(raw=raw,signal=raw.copy(),currency='CNY',lot=100,splits=[],dividends=[])
   signals[s]=pd.Series(float(s=='new'),index=idx);strength[s]=pd.Series(9.,index=idx)
  m,path,orders,d=run(assets,str(dates[21].date()),str(dates[-1].date()),policy='score_change',signals=signals,cadence='daily',fx_override=pd.Series(1.,index=dates),selection=TrendSlots(strength,slots=1),entry_fraction=.1)
  self.assertTrue(path.nav.notna().all());self.assertTrue(path.loc[:dates[25],'w_new'].eq(0).all())
  self.assertTrue(all(o['date']>str(dates[25].date()) for o in orders));self.assertTrue(any(o['symbol']=='new' for o in orders))
  self.assertEqual(path.loc[dates[21],'nav'],1.)
if __name__=='__main__':unittest.main()
