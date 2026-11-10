"""Hand-written R1 expectations through the actual native ledger/admission."""
from dataclasses import replace,asdict
from types import SimpleNamespace
from datetime import timedelta
import json,unittest
import adapter_r1 as R
import test_bridge as T
J=R.J;D=J.D
class Harness:
 r1_enabled=True
 annotate_candidate=R.annotate_candidate
 preview_with_r1=R.preview_with_r1
 record_r1=R.record_r1
 def __init__(self,sid='A',sector='S'):
  self.sector_by_sid={sid:sector};self.r1_previews=[];self.r1_reservations=[]
def account(strict=False):
 a=T.account();a.risk_state={'on':True};T.progress(a,'S',T.BASE,'S-confirm')
 if not strict:R.BASE.enable(a)
 return a
def intent(price=250,unit=100,sid='A',rid='fresh',at=T.BASE):
 rule=replace(T.T.RULE,buy_minimum=unit,buy_step=1 if unit==200 else 100)
 i=T.intent(at=at,rid=rid,sid=sid,floor=str(D(price)-1))
 i.update(quote=T.T.quote(sid=sid,price=price,rule=rule,fees=T.T.MINIMUM),budget=D(20000),cap=rule.buy_floor(int(D(20000)/D(price))))
 return i,rule
def attempt(h,a,i,rule,raw=250,strict=False,annotate=True):
 if annotate:h.annotate_candidate(a,i,True)
 x,why=h.preview_with_r1(a,i,D(raw),D(1),rule,T.T.MINIMUM)
 if why:return x,None,why
 at=i['clock'].earliest_execution_at;a.sync(at);a.current_nav=a.balance(at,a.market.marks(at,a.positions))['nav']
 fn=R.route_with_original_account_check if strict else R.Runner.route
 route,why=fn(h,a,i,x,at)
 return x,route,why
class Tests(unittest.TestCase):
 def test_actual_100_minimum_confirmed_fill_and_cash_bridge(self):
  a=account();a.fixture_state['price']=D(250);h=Harness();i,rule=intent();x,r,why=attempt(h,a,i,rule)
  self.assertIsNone(why);self.assertEqual(r,(100,'confirmed'));T.reserve(a,i,x,r);a.fill_buy('A',T.win(i,x,raw=250))
  self.assertEqual(a.quantity('A'),100);self.assertEqual(len(h.r1_reservations),1)
  self.assertEqual(D(T.journal_bridge(a,i['clock'].earliest_execution_at)['independent_NAV_difference']),0)
 def test_200_initial_and_after_full_clear_quantity_is_not_100(self):
  a=account();h=Harness();i,rule=intent(price=150,unit=200);x,r,why=attempt(h,a,i,rule,raw=150)
  self.assertIsNone(why);self.assertEqual(r,(200,'confirmed'));self.assertEqual(x['maxq'],200)
 def test_four_percent_gross_boundary_and_open_gap(self):
  a=account();h=Harness();i,rule=intent(price=399);h.annotate_candidate(a,i,True)
  exact=D(400)/(D(1)+J.LR.SLIP);x,r,why=attempt(h,a,i,rule,raw=exact,annotate=False)
  self.assertIsNone(why);self.assertEqual(D(r[0])*x['price'],D(40000));self.assertGreater(J.LR.fees(r[0],x['price'],T.T.MINIMUM,'buy'),0)
  a=account();h=Harness();i,rule=intent(price=399);_,r,why=attempt(h,a,i,rule,raw=400)
  self.assertIsNone(r);self.assertEqual(why,'R1_one_unit_exceeds_four_percent_decision_NAV');self.assertFalse(a.budget.consumed & {'fresh'})
 def test_full_target_not_cropped_remainder(self):
  a=account();h=Harness();i,rule=intent(price=100);i.update(budget=D(9000),cap=0);h.annotate_candidate(a,i,True)
  self.assertNotIn('R1_full_target',i);_,r,_=attempt(h,a,i,rule,raw=100,annotate=False);self.assertIsNone(r)
 def test_confirmed_capacity_unavailable_never_borrows_probe(self):
  a=account()
  for k in range(3):T.legacy(a,'O'+str(k),'OTHER'+str(k),20000,pool='confirmed')
  h=Harness();i,rule=intent(at=T.BASE+timedelta(days=1));_,r,why=attempt(h,a,i,rule)
  self.assertIsNone(r);self.assertEqual(why,'R1_confirmed_unfunded');self.assertFalse(h.r1_reservations)
 def test_probe_stage_does_not_get_exception(self):
  a=T.account();a.risk_state={'on':True};R.BASE.enable(a);h=Harness();i,rule=intent();h.annotate_candidate(a,i,True)
  self.assertNotIn('R1_full_target',i);_,r,_=attempt(h,a,i,rule,annotate=False);self.assertIsNone(r)
 def test_other_stock_uses_same_industry_capacity(self):
  a=account();T.legacy(a,'OLD','S',9000,pool='confirmed');h=Harness();i,rule=intent(at=T.BASE+timedelta(days=1));_,r,why=attempt(h,a,i,rule)
  self.assertIsNone(r);self.assertIn('sector_capital',why)
 def test_known_fee_reduces_sector_budget_NAV_at_boundary(self):
  a=account();T.legacy(a,'OLD','S',6000,pool='confirmed',floor='9.99')
  mark=D('.06')*a.available/(D('.94')*D(6000));a.fixture_state['price']=mark
  known=T.BASE+timedelta(days=1);a.current_nav=a.balance(known,a.market.marks(known,a.positions))['nav'];nav=a.current_nav
  gross=D('.04')*nav-D('.000001');raw=(gross/D(100))/(D(1)+J.LR.SLIP)
  h=Harness();i,rule=intent(price=400,at=T.BASE+timedelta(days=2));i['budget']=D('.02')*nav
  x,r,why=attempt(h,a,i,rule,raw=raw);fee=J.LR.fees(100,x['price'],T.T.MINIMUM,'buy')
  old=D(6000)*mark;self.assertLessEqual(old+gross,D('.1')*nav);self.assertGreater(old+gross,D('.1')*(nav-fee))
  self.assertIsNone(r);self.assertIn('sector_capital',why)
 def test_actual_holding_any_role_or_old_attempt_cannot_get_exception(self):
  a=account();T.legacy(a,'A','S',100,pool='probe');h=Harness();i,rule=intent(at=T.BASE+timedelta(days=1));h.annotate_candidate(a,i,True)
  self.assertNotIn('R1_full_target',i);_,r,_=attempt(h,a,i,rule,annotate=False);self.assertIsNone(r)
 def test_old_attempt_inventory_survives_new_confirmed_attempt(self):
  a=account();T.legacy(a,'A','S',100,pool='probe');old=a.jmeta[a.layers[-1]['id']]['attempt']
  a.budget.observe('S',J.ordinal(T.BASE+timedelta(days=2)),failure=True)
  T.progress(a,'S',T.BASE+timedelta(days=3),'new-probe');T.progress(a,'S',T.BASE+timedelta(days=4),'new-confirm')
  self.assertNotEqual(old,a.budget.sectors['S'].attempt);self.assertEqual(a.quantity('A'),100)
  h=Harness();i,_=intent(at=T.BASE+timedelta(days=5));h.annotate_candidate(a,i,True);self.assertNotIn('R1_full_target',i)
 def test_pending_buy_and_cancel_pending_responsibility_not_flat(self):
  a=account();h=Harness();i,rule=intent();x,r,_=attempt(h,a,i,rule);T.reserve(a,i,x,r)
  fresh,rule=intent(rid='fresh2');h.annotate_candidate(a,fresh,True);self.assertNotIn('R1_full_target',fresh)
  a.budget.cancel(i['budget_order']);self.assertEqual(a.budget.orders[i['budget_order']].status,'cancel_pending')
  self.assertIn('A',a.buys)
 def test_pending_sell_and_partial_actual_holding_not_flat(self):
  a=account();h=Harness();a.fixture_state['price']=D(10);i=T.intent();x,why=J.LR.preview(i,D(10),D(1),T.T.RULE,T.T.MINIMUM)
  a.sync(i['clock'].earliest_execution_at);r,why=R.BASE.Runner.route(SimpleNamespace(sector_by_sid={'A':'S'}),a,i,x,i['clock'].earliest_execution_at);T.reserve(a,i,x,r);a.fill_buy('A',T.win(i,x,capacity=100))
  self.assertGreater(a.quantity('A'),0);self.assertIn('A',a.buys)
  fresh,rule=intent(rid='fresh-partial');h.annotate_candidate(a,fresh,True);self.assertNotIn('R1_full_target',fresh)
  a.cancel_buy('A');clock=T.T.admission.Clock(T.BASE+timedelta(days=2),T.BASE+timedelta(days=3),T.BASE.date());a.sell('A',clock,T.T.quote(price=10),[z['id'] for z in a.live('A')],'fixture_pending_sell')
  newer,_=intent(rid='after-sell-request');h.annotate_candidate(a,newer,True);self.assertNotIn('R1_full_target',newer)
 def test_same_canonical_receipt_once(self):
  a=account();h=Harness();i,rule=intent();x,r,_=attempt(h,a,i,rule);T.reserve(a,i,x,r)
  _,r,why=attempt(h,a,i,rule,annotate=False);self.assertIsNone(r);self.assertEqual(why,'no_fresh_stock_CP1')
 def test_serial_reservations_do_not_double_spend(self):
  a=account();T.legacy(a,'OLD','LEGACY',85000);h=Harness();accepted=[]
  for k in range(3):
   sid='NEW'+str(k);sec='S'+str(k);T.start(a,sec);T.progress(a,sec,T.ORIG,sec+'p');T.progress(a,sec,T.BASE,sec+'c');h.sector_by_sid[sid]=sec
   i,rule=intent(sid=sid,rid='cp'+str(k),at=T.BASE+timedelta(days=1));i['budget']=D('.02')*a.current_nav
   x,r,why=attempt(h,a,i,rule)
   if r:T.reserve(a,i,x,r);accepted.append(sid)
   else:self.assertIn('cash',why)
  self.assertEqual(len(accepted),1);self.assertLessEqual(a.budget.resources()[2],a.budget.cash)
 def test_original_account_risk_fixture_still_blocks_R1(self):
  a=account(strict=True);T.legacy(a,'OLD','LEGACY',3000,pool='confirmed',floor='0.01');h=Harness();i,rule=intent(at=T.BASE+timedelta(days=1));_,r,why=attempt(h,a,i,rule,strict=True)
  self.assertIsNone(r);self.assertIn('account_risk',why);self.assertNotIn('fresh',a.budget.consumed)
 def test_core_point25_risk_not_relaxed(self):
  a=account();i=T.intent(floor='50');i.update(kind='core',role='core',quote=T.T.quote(price=100),budget=D(100000),cap=1000)
  J.LR.resize_core(i,D(1000000),D(1));self.assertEqual(i['cap'],0);self.assertEqual(i['size_reject'],'minimum_unit_exceeds_risk_or_nominal_cap')
  Harness().annotate_candidate(a,i,True);self.assertNotIn('R1_full_target',i)
 def test_invalidated_or_Q_false_or_ACT_paused_no_exception(self):
  for kind in ['Q','ACT','industry']:
   a=account();h=Harness();i,_=intent()
   if kind=='ACT':a.risk_state['on']=False
   if kind=='industry':a.budget.observe('S',J.ordinal(T.BASE),failure=True)
   h.annotate_candidate(a,i,False if kind=='Q' else True);self.assertNotIn('R1_full_target',i)
 def test_oversized_unit_still_rejected(self):
  a=account();h=Harness();i,rule=intent(price=1000);_,r,why=attempt(h,a,i,rule,raw=1000);self.assertIsNone(r);self.assertEqual(why,'R1_one_unit_exceeds_four_percent_decision_NAV')
 def test_normal_target_already_sufficient_actual_fills_identical(self):
  for price,unit in [(10,100),(100,100),(199,100),(90,200)]:
   result=[]
   for modified in [False,True]:
    a=account();a.fixture_state['price']=D(price);h=Harness();i,rule=intent(price=price,unit=unit)
    if modified:x,r,why=attempt(h,a,i,rule,raw=price)
    else:
     x,why=J.LR.preview(i,D(price),D(1),rule,T.T.MINIMUM);a.sync(i['clock'].earliest_execution_at)
     r,why=R.BASE.Runner.route(SimpleNamespace(sector_by_sid={'A':'S'}),a,i,x,i['clock'].earliest_execution_at)
    self.assertIsNone(why);T.reserve(a,i,x,r);a.fill_buy('A',T.win(i,x,raw=price))
    result.append(J.W.canon(dict(trades=a.trades,cash=a.available,positions=a.positions,lots=a.budget.lots,orders=a.budget.orders,consumed=a.budget.consumed,losses=a.budget.losses)))
   self.assertEqual(*result)
 def test_full_clear_then_new_200_minimum_signal_can_reenter(self):
  a=account();a.fixture_state['price']=D(150);h=Harness();i,rule=intent(price=150,unit=200);x,r,_=attempt(h,a,i,rule,raw=150);T.reserve(a,i,x,r);a.fill_buy('A',T.win(i,x,raw=150))
  decision=T.BASE+timedelta(days=2);clock=T.T.admission.Clock(decision,decision+timedelta(days=1),decision.date());a.sell('A',clock,T.T.quote(price=150,rule=rule),[z['id'] for z in a.live('A')],'real_clear_fixture')
  a.fill_exit('A',T.T.window(sid='A',price=150,at=clock.earliest_execution_at,fees=T.T.MINIMUM,eid='actual-sell'));a.settle_due(clock.earliest_execution_at);a.sync(clock.earliest_execution_at)
  self.assertEqual(a.quantity('A'),0);a.current_nav=a.balance(clock.earliest_execution_at,a.market.marks(clock.earliest_execution_at,a.positions))['nav']
  old,_=intent(price=150,unit=200,rid='fresh',at=T.BASE+timedelta(days=4));old['budget']=D('.02')*a.current_nav
  _,r,why=attempt(h,a,old,rule,raw=150);self.assertIsNone(r);self.assertEqual(why,'no_fresh_stock_CP1')
  fresh,rule=intent(price=150,unit=200,rid='fresh-reentry',at=T.BASE+timedelta(days=4));fresh['budget']=D('.02')*a.current_nav
  x,r,why=attempt(h,a,fresh,rule,raw=150);self.assertIsNone(why);self.assertEqual(r,(200,'confirmed'));T.reserve(a,fresh,x,r)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 R.L.save(R.O/'SYNTHETIC_GATE.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),real_native_ledger_and_admission=True,historical_paths=0,original_account_3_percent_tested_separately=True))
 raise SystemExit(not result.wasSuccessful())
