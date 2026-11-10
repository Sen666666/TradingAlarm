import unittest
from types import SimpleNamespace
from datetime import timedelta
from study import *
import test_sector_account as F
class Tests(unittest.TestCase):
 def item(self,s='A',price=100,floor=95,rule=F.RULE,nav=1000000):
  i=dict(sid=s,quote=F.quote(sid=s,price=price,rule=rule),floor=D(str(floor)),kind='core',clock=F.CLOCK,weight=1,group=1,score=60,epoch=(0,1),reason='I_early_probe');resize_core(i,D(nav),ONE);return i
 def test_narrow_protection_allows_more_than_old_two_percent(self):
  i=self.item();self.assertGreater(i['budget'],D(20000));self.assertLessEqual(i['budget'],D(100000));self.assertLessEqual(protection_risk(i['cap'],i['reference_price'],D(95),F.FREE),D(2500))
 def test_high_price_minimum_risk_rejected(self):
  star=L.QuantityRule('star',200,1,1,True,1);i=self.item(price=500,floor=400,rule=star);self.assertEqual(i['cap'],0);self.assertTrue(i['size_reject'])
 def test_high_price_narrow_protection_can_fit(self):
  star=L.QuantityRule('star',200,1,1,True,1);i=self.item(price=400,floor=390,rule=star);self.assertGreaterEqual(i['cap'],200);self.assertGreater(i['budget'],D(20000))
 def test_gap_up_can_reduce_but_never_increase_frozen_shares(self):
  i=self.item();x,why=preview(i,D(101),ONE,F.RULE,F.FREE);self.assertIsNone(why);self.assertLessEqual(x['maxq'],i['cap']);self.assertLessEqual(protection_risk(x['maxq'],x['price'],x['floor'],F.FREE),i['risk_budget'])
 def test_gap_below_protection_no_order(self):
  i=self.item();x,why=preview(i,D(94),ONE,F.RULE,F.FREE);self.assertIsNone(x);self.assertEqual(why,'open_at_or_below_protection')
 def test_open_minimum_risk_above_budget_no_order(self):
  i=self.item();x,why=preview(i,D(150),ONE,F.RULE,F.FREE);self.assertIsNone(x);self.assertTrue(why)
 def example(self,s,p,minq,maxq,weight=1,schedule=F.FREE):
  rule=L.QuantityRule(s,minq,1 if minq==200 else 100,1 if minq==200 else 100,True,1)
  return dict(sid=s,minq=minq,maxq=maxq,rule=rule,weight=D(weight),qty=0,cost=lambda q:D(q)*D(p)+fees(q,D(p),schedule,'buy'))
 def test_minimum_round_precedes_large_topup(self):
  a=self.example('expensive',100,200,200);b=self.example('cheap',10,100,2000);v,audit=whole_orders([a,b],D(30000));self.assertEqual(v['expensive'],200);self.assertGreaterEqual(v['cheap'],100)
 def test_insufficient_cash_does_not_create_fragment(self):
  a=self.example('a',100,200,200);b=self.example('b',110,200,200);v,_=whole_orders([a,b],D(15000));self.assertEqual(v,dict(a=0,b=0))
 def test_quantities_capped_and_fees_included(self):
  a=self.example('a',10,100,500,schedule=F.MINIMUM);b=self.example('b',11,100,500,schedule=F.MINIMUM);v,_=whole_orders([a,b],D(3500));self.assertLessEqual(sum(x['cost'](v[x['sid']]) for x in [a,b] if v[x['sid']]),D(3500));self.assertTrue(all(q==0 or q%100==0 for q in v.values()))
 def test_priority_allocation_deterministic(self):
  def run():
   x=[self.example('b',10,100,500,3),self.example('a',10,100,500,1)];return whole_orders(x,D(2500))[0]
  self.assertEqual(run(),run())
 def test_known_open_reservation_does_not_forge_prior_quote(self):
  a=Account('P1',SimpleNamespace(protocol={'fractional_split_policy':'floor_position_fraction_writeoff'}),SimpleNamespace(factor=lambda sid,at:ONE));i=self.item(price=10,floor=9);a.reserve_quantity(i,100,D('9.5'),F.FREE,F.CLOCK.earliest_execution_at);self.assertEqual(a.buys['A'].quote.raw_price,D(10));fill=a.fill_buy('A',F.window(price=9.5,at=F.CLOCK.earliest_execution_at));self.assertEqual(fill.shares,100);self.assertEqual(a.layers[0]['kind'],'core');a.check()
 def test_original_bp_boundary_tests(self):
  import test_pilot
  suite=unittest.defaultTestLoader.loadTestsFromModule(test_pilot);r=unittest.TestResult();suite.run(r);self.assertTrue(r.wasSuccessful(),r.errors)
if __name__=='__main__':unittest.main()
