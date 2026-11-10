"""Frozen C1 formula plus real ledger/budget/route/checkpoint fixtures; no history."""
from pathlib import Path
from types import SimpleNamespace
from datetime import timedelta
from dataclasses import asdict,replace
import sys,unittest,tempfile,pickle,copy,json
import adapter_c1 as C
J,D=C.J,C.D
sys.path.insert(0,str(J.O));import test_bridge as T

def account(mode='C1'):
 a=T.account();C.enable(a,mode);return a
def decision(a,at):
 a.current_nav=a.balance(at,a.market.marks(at,a.positions))['nav'];C.freeze_close(a,at,a.current_nav)
 return copy.deepcopy(a.budget.c1)
def attempt(a,i,sector='S',raw=None):
 raw=D(raw) if raw is not None else a.fixture_state['price']
 x,why=J.LR.preview(i,raw,a.fixture_state['factor'],T.T.RULE,T.T.MINIMUM)
 if why:return x,None,why
 at=i['clock'].earliest_execution_at;a.sync(at)
 route,why=C.Runner.route(SimpleNamespace(sector_by_sid={i['sid']:sector}),a,i,x,at)
 return x,route,why
def shell(a,mode='C1'):
 r=C.Runner.__new__(C.Runner);r.accounts={'B':a};r.c1_mode=mode;r.c1_rows=[];r.source_freeze={str(Path(C.__file__)):C.L.sha(C.__file__)}
 for name in ['daily','opportunities','funding','stage_events','balance_audit']:setattr(r,name,[])
 return r
def economic(a):
 return J.W.canon(dict(trades=a.trades,cash=a.available,positions=a.positions,layers=a.layers,metadata=a.jmeta,journal=a.journal,orders=a.budget.orders,lots=a.budget.lots,consumed=sorted(a.budget.consumed),losses={str(k):v for k,v in a.budget.losses.items()}))

class Tests(unittest.TestCase):
 def test_exact_100_90_80_90_new110_formula(self):
  s=C.C1State(D(1000000),D(1000000),D(1000000));observed=[]
  for k,(nav,high,cap) in enumerate([(1000000,1000000,'.60'),(900000,1000000,'.35'),(800000,1000000,'.10'),(900000,1000000,'.35'),(1100000,1100000,'.60')]):
   s.observe(T.BASE+timedelta(days=k),D(nav));self.assertEqual(s.high,D(high));self.assertEqual(s.fraction,D(cap));observed.append(asdict(s))
  C.IO.write_json(C.O/'FORMULA_TRACE.json',J.W.canon(observed))
 def test_real_ACT_resume_resets_phase_not_global_H(self):
  a=account();T.legacy(a,'OLD','OTHER',50000,pool='confirmed');a.fixture_state['price']=D(8);decision(a,T.BASE+timedelta(days=2));old=copy.deepcopy(a.budget.c1)
  state=dict(on=False,peak=D(1000000),saw_off=True,previous_fast=False,episode=0)
  resumed,dd,event=J.M.E.risk_policy.advance(state,a.current_nav,True,True,True,'ACT20_BREAK')
  self.assertEqual(event,'resume');self.assertEqual(resumed['peak'],a.current_nav);self.assertEqual(a.budget.c1,old);self.assertEqual(old.high,D(1000000))
 def test_same_close_idempotent_and_no_intraopen_repricing(self):
  a=account();before=decision(a,T.BASE);decision(a,T.BASE);self.assertEqual(a.budget.c1,before)
  with self.assertRaises(AssertionError):C.freeze_close(a,T.BASE,a.current_nav-D(1))
 def test_overnight_gap_true_budget_nav_and_two_fees_keep_frozen_c(self):
  a=account();T.progress(a,'S',T.BASE,'confirmed');T.legacy(a,'OLD','S',5000,pool='confirmed');snap=decision(a,T.BASE+timedelta(days=2));prior_nav=a.current_nav;a.fixture_state['price']=D('9.8')
  for k,sid in enumerate(['A','B']):
   i=T.intent(at=T.BASE+timedelta(days=2),rid='gap'+str(k),sid=sid,floor='9')
   x,r,why=attempt(a,i);self.assertIsNone(why);self.assertEqual(r[1],'confirmed');T.reserve(a,i,x,r);a.fill_buy(sid,T.win(i,x,raw='9.8'))
   self.assertEqual(a.budget.c1,snap);self.assertEqual(a.current_nav,prior_nav);self.assertNotEqual(D(str(a.budget.nav)),prior_nav)
   self.assertAlmostEqual(a.budget.nav,float(a.balance(i['clock'].earliest_execution_at,a.market.marks(i['clock'].earliest_execution_at,a.positions))['nav']))
 def test_existing_over_cap_not_sold_and_probe_still_permitted(self):
  a=account();T.progress(a,'S',T.BASE,'confirmed');T.legacy(a,'OLD','OTHER',50000,pool='confirmed');a.fixture_state['price']=D(8);decision(a,T.BASE+timedelta(days=2));a.sync(T.BASE+timedelta(days=2));before=(a.quantity('OLD'),len(a.trades),a.jmeta[a.layers[-1]['id']]['last_core_line'])
  self.assertGreater(a.budget.resources('confirmed')[0],a.budget.confirmed_fraction()*a.budget.nav)
  i=T.intent(at=T.BASE+timedelta(days=2),floor='7.9');x,r,why=attempt(a,i);self.assertIsNone(why);self.assertEqual(r[1],'probe');self.assertEqual(before,(a.quantity('OLD'),len(a.trades),a.jmeta[a.layers[-1]['id']]['last_core_line']))
 def test_migration_counts_existing_confirmed_without_releasing_probe_first(self):
  a=account();T.legacy(a,'OLD','OTHER',50000,pool='confirmed');T.legacy(a,'P','S',2000,pool='probe');a.fixture_state['price']=D(8);decision(a,T.BASE+timedelta(days=2));a.sync(T.BASE+timedelta(days=2));snapshot=(a.available,a.budget.nav,a.budget.resources(),[(x.batch,x.pool) for x in a.budget.lots])
  T.progress(a,'S',T.BASE+timedelta(days=2),'confirm');self.assertFalse(a.budget.migrate('S'));self.assertEqual(snapshot,(a.available,a.budget.nav,a.budget.resources(),[(x.batch,x.pool) for x in a.budget.lots]))
 def test_partial_pending_cancel_ack_and_original_end_session_expiry(self):
  a=account();T.progress(a,'S',T.BASE,'confirmed');decision(a,T.BASE);i=T.intent();x,r,why=attempt(a,i);self.assertIsNone(why);T.reserve(a,i,x,r);a.fill_buy('A',T.win(i,x,capacity=100));bid=i['budget_order'];before=a.budget.resources();a.budget.cancel(bid)
  self.assertEqual(before,a.budget.resources());self.assertGreater(before[2],0)
  at=i['clock'].earliest_execution_at+timedelta(hours=5);a.expire_day_buys(at);a.sync(at);decision(a,at)
  self.assertNotIn('A',a.buys);self.assertEqual(a.budget.resources()[2],0);self.assertEqual(a.quantity('A'),100);self.assertIsNone(a.fill_buy('A',T.win(i,x,at=at)))
 def test_final_request_pool_cap_agrees_with_route_limit(self):
  a=account();T.progress(a,'S',T.BASE,'confirmed');T.legacy(a,'OLD','OTHER',50000,pool='confirmed');a.fixture_state['price']=D(8);decision(a,T.BASE+timedelta(days=2));a.sync(T.BASE+timedelta(days=3));s=a.budget.sectors['S'];bar=J.ordinal(T.BASE+timedelta(days=2));token=J.V.Evidence('fresh','S','stock_cp1','21',bar-1,bar,bar,s.episode,'A',s.attempt)
  answer=a.budget.request('direct','A','S',100,8,7.9,token,bar,role='mobile');self.assertEqual(answer,'confirmed_unfunded')
 def test_probe_risk_unchanged(self):
  a=account();T.legacy(a,'OLD','OTHER',9000,pool='probe',floor='9.46');decision(a,T.BASE+timedelta(days=2));_,r,why=attempt(a,T.intent(at=T.BASE+timedelta(days=2),floor='8'));self.assertIsNone(r);self.assertIn('probe_risk',why)
 def test_sector_capital_unchanged(self):
  a=account();T.progress(a,'S',T.BASE,'confirmed');T.legacy(a,'OLD','S',9400,pool='confirmed');decision(a,T.BASE+timedelta(days=2));i=T.intent(at=T.BASE+timedelta(days=2),floor='99');i.update(quote=T.T.quote(price=100,fees=T.T.MINIMUM),cap=200)
  _,r,why=attempt(a,i,raw=100);self.assertIsNone(r);self.assertIn('sector_capital',why)
 def test_stock_cap_and_original_2percent_target_unchanged(self):
  a=account();T.progress(a,'S',T.BASE,'confirmed');T.legacy(a,'A','S',10000,pool='confirmed');decision(a,T.BASE+timedelta(days=2));_,r,why=attempt(a,T.intent(at=T.BASE+timedelta(days=2)));self.assertIsNone(r);self.assertIn('stock_capital',why)
 def test_core_point25_and_200_minimum_unchanged(self):
  i=T.intent(floor='50');i.update(kind='core',role='core',quote=T.T.quote(price=100,fees=T.T.MINIMUM),budget=D(100000),cap=1000);J.LR.resize_core(i,D(1000000),D(1));self.assertEqual(i['cap'],0)
  rule=replace(T.T.RULE,buy_minimum=200,buy_step=1);i=T.intent(floor='140');i.update(quote=T.T.quote(price=150,rule=rule,fees=T.T.MINIMUM),cap=200,budget=D(20000));_,why=J.LR.preview(i,D(150),D(1),rule,T.T.MINIMUM);self.assertEqual(why,'open_minimum_exceeds_frozen_contract')
 def test_real_fee_cash_and_quantity_NAV_bridge(self):
  a=account();T.progress(a,'S',T.BASE,'confirmed');decision(a,T.BASE);i=T.intent();x,r,why=attempt(a,i);self.assertIsNone(why);T.reserve(a,i,x,r);a.fill_buy('A',T.win(i,x));at=i['clock'].earliest_execution_at
  self.assertEqual(D(T.journal_bridge(a,at)['independent_NAV_difference']),0);self.assertGreater(a.fees_cny,0);self.assertLessEqual(a.budget.resources()[2],float(a.available)+a.budget.resources()[2])
 def test_same_receipt_consumed_once(self):
  a=account();T.progress(a,'S',T.BASE,'confirmed');decision(a,T.BASE);i=T.intent();x,r,why=attempt(a,i);T.reserve(a,i,x,r);_,r,why=attempt(a,i);self.assertIsNone(r);self.assertEqual(why,'no_fresh_stock_CP1')
 def test_fixed60_actual_economic_objects_equal_original_Bdiag(self):
  outcomes=[]
  for enabled in [False,True]:
   a=T.account();C.BASE.enable(a)
   if enabled:C.enable(a,'fixed60')
   T.progress(a,'S',T.BASE,'confirmed');T.legacy(a,'OLD','S',5000,pool='confirmed')
   close_at=T.BASE+timedelta(days=2);a.current_nav=a.balance(close_at,a.market.marks(close_at,a.positions))['nav']
   if enabled:C.freeze_close(a,close_at,a.current_nav)
   i=T.intent(at=close_at);x,why=J.LR.preview(i,D(10),D(1),T.T.RULE,T.T.MINIMUM);at=i['clock'].earliest_execution_at;a.sync(at)
   routefn=C.Runner.route if enabled else C.BASE.Runner.route;r,why=routefn(SimpleNamespace(sector_by_sid={'A':'S'}),a,i,x,at);self.assertIsNone(why);T.reserve(a,i,x,r);a.fill_buy('A',T.win(i,x));outcomes.append(economic(a))
  self.assertEqual(*outcomes)
 def test_checkpoint_real_account_state_and_identity_restore(self):
  a=account();T.progress(a,'S',T.BASE,'confirmed');decision(a,T.BASE);i=T.intent();x,r,why=attempt(a,i);T.reserve(a,i,x,r);a.fill_buy('A',T.win(i,x,capacity=100));runner=shell(a);root=Path(tempfile.mkdtemp(prefix='C1-real-state-checkpoint-',dir='/tmp'));at=i['clock'].earliest_execution_at
  with C.IO.atomic_runner_outputs(runner,C.L,root,canonicalize=J.W.canon):runner.checkpoint(root,at)
  restored=shell(account());restored.source_freeze=dict(runner.source_freeze)
  with C.IO.atomic_runner_outputs(restored,C.L,root,canonicalize=J.W.canon):self.assertEqual(restored.restore(root/'checkpoint.pkl'),at)
  self.assertEqual(economic(runner.accounts['B']),economic(restored.accounts['B']));self.assertEqual(runner.accounts['B'].budget.c1,restored.accounts['B'].budget.c1)
  self.assertTrue((root/'checkpoint.provenance.json').exists());C.IO.write_json(C.O/'CHECKPOINT_FIXTURE.json',dict(passed=True,path=str(root),global_H_persisted=True,partial_pending_and_actual_lot_persisted=True))
 def test_static_only_three_pool_literals_and_close_hook_change(self):
  self.assertEqual(C.REQUEST_OLD,C.REQUEST_NEW.replace('self.confirmed_fraction()','0.60'));self.assertEqual(C.MIGRATE_OLD,C.MIGRATE_NEW.replace('self.confirmed_fraction()','.60'));self.assertEqual(C.ROUTE_OLD,C.ROUTE_NEW.replace('b.confirmed_fraction()','.60'))
  self.assertEqual(C.PLANNING_OLD,C.PLANNING_NEW.replace('freeze_close(a,at,a.current_nav);',''))
  self.assertIs(C.Runner.opening,J.Runner.opening)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));C.IO.write_json(C.O/'SYNTHETIC_GATE.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),real_ledger_budget_route_checkpoint=True,historical_paths=0));raise SystemExit(not result.wasSuccessful())
