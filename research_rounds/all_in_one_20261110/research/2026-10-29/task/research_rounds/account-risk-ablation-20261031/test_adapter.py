"""Actual ledger/admission fixtures. No historical account experiment."""
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
import json,unittest
import adapter as A
import test_bridge as T
J=A.J;D=J.D
def attempt(a,i,raw=10,sector='S',rule=None):
 rule=rule or T.T.RULE;x,why=J.LR.preview(i,D(raw),D(1),rule,T.T.MINIMUM)
 if why:return x,None,why
 at=i['clock'].earliest_execution_at;a.sync(at);a.current_nav=a.balance(at,a.market.marks(at,a.positions))['nav']
 answer,why=A.Runner.route(SimpleNamespace(sector_by_sid={i['sid']:sector}),a,i,x,at)
 return x,answer,why
class Tests(unittest.TestCase):
 def test_old_account_only_block_now_real_reserved_and_filled(self):
  a=T.account();T.progress(a,'S',T.BASE,'confirm');T.legacy(a,'OLD','LEGACY',50000,pool='confirmed',floor='9')
  i=T.intent(at=T.BASE+T.timedelta(days=1));_,r,why=T.routed(a,i);self.assertIsNone(r);self.assertEqual(why,'account_risk')
  A.enable(a);x,r,why=attempt(a,i);self.assertIsNone(why);T.reserve(a,i,x,r);fill=a.fill_buy('A',T.win(i,x))
  self.assertIsNotNone(fill);self.assertGreater(a.budget.resources()[1],.03*a.budget.nav)
 def test_core_quarter_percent_minimum_still_fails(self):
  a=T.account();A.enable(a);i=T.intent(floor='50');i.update(kind='core',role='core',quote=T.T.quote(price=100,fees=T.T.MINIMUM),budget=D(100000),cap=1000)
  J.LR.resize_core(i,D(1000000),D(1));self.assertEqual(i['cap'],0);self.assertEqual(i['size_reject'],'minimum_unit_exceeds_risk_or_nominal_cap')
 def test_two_hundred_share_minimum_still_unaffordable(self):
  a=T.account();A.enable(a);rule=replace(T.T.RULE,buy_minimum=200,buy_step=1)
  i=T.intent(floor='140');i.update(quote=T.T.quote(price=150,rule=rule,fees=T.T.MINIMUM),cap=200,budget=D(20000))
  _,r,why=attempt(a,i,raw=150,rule=rule);self.assertIsNone(r);self.assertEqual(why,'open_minimum_exceeds_frozen_contract');self.assertFalse(a.budget.orders)
 def test_probe_risk_retained(self):
  a=T.account();T.legacy(a,'OLD','LEGACY',9000,pool='probe',floor='9.46');A.enable(a)
  _,r,why=attempt(a,T.intent(at=T.BASE+T.timedelta(days=1),floor='8'));self.assertIsNone(r);self.assertIn('probe_risk',why)
 def test_sector_capital_retained(self):
  a=T.account();T.progress(a,'S',T.BASE,'confirm');T.legacy(a,'OLD','S',9400,pool='confirmed',floor='9.99');A.enable(a)
  i=T.intent(at=T.BASE+T.timedelta(days=1),floor='99');i.update(quote=T.T.quote(price=100,fees=T.T.MINIMUM),cap=200)
  _,r,why=attempt(a,i,raw=100);self.assertIsNone(r);self.assertIn('sector_capital',why)
 def test_cash_and_serial_reservations_retained(self):
  a=T.account();T.legacy(a,'OLD','LEGACY',87000);A.enable(a);accepted=[]
  for k in range(6):
   sector='S'+str(k);T.start(a,sector);T.progress(a,sector,T.ORIG,sector+'p');T.progress(a,sector,T.BASE,sector+'c')
  for k in range(6):
   sector='S'+str(k);i=T.intent(rid='new'+str(k),sid='NEW'+str(k));x,r,why=attempt(a,i,sector=sector)
   if r:T.reserve(a,i,x,r);accepted.append(r[0])
   else:self.assertIn('cash',why)
  self.assertEqual(accepted,[1900,1000]);self.assertEqual(sum(o.qty>0 for o in a.budget.orders.values()),2)
 def test_same_signal_not_reused_after_acceptance(self):
  a=T.account();A.enable(a);i=T.intent();x,r,why=attempt(a,i);self.assertIsNone(why);T.reserve(a,i,x,r)
  _,r,why=attempt(a,i);self.assertIsNone(r);self.assertEqual(why,'no_fresh_stock_CP1')
 def test_only_two_predicates_removed(self):
  self.assertNotIn("failures.append('account_risk')",(A.O/'model_without_account_check.py').read_text())
  self.assertNotIn("fails.append('account_risk')",(A.O/'route_without_account_check.py').read_text())
  for s in ('.005*budget_nav','.01*budget_nav','sector_capital','pool_capital'):
   self.assertIn(s,(A.O/'model_without_account_check.py').read_text())
  self.assertNotIn('minimum_guard',(A.O/'adapter.py').read_text())
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 A.L.save(A.O/'SYNTHETIC_GATE.json',dict(passed=r.wasSuccessful(),tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),actual_ledger_fixtures=True,historical_paths=0))
 raise SystemExit(not r.wasSuccessful())
