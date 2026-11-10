import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from campaign_engine import features,run_campaign,order_priority
class CampaignTests(unittest.TestCase):
 def test_foreign_dividend_fixing_is_causal_and_same_day_components_are_retained(self):
  a=self.asset();idx=a['raw'].index;a['currency']='HKD'
  for col in ['open','high','low','close']:a['raw'].loc[idx[250]:,col]=160.
  a['raw'].loc[idx[270]:,['open','high','low','close']]-=9.8
  a['dividend_fx']=pd.Series(7.8,index=idx)
  a['dividends']=[dict(ex_date=str(idx[270].date()),pay_date=str(idx[280].date()),amount=1.,currency='USD',settlement=dict(fixing=str(idx[275].date()),hkd_per_share=8.)),dict(ex_date=str(idx[270].date()),pay_date=str(idx[280].date()),amount=2.,currency='HKD')]
  b={**a,'dividend_fx':a['dividend_fx'].copy(),'dividends':[dict(e) for e in a['dividends']]}
  b['dividend_fx'].loc[idx[276]:]=9.;b['dividends'][0]['settlement']=dict(fixing=str(idx[275].date()),hkd_per_share=10.)
  with patch('campaign_engine.fx_series',lambda index:pd.Series(1.,index=index)):
   _,p,orders,_,_=run_campaign({'a':a},start=str(idx[240].date()),entry='ma',pyramid=False)
   _,q,_,_,_=run_campaign({'a':b},start=str(idx[240].date()),entry='ma',pyramid=False)
  pd.testing.assert_frame_equal(p.loc[:idx[275]],q.loc[:idx[275]])
  qty=orders[0]['units'];self.assertEqual(len(orders),1)
  self.assertAlmostEqual(p.loc[idx[270],'nav'],p.loc[idx[269],'nav'])
  self.assertAlmostEqual((p.loc[idx[276],'nav']-p.loc[idx[275],'nav'])*1e6,.2*qty)
  self.assertAlmostEqual(p.loc[idx[280],'fees'],10.*qty*.001)
  self.assertAlmostEqual(p.loc[idx[280],'cash']-p.loc[idx[279],'cash'],10.*qty*.999)
 def test_explicit_asset_kind_does_not_change_signal_or_accounting(self):
  a=self.asset();b={**a,'kind':'defensive'}
  with patch('campaign_engine.fx_series',lambda index:pd.Series(1.,index=index)):
   _,p,o,c,s=run_campaign({'a':a},start='2020-12-01',entry='breakout',pyramid=False)
   _,q,oo,cc,ss=run_campaign({'a':b},start='2020-12-01',entry='breakout',pyramid=False,eligible_kinds=('defensive',))
   with self.assertRaises(ValueError):run_campaign({'a':b})
  pd.testing.assert_frame_equal(p,q);self.assertEqual((o,c,s),(oo,cc,ss))
 def test_capacity_changes_only_position_limit_and_keeps_account_funded(self):
  assets={str(i):self.asset() for i in range(5)}
  for n,a in assets.items():a['sector']=n
  with patch('campaign_engine.fx_series',lambda index:pd.Series(1.,index=index)):
   _,p,_,_,_=run_campaign(assets,start='2020-12-01',entry='ma',pyramid=False,max_positions=4)
   _,q,_,_,_=run_campaign(assets,start='2020-12-01',entry='ma',pyramid=False,max_positions=5)
  self.assertEqual((p.filter(like='w_')>0).sum(axis=1).max(),4)
  self.assertEqual((q.filter(like='w_')>0).sum(axis=1).max(),5)
  self.assertTrue((q.cash>=0).all())
 def test_layer_mode_future_prices_do_not_change_earlier_account(self):
  a=self.asset();idx=a['raw'].index;b={**a,'raw':a['raw'].copy(),'signal':a['signal'].copy()}
  b['raw'].iloc[310:,0:4]*=.5;b['signal'].iloc[310:,0:4]*=.5
  with patch('campaign_engine.fx_series',lambda index:pd.Series(1.,index=index)):
   _,p,orders,_,_=run_campaign({'a':a},start=str(idx[240].date()),entry='ma',exit_mode='trend',stop_mode='layers')
   _,q,changed,_,_=run_campaign({'a':b},start=str(idx[240].date()),entry='ma',exit_mode='trend',stop_mode='layers')
  pd.testing.assert_frame_equal(p.loc[:idx[309]],q.loc[:idx[309]])
  cutoff=str(idx[310].date())
  self.assertEqual([o for o in orders if o['date']<cutoff],[o for o in changed if o['date']<cutoff])
 def test_layer_stop_sells_only_add_inventory_across_split_and_closed_session(self):
  a=self.asset();idx=a['raw'].index
  prices=np.full(len(idx),100.);prices[241:243]=110.;prices[243:245]=120.;prices[245:]=110.
  for col in ['open','high','low','close']:a['raw'][col]=prices.copy()
  a['raw'].loc[idx[247]:,['open','high','low','close']]/=2
  a['splits']=[dict(date=str(idx[247].date()),ratio=2)]
  a['raw'].loc[idx[246],'volume']=0
  def fixed_features(asset):
   f=features(asset);f['atr']=2.;f['ma']=0.;f['strength']=1.;f['trend_exit']=False;f.loc[idx[250]:,'trend_exit']=True
   return f
  with patch('campaign_engine.fx_series',lambda index:pd.Series(1.,index=index)),patch('campaign_engine.features',fixed_features):
   _,path,orders,closed,_=run_campaign({'a':a},start=str(idx[240].date()),entry='ma',exit_mode='trend',stop_mode='layers')
  campaign=[o for o in orders if o['campaign_id']==1];buys=[o for o in campaign if o['units']>0];sells=[o for o in campaign if o['units']<0]
  self.assertEqual(len(buys),3);self.assertEqual(len(sells),2)
  self.assertEqual(sells[0]['date'],str(idx[247].date()))
  self.assertEqual(-sells[0]['units'],2*buys[2]['units'])
  self.assertEqual(-sells[1]['units'],2*(buys[0]['units']+buys[1]['units']))
  self.assertGreater(path.loc[idx[247],'w_a'],0)
  self.assertEqual(sells[1]['date'],str(idx[251].date()))
  expected=sum(-o['units']*o['raw_open']-o['fee'] for o in campaign)
  self.assertAlmostEqual(closed[0]['pnl'],expected)
  self.assertAlmostEqual(path.loc[idx[251],'nav']*1e6-1e6,expected)
 def test_optional_audit_does_not_change_trades(self):
  a=self.asset();audit=[]
  with patch('campaign_engine.fx_series',lambda index:pd.Series(1.,index=index)):
   baseline=run_campaign({'a':a},start='2020-12-01',entry='ma')
   traced=run_campaign({'a':a},start='2020-12-01',entry='ma',decision_audit=audit)
  pd.testing.assert_frame_equal(baseline[1],traced[1])
  pd.testing.assert_series_equal(pd.Series(baseline[0]),pd.Series(traced[0]));self.assertEqual(baseline[2:],traced[2:])
  self.assertTrue(any(e['event']=='sizing' for e in audit))
 def asset(self,n=340):
  idx=pd.bdate_range('2020-01-01',periods=n);p=np.linspace(100,180,n)
  raw=pd.DataFrame({'open':p,'high':p+1,'low':p-1,'close':p,'volume':1e7},index=idx)
  return dict(raw=raw,signal=raw.copy(),splits=[],dividends=[],lot=1,currency='CNY',kind='equity',sector='test',volume_multiplier=1)
 def test_additive_adjustment_is_causal_and_continuous(self):
  a=self.asset();idx=a['raw'].index
  a['raw'].loc[idx[280]:,['open','high','low','close']]/=2
  a['splits']=[dict(date=str(idx[280].date()),ratio=2)]
  a['raw'].loc[idx[290]:,['open','high','low','close']]-=1
  a['dividends']=[dict(ex_date=str(idx[290].date()),pay_date=str(idx[295].date()),amount=1)]
  f=features(a);expected=np.linspace(100,180,len(idx))
  np.testing.assert_allclose(f.close,expected)
  b={**a,'raw':a['raw'].copy()};b['raw'].iloc[320:,0:4]*=3
  pd.testing.assert_frame_equal(f.iloc[:320],features(b).iloc[:320])
 def test_no_future_prices_change_past_account(self):
  a=self.asset();idx=a['raw'].index
  with patch('campaign_engine.fx_series',lambda index:pd.Series(1.,index=index)):
   _,p,orders,_,_=run_campaign({'a':a},start=str(idx[240].date()),entry='ma')
   b={**a,'raw':a['raw'].copy(),'signal':a['signal'].copy()};b['raw'].iloc[310:,0:4]*=.5;b['signal'].iloc[310:,0:4]*=.5
   _,q,_,_,_=run_campaign({'a':b},start=str(idx[240].date()),entry='ma')
  pd.testing.assert_frame_equal(p.loc[:idx[309]],q.loc[:idx[309]])
  self.assertTrue(orders);self.assertTrue(all(o['signal_date']<o['date'] for o in orders));self.assertTrue((p.cash>=0).all())
 def test_pyramids_use_favorable_actual_prices_and_zero_volume_no_fill(self):
  a=self.asset();idx=a['raw'].index;a['raw'].loc[idx[240:244],'volume']=0
  with patch('campaign_engine.fx_series',lambda index:pd.Series(1.,index=index)):
   _,_,orders,_,_=run_campaign({'a':a},start=str(idx[240].date()),entry='ma')
  buys=[o for o in orders if o['units']>0]
  self.assertEqual(len(buys),3)
  self.assertTrue(all(buys[i]['raw_open']>buys[i-1]['raw_open'] for i in range(1,len(buys))))
  self.assertTrue(all(a['raw'].loc[o['date'],'volume']>0 for o in orders))
 def test_split_and_dividend_do_not_create_wealth(self):
  a=self.asset();idx=a['raw'].index
  for c in ['open','high','low','close']:a['raw'].loc[idx[250]:,c]=160.+(1 if c=='high' else -1 if c=='low' else 0)
  a['raw'].loc[idx[270]:,['open','high','low','close']]/=2
  a['raw'].loc[idx[280]:,['open','high','low','close']]-=1
  a['splits']=[dict(date=str(idx[270].date()),ratio=2)]
  a['dividends']=[dict(ex_date=str(idx[280].date()),pay_date=str(idx[285].date()),amount=1)]
  with patch('campaign_engine.fx_series',lambda index:pd.Series(1.,index=index)):
   _,p,orders,_,_=run_campaign({'a':a},start=str(idx[240].date()),entry='ma',pyramid=False)
  self.assertAlmostEqual(p.loc[idx[269],'nav'],p.loc[idx[270],'nav'])
  self.assertAlmostEqual(p.loc[idx[279],'nav'],p.loc[idx[280],'nav'])
  self.assertAlmostEqual(p.loc[idx[284],'nav'],p.loc[idx[285],'nav'])
 def test_low_atr_priority_uses_raw_price_and_exits_first(self):
  a=pd.Series(dict(close=110.,cash_adjustment=10.,atr=2.,strength=.8))
  b=pd.Series(dict(close=100.,cash_adjustment=0.,atr=3.,strength=.9))
  self.assertLess(order_priority('a',{'type':'entry'},a,'low_atr'),order_priority('b',{'type':'entry'},b,'low_atr'))
  self.assertLess(order_priority('b',{'type':'exit'},b,'low_atr'),order_priority('a',{'type':'entry'},a,'low_atr'))
  a['close']=210.;a['cash_adjustment']=110.
  self.assertAlmostEqual(order_priority('a',{'type':'entry'},a,'low_atr')[1],.02)
if __name__=='__main__':unittest.main()
