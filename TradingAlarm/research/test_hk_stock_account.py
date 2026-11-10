import unittest
import numpy as np
import pandas as pd
from hk_stock_account_pilot import run
class HKAccountTests(unittest.TestCase):
 def data(self):
  idx=pd.bdate_range('2021-01-01',periods=390);price=np.linspace(100,140,len(idx))
  raw={c:pd.DataFrame(dict(open=price,close=price,high=price+1,low=price-1,volume=1e7),index=idx) for c in ['00700','09618','03690']}
  return raw,{c:[] for c in raw},pd.Series(1.,index=idx),pd.Series(.5,index=idx)
 def test_future_prices_and_fx_do_not_change_past(self):
  raw,events,fx,target=self.data();_,p,orders=run(raw,events,fx,target)
  cutoff=p.index[-20];changed={c:f.copy() for c,f in raw.items()}
  for f in changed.values():f.loc[cutoff:,['open','close','high','low']]*=1.2
  fx2=fx.copy();fx2.loc[cutoff:]*=1.3
  _,q,_=run(changed,events,fx2,target)
  pd.testing.assert_frame_equal(p[p.index<cutoff],q[q.index<cutoff])
  self.assertTrue((p.cash>=0).all());self.assertTrue(all(x['signal_date']<x['date'] for x in orders))
 def test_unpaid_dividend_cannot_fund_same_day_buys(self):
  raw,events,fx,target=self.data();start=raw['00700'].loc['2022-01-01':].index
  events['00700']=[dict(ex=start[5],pay=start[10],amount=1.,currency='HKD')]
  _,p,_=run(raw,events,fx,target)
  self.assertGreater(p.loc[start[5],'cash_receivable'],0)
  self.assertEqual(p.loc[start[10],'cash_receivable'],0)
 def test_other_primary_does_not_receive_tencent_distributions(self):
  raw,events,fx,target=self.data()
  for code in ['09618','03690']:
   _,p,_=run({code:raw[code]},{code:[]},fx,target,primary=code)
   self.assertTrue((p.security_claim_value==0).all())
 def test_future_dividend_fixing_not_known_early(self):
  raw,events,fx,target=self.data();idx=raw['09618'].index;fx[:]=7.8
  event=dict(ex=idx[275],pay=idx[300],amount=1.,currency='USD',settlement=dict(fixing=str(idx[285].date()),hkd_per_share=7.7))
  _,p,_=run({'09618':raw['09618']},{'09618':[event]},fx,target,primary='09618')
  changed=dict(event,settlement=dict(fixing=str(idx[285].date()),hkd_per_share=8.1))
  _,q,_=run({'09618':raw['09618']},{'09618':[changed]},fx,target,primary='09618')
  pd.testing.assert_frame_equal(p.loc[:idx[285]],q.loc[:idx[285]])
  self.assertNotEqual(p.loc[idx[286],'cash_receivable'],q.loc[idx[286],'cash_receivable'])
  self.assertEqual(p.loc[idx[300],'cash_receivable'],0)
 def test_execution_lot_and_signal_delay(self):
  raw,events,fx,target=self.data();idx=raw['09618'].index
  target[:]=0;signal=idx[270];target.loc[signal:]=1
  _,p,orders=run({'09618':raw['09618']},{'09618':[]},fx,target,primary='09618',order_increment=400,signal_lag=2)
  self.assertEqual(orders[0]['date'],str(idx[272].date()))
  self.assertEqual(orders[0]['signal_date'],str(signal.date()))
  self.assertTrue(all(o['delta']%400==0 for o in orders))
  self.assertTrue((p.cash>=0).all())
 def test_invalid_execution_assumptions_fail_closed(self):
  raw,events,fx,target=self.data()
  for kw in [dict(order_increment=0),dict(order_increment=1.5),dict(signal_lag=0),dict(signal_lag=999)]:
   with self.assertRaises(ValueError):run(raw,events,fx,target,**kw)
 def test_usd_signal_matches_equivalent_hkd_cash(self):
  from hk_stock_rule_transfer import targets_for
  raw,events,fx,target=self.data();parent=raw['09618'];fx[:]=7.8
  ex=parent.index[250]
  usd=[dict(ex=ex,pay=parent.index[260],amount=2.,currency='USD')]
  hkd=[dict(ex=ex,pay=parent.index[260],amount=15.6,currency='HKD')]
  pd.testing.assert_frame_equal(targets_for(parent,usd,fx),targets_for(parent,hkd,fx))
if __name__=='__main__':unittest.main()
