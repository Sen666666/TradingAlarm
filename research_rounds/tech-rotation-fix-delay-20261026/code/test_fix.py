from study_common import *
from engine_fix import Account,Runner
from dataclasses import replace
from decimal import Decimal as D
from datetime import timedelta
import unittest
fixture=import_path('rotation_original_tests',BASE/'code/test_contracts.py')

class FixTests(unittest.TestCase):
 def setup_pair(self,delay=False):
  r,a,at,c,ss,gg=fixture.Contracts().setup_rotation();a.__class__=Account;a.cfg={'sd':True};r.__class__=Runner;a.market.actions={};r.start_swap(a,at,c,ss,gg)
  if delay:a.delay_events=1;a.exits['S0'].delay_remaining=1
  return r,a,at,c
 def sell(self,r,a,at):
  w=fixture.window(sid='S0',at=at,cash_due_at=at,eid='sale:'+str(at));f=a.fill_exit('S0',w);a.settle_due(at);return f
 def test_sale_then_buy_same_day_real_cash_and_source_contract(self):
  r,a,T,c=self.setup_pair();S=c.earliest_execution_at;a.available=D(0);self.assertIsNotNone(self.sell(r,a,S));self.assertEqual(a.available,D(100000));r.after_sales(a,S);self.assertIn('N',a.buys)
  o=a.buys['N'];self.assertEqual(a.intents[o.order_id]['decision_at'],T);self.assertEqual(a.intents[o.order_id]['funded_at'],S);self.assertLessEqual(o.budget_cny,D(150000));self.assertIsNone(a.fill_buy('N',fixture.window(sid='N',at=S)))
  r.market.window=lambda sid,at,side,m:fixture.window(sid=sid,at=at,cash_due_at=at)
  r.after_buys(a,S);self.assertGreater(a.quantity('N'),0);f=a.fills[-1];self.assertEqual(f.at,S+timedelta(seconds=1));self.assertGreaterEqual(a.available,0)
 def test_no_sale_does_not_create_buy(self):
  r,a,T,c=self.setup_pair();r.after_sales(a,c.earliest_execution_at);self.assertNotIn('N',a.buys)
 def test_partial_sale_keeps_pair_unfunded(self):
  r,a,T,c=self.setup_pair();S=c.earliest_execution_at;w=fixture.window(sid='S0',at=S,capacity=100,cash_due_at=S);a.fill_exit('S0',w);a.settle_due(S);r.after_sales(a,S);self.assertGreater(a.quantity('S0'),0);self.assertNotIn('N',a.buys)
 def test_each_leg_delay_consumed_once(self):
  r,a,T,c=self.setup_pair(delay=True);S=c.earliest_execution_at;self.assertIsNone(self.sell(r,a,S));self.assertIsNotNone(self.sell(r,a,S+timedelta(days=1)));S+=timedelta(days=1);r.after_sales(a,S);r.market.window=lambda sid,at,side,m:fixture.window(sid=sid,at=at,cash_due_at=at,eid=str(at));r.after_buys(a,S);self.assertEqual(a.quantity('N'),0);r.after_buys(a,S+timedelta(days=1));self.assertGreater(a.quantity('N'),0)
 def test_support_failure_rejects_buy_at_execution(self):
  r,a,T,c=self.setup_pair();S=c.earliest_execution_at;self.sell(r,a,S);r.after_sales(a,S);r.market.window=lambda sid,at,side,m:fixture.window(sid=sid,at=at,price=8,cash_due_at=at);r.after_buys(a,S);self.assertEqual(a.quantity('N'),0);self.assertNotIn('N',a.buys)
 def test_latch_preserves_order_one_day_and_expires_second(self):
  r,a,T,c=self.setup_pair();a.cfg={'latch':True};a.swap=None;a.market.sessions['A']=[c.earliest_execution_at+timedelta(days=i) for i in range(5)]
  ok,oid=a.reserve_budget(quote=fixture.quote(sid='N'),clock=c,gross_budget_cny=D(10000));self.assertTrue(ok);a.expire_day_buys(c.earliest_execution_at+timedelta(hours=5));self.assertEqual(a.buys['N'].order_id,oid);a.expire_day_buys(c.earliest_execution_at+timedelta(days=1,hours=5));self.assertNotIn('N',a.buys)

if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FixTests));
 if r.wasSuccessful():write(HERE/'technical/synthetic.json',dict(passed=True,tests=r.testsRun))
 else:sys.exit(1)
