import unittest
from unittest.mock import patch
import pandas as pd
from campaign_engine import features,run_campaign
from campaign_claims import CampaignClaims


class ClaimIntegrationTests(unittest.TestCase):
 def test_ex_distribution_and_child_dividend_conserve_wealth_without_spendable_shares(self):
  idx=pd.bdate_range('2020-01-01',periods=320)
  raw=pd.DataFrame(dict(open=100.,high=101.,low=99.,close=100.,volume=1e7),index=idx)
  childraw=raw.copy();childraw.loc[idx[275]:,['open','high','low','close']]-=1
  child=dict(raw=childraw,currency='HKD',sector='child',dividends=[dict(ex_date=str(idx[275].date()),pay_date=str(idx[280].date()),amount=1.)],splits=[])
  parent=dict(raw=raw.copy(),signal=raw.copy(),currency='HKD',sector='parent',kind='equity',lot=10,volume_multiplier=1,dividends=[],splits=[],in_kind=[dict(ex_date=str(idx[270].date()),recipient='child',numerator=1,denominator=10,signal_reference_value=10.)])
  parent['raw'].loc[idx[270]:,['open','high','low','close']]-=10
  def fixed(a):
   f=features(a);f['atr']=1.;f['ma']=90.;f['strength']=1.;f['trend_exit']=False
   return f
  claims=CampaignClaims({'parent':parent},{'child':child})
  with patch('campaign_engine.fx_series',lambda i:pd.Series(1.,index=i)),patch('campaign_engine.features',fixed):
   _,p,orders,_,_=run_campaign({'parent':parent},start=str(idx[240].date()),entry='ma',exit_mode='trend',pyramid=False,fx_bps=0,security_claims=claims)
  self.assertEqual(len(orders),1);qty=orders[0]['units'];self.assertEqual(qty%10,0)
  self.assertEqual(claims.quantities()['child'],qty/10)
  self.assertAlmostEqual(p.loc[idx[269],'nav'],p.loc[idx[270],'nav'])
  self.assertAlmostEqual(p.loc[idx[274],'nav'],p.loc[idx[275],'nav'])
  self.assertAlmostEqual(p.loc[idx[279],'nav'],p.loc[idx[280],'nav'])
  self.assertEqual(p.loc[idx[275],'cash'],p.loc[idx[274],'cash'])
  self.assertAlmostEqual(p.loc[idx[280],'cash']-p.loc[idx[279],'cash'],qty/10)
  self.assertEqual(claims.ledger.value(str(idx[-1].date()),{'child':(str(idx[-1].date()),99.,str(idx[-1].date()),1.)},'zero_floor')['spendable_cash'],0)
  with self.assertRaises(ValueError):claims.values(idx[270],1.)
  with self.assertRaises(ValueError):claims.step(idx[270],{'parent':qty},1.,0)


if __name__=='__main__':unittest.main()
