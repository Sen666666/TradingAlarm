from datetime import timedelta
from decimal import Decimal
import unittest
import pandas as pd
from normalize_actions import terms,normalize
from current_pool_bridge import prepare_signal
from sector_account import SectorAccount,QuantityRule
from test_sector_account import quote,window,CLOCK,T

class ActionExtensionTests(unittest.TestCase):
 def test_same_date_cash_distributions_sum_in_old_share_units(self):
  events,ignored,unresolved=normalize([
   {'1':20240627,'471':'2024-06-27(每十股 转增3.00股 红利5.00元)$'},
   {'1':20240627,'471':'2024-06-27(每十股 红利1.60元)$'}],'source','2013-01-04','2026-10-22')
  self.assertFalse(unresolved);self.assertEqual(len(events),1)
  self.assertEqual(Decimal(events[0]['cash_per_old_share']),Decimal('.66'))
  self.assertEqual(Decimal(events[0]['split_ratio']),Decimal('1.3'))
  self.assertEqual(len(events[0]['raw_text_components']),2)

 def test_rights_TERP_does_not_turn_into_holder_bonus_or_negative_dividend(self):
  e=terms({'1':20200103,'471':'2020-01-03(每十股 配股3.00股 配股价2.29元)$'},'source')
  self.assertEqual(e['cash_per_old_share'],'0');self.assertEqual(e['split_ratio'],'1')
  idx=pd.to_datetime(['2020-01-02','2020-01-03','2020-01-06']);ex=(Decimal(10)+Decimal('.3')*Decimal('2.29'))/Decimal('1.3')
  raw=pd.DataFrame({k:[10,float(ex),float(ex)] for k in ['open','high','low','close']},index=idx);raw['volume']=1000.
  out=prepare_signal(raw,{'adjustment':{'method':'theoretical_ex_price'}},[e])
  self.assertAlmostEqual(out.close.iloc[1],10);self.assertEqual(out.volume.iloc[1],1000.)
  prefix=prepare_signal(raw.iloc[:1],{'adjustment':{'method':'theoretical_ex_price'}},[e])
  pd.testing.assert_frame_equal(prefix,out.iloc[:1],check_exact=True,check_freq=False)

 def test_targeted_issuance_does_not_give_retail_free_shares(self):
  e=terms({'1':20201229,'471':'2020-12-29(每十股 少数股东转增7.88股)$'},'source')
  self.assertEqual(e['split_ratio'],'1');self.assertEqual(e['cash_per_old_share'],'0')

 def test_consideration_and_regular_bonus_keep_separate_source_categories(self):
  e=terms({'1':20130820,'471':'2013-08-20(  每10股对价股票5.0000股)$'},'source')
  self.assertEqual(Decimal(e['split_ratio']),Decimal('1.5'))
  c=terms({'1':20200103,'471':'2020-01-03(每十股 转增3.00股红利2.00元)$'},'source')
  self.assertEqual(Decimal(c['split_ratio']),Decimal('1.3'));self.assertEqual(Decimal(c['cash_per_old_share']),Decimal('.2'))

 def test_unrecognized_term_stays_unresolved_and_origin_event_is_not_backfilled(self):
  _,ignored,unresolved=normalize([{'1':20200102,'471':'2020-01-02(每十股 红利1.00元)$'},
     {'1':20200103,'471':'2020-01-03(未支持换股)$'}],'source','2020-01-02','2020-01-06')
  self.assertEqual(len(ignored),1);self.assertEqual(len(unresolved),1)

 def test_fraction_proxy_floors_aggregate_position_and_invents_no_cash(self):
  rule=QuantityRule('STAR-proxy',200,1,1,True,1)
  a=SectorAccount(initial_cash=10000,fractional_split_policy='floor_position_fraction_writeoff')
  self.assertTrue(a.reserve_budget(quote=quote(rule=rule),clock=CLOCK,gross_budget_cny=2010)[0])
  w=window(rule=rule,capacity=201);a.fill_buy('A',w);cash=a.available
  at=w.at+timedelta(days=1)
  a.split(event_id='bonus',sid='A',ratio='1.3',at=at,new_shares_sellable_at=at+timedelta(days=1))
  self.assertEqual(a.quantity('A'),261);self.assertEqual(a.available,cash)
  self.assertEqual(a.audit_log[-1]['fractional_shares_written_off'],Decimal('.3'))

if __name__=='__main__':unittest.main()
