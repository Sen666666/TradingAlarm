import unittest
from types import SimpleNamespace
from datetime import timedelta
from pilot import *
import test_sector_account as F

class Tests(unittest.TestCase):
 def account(self):return Account('P1',SimpleNamespace(protocol={'fractional_split_policy':'floor_position_fraction_writeoff'}),SimpleNamespace(factor=lambda sid,at:D(1)))
 def buy(self,a,kind='core',at=F.T,price=10):
  q=F.quote(price=price);clock=A.Clock(at,at+timedelta(days=1),at.date());ok,oid=a.reserve_budget(quote=q,clock=clock,gross_budget_cny=1000,purpose='annual_rebalance',reservation_at=clock.earliest_execution_at)
  self.assertTrue(ok);a.order_meta[oid]=dict(kind=kind,clock=clock,floor=D(5),score=70,epoch=(0,1),reason='test');return a.fill_buy('A',F.window(price=price,at=clock.earliest_execution_at,cash_due_at=clock.earliest_execution_at))
 def test_layer_exit_keeps_core(self):
  a=self.account();self.buy(a);self.buy(a,'add',F.T+timedelta(days=2));clock=A.Clock(F.T+timedelta(days=4),F.T+timedelta(days=5),(F.T+timedelta(days=4)).date());a.sell('A',clock,F.quote(),[2],'CP1_add_protection');a.fill_exit('A',F.window(at=clock.earliest_execution_at));self.assertEqual(a.layers[0]['qty'],100);self.assertEqual(a.layers[1]['qty'],0);self.assertEqual(a.quantity('A'),100)
 def test_full_exit_overrides_partial(self):
  a=self.account();self.buy(a);self.buy(a,'add',F.T+timedelta(days=2));at=F.T+timedelta(days=4);clock=A.Clock(at,at+timedelta(days=1),at.date());a.sell('A',clock,F.quote(),[2],'CP1_add_protection');a.sell('A',clock,F.quote(),[1,2],'ACT_pause');self.assertIsNone(a.exits['A'].remaining_target);a.fill_exit('A',F.window(at=clock.earliest_execution_at));self.assertEqual(a.quantity('A'),0)
 def test_t1_cannot_sell_fresh_inventory(self):
  a=self.account();self.buy(a);at=F.T+timedelta(days=1);clock=A.Clock(at,at+timedelta(seconds=1),at.date());a.sell('A',clock,F.quote(),[1],'test');self.assertIsNone(a.fill_exit('A',F.window(at=at+timedelta(seconds=1))));self.assertEqual(a.quantity('A'),100)
 def test_split_matches_physical(self):
  a=self.account();self.buy(a);self.buy(a,'add',F.T+timedelta(days=2));at=F.T+timedelta(days=4);a.split(event_id='split-test',sid='A',ratio=D('1.3'),at=at,new_shares_sellable_at=at);self.assertEqual(a.quantity('A'),260);self.assertEqual([z['qty'] for z in a.layers],[130,130]);a.check()
 def test_open_guard_rejects_before_fill(self):
  a=self.account();q=F.quote();clock=A.Clock(F.T,F.T+timedelta(days=1),F.T.date());ok,oid=a.reserve_budget(quote=q,clock=clock,gross_budget_cny=1000);a.order_meta[oid]=dict(floor=D(11));self.assertIsNone(a.fill_buy('A',F.window()));self.assertEqual(a.quantity('A'),0);self.assertEqual(a.available,INITIAL)
 def test_fractional_minimum_not_invented(self):
  a=self.account();ok,_=a.reserve_budget(quote=F.quote(price=500,rule=L.QuantityRule('star',200,1,1,True,1)),clock=F.CLOCK,gross_budget_cny=20000);self.assertFalse(ok);self.assertFalse(a.buys)
 def test_deferred_funding_uses_actual_cash(self):
  a=self.account();a.available=D(500);q=F.quote();clock=F.CLOCK;ok,_=a.reserve_budget(quote=q,clock=clock,gross_budget_cny=10000,purpose='annual_rebalance',reservation_at=clock.earliest_execution_at);self.assertFalse(ok);self.assertEqual(a.available,D(500))
 def test_allocation_equal_and_weighted(self):
  q=F.quote();items=[dict(sid='a',budget=D(100),weight=1,quote=q),dict(sid='b',budget=D(100),weight=3,quote=q)];v=allocate(items,D(100));self.assertLessEqual(sum(v.values()),D(100));self.assertAlmostEqual(float(v['b']/v['a']),3,places=3)
 def test_allocation_caps_and_fees(self):
  q=F.quote(fees=F.MINIMUM);items=[dict(sid='a',budget=D(10),weight=10,quote=q),dict(sid='b',budget=D(100),weight=1,quote=q)];v=allocate(items,D(60));self.assertLessEqual(v['a'],D(10));self.assertLessEqual(sum((b+fee(q,b) for b in v.values()),ZERO),D(60))
 def test_dividend_contribution_matches_ledger(self):
  a=self.account();self.buy(a);self.buy(a,'add',F.T+timedelta(days=2));at=F.T+timedelta(days=4);a.accrue_dividend(event_id='d',sid='A',currency='CNY',net_local=D(20),ex_at=at,paid_at=None,source_id='test',entitlement_basis='test');self.assertEqual(sum(z['dividend'] for z in a.layers),D(20))

if __name__=='__main__':unittest.main()
