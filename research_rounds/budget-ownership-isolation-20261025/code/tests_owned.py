from budget_common import *
from owned_account import OwnedAccount
import unittest
from decimal import Decimal as D
sys.path.append(str(OLD/'code'))
from test_sector_account import quote,window,T,CLOCK,FREE,MINIMUM,fx
from sector_account import SectorAccount
from dataclasses import replace
from datetime import timedelta

class Tests(unittest.TestCase):
 def account(self,isolate=True):return OwnedAccount(initial_cash=10000,owners=['G','H','J'],owner_of_sid={'A':'G','B':'H'},isolate=isolate)
 def test_cash_limit_and_shared_identity(self):
  iso=self.account();shared=self.account(False);original=SectorAccount(initial_cash=10000)
  for a in [iso,shared,original]:self.assertTrue(a.reserve_budget(quote=quote(),clock=CLOCK,gross_budget_cny=6000)[0])
  self.assertLess(iso.buys['A'].budget_cny,shared.buys['A'].budget_cny)
  self.assertEqual(shared.buys,original.buys);self.assertEqual(shared.audit_log,original.audit_log);self.assertLess(shared.owner_cash['G'],0)
  for a in [shared,original]:a.fill_buy('A',window())
  self.assertEqual(shared.audit_log,original.audit_log);self.assertEqual(shared.available,original.available)
 def test_cancel_and_partial_fill_refund(self):
  a=self.account();before=a.owner_cash['G'];a.reserve_budget(quote=quote(),clock=CLOCK,gross_budget_cny=3000);a.fill_buy('A',window(capacity=100));a.expire_day_buys(T+timedelta(days=1,hours=1));self.assertEqual(a.owner_cash['G'],before-D(1000));a.check()
 def test_sale_remains_unavailable_until_settled(self):
  a=self.account();a.reserve_budget(quote=quote(),clock=CLOCK,gross_budget_cny=2000);a.fill_buy('A',window());at=T+timedelta(days=2);clock=replace(CLOCK,decision_at=at,earliest_execution_at=at+timedelta(days=1),session_date=at.date());a.request_exit(quote(),clock);a.fill_exit('A',window(at=at+timedelta(days=1),eid='sell'))
  before=a.owner_cash['G'];a.settle_due(at+timedelta(days=1));self.assertEqual(a.owner_cash['G'],before);a.settle_due(at+timedelta(days=3));self.assertEqual(a.owner_cash['G'],D('3333.33'));a.check()
 def test_dividend_belongs_to_original_sector(self):
  a=self.account();a.accrue_dividend(event_id='d',sid='A',currency='CNY',net_local=12,ex_at=T,paid_at=T,source_id='synthetic',entitlement_basis='test');a.pay_dividend('d',at=T,fx=fx(),payment_evidence_id='p',payment_known_at=T);self.assertEqual(a.owner_cash['G'],D('3345.33'));self.assertEqual(a.owner_cash['H'],D('3333.33'));a.check()
 def test_fee_topups_and_nested_release(self):
  a=self.account();a.reserve_budget(quote=quote(fees=MINIMUM),clock=CLOCK,gross_budget_cny=3000);a.fill_buy('A',window(price=5,fees=MINIMUM));a.check();self.assertEqual(a.owner_cash['G'],D('3333.33')-D(1500)-D(5))
 def test_zero_ownership_cannot_borrow(self):
  a=self.account();a.owner_cash['H']+=a.owner_cash['G'];a.owner_cash['G']=D(0);self.assertFalse(a.reserve_budget(quote=quote(),clock=CLOCK,gross_budget_cny=1500)[0]);self.assertFalse(a.buys);a.check()

if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));assert r.wasSuccessful();write(HERE/(sys.argv[1] if len(sys.argv)>1 else 'technical/tests.json'),dict(passed=True,tests=r.testsRun,recorded_at=now()))
