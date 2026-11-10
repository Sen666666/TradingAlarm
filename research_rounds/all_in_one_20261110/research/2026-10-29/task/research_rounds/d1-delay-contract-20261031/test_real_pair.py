"""Actual D1 Pair opening/revalidation and original native ledger; no history."""
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
import json,unittest,copy,tempfile,hashlib
import d1_runner as E
P=E.R.P;T=P.T;J=E.J;D=J.D;IO=P.IO;DETAIL=[]
def setup(role='mobile',ref='B3',enabled=True,late=False):
 cls=E.B3D1 if ref=='B3' else E.DiagD1;r=cls.__new__(cls);a=T.account();a.__class__=E.Account
 a.configure_d1(enabled,P.OPENS);a.d1_account_cap=ref=='B3'
 a.risk_state={'on':True}  # Explicit predecision ACT fixture, not a replacement ACT engine.
 if ref=='B_diag':E.BASE.enable(a)
 T.progress(a,'S',T.BASE,'confirm');decision=P.next_cutoff(T.BASE+P.timedelta(days=4) if late else T.BASE);first=P.next_open(decision);close=P.next_cutoff(first);second=P.next_open(close)
 a.facts.structure_lookup={'A':{decision.date():'stock-E',close.date():'stock-E',second.date():'stock-E'}}
 a.facts.row=lambda sid,at:SimpleNamespace(i_target=True,close=a.fixture_state['price'])
 prices={first:D(10),second:D(11)};capacity={};unavailable=set()
 a.market.raw={'A':J.pd.DataFrame({'open':[10.,11.]},index=J.pd.DatetimeIndex([str(first.date()),str(second.date())]))}
 a.market.quantity=lambda *args:T.T.RULE;a.market.fees=lambda *args:T.T.MINIMUM
 def window(sid,at,side,cost):
  if at in unavailable:return None
  raw=prices.get(at,D(10));price=raw*(D('1.0005') if side=='buy' else D('.9995'))
  return T.T.window(sid=sid,at=at,price=price,raw_open=raw,fees=T.T.MINIMUM,eid=side+str(at),capacity=capacity.get(at,10000000),cash_due_at=at)
 a.market.window=window
 r.accounts={'B':a};r.market=a.market;r.facts=a.facts;r.sector_by_sid={'A':'S'};r.d1_enabled=enabled;r.source_freeze={}
 for n in ('daily','opportunities','funding','stage_events','balance_audit'):setattr(r,n,[])
 i=T.intent(at=decision,rid='fresh-original');i['clock']=replace(i['clock'],earliest_execution_at=first)
 if role=='core':
  i.update(kind='core',role='core',CP1_id=None,CP1_trace=None,budget=D(100000),cap=10000)
  J.LR.resize_core(i,a.current_nav,D(1))
 a.pending=[i]
 return r,a,i,first,close,second,prices,capacity,unavailable
def closing(r,a,at):
 a.expire_day_buys(at);r.revalidate_carried_buys(a,at,{'A':SimpleNamespace(q=True)});a.pending=[];a.sync(at)

class Tests(unittest.TestCase):
 def test_real_pair_core_and_mobile_upgap_amend_before_fill_and_single_receipt(self):
  for role in ('core','mobile'):
   r,a,i,t,c,t1,prices,cap,unavailable=setup(role)
   r.opening(a,t);o=a.buys['A'];oid=o.order_id;q=o.remaining_shares;principal=o.remaining_budget_cny;consumed=set(a.budget.consumed)
   self.assertEqual(a.quantity('A'),0);self.assertEqual(o.delay_remaining,0)
   reserve=a.budget.resources()[2];closing(r,a,c);self.assertEqual(a.budget.resources()[2],reserve)
   a.fixture_state['price']=D(11);r.opening(a,t1)
   self.assertGreater(a.quantity('A'),0);self.assertLessEqual(a.quantity('A'),q);self.assertEqual(a.budget.consumed,consumed)
   amendment=next(x for x in a.d1_audit if x['kind']=='D1_same_order_amend')
   self.assertEqual(amendment['order'],oid);self.assertLessEqual(amendment['new_principal'],principal)
   if role=='core':self.assertLessEqual(a.d1_orders[oid]['core_used_risk'],i['risk_budget'])
   self.assertEqual(D(T.journal_bridge(a,t1)['independent_NAV_difference']),0)
   DETAIL.append(dict(case='real Pair up-gap',role=role,old_shares=q,new_shares=a.quantity('A'),old_principal=principal,new_principal=amendment['new_principal'],same_order=oid))
 def test_guard_rejects_unamended_retry_before_native_inventory_mutation(self):
  r,a,i,t,c,t1,*_=setup();r.opening(a,t);closing(r,a,c)
  with self.assertRaisesRegex(AssertionError,'amend before'):a.fill_buy('A',a.market.window('A',t1,'buy',1))
  self.assertEqual(a.quantity('A'),0)
 def test_core_amend_uses_original_buy_and_exit_fee_slippage_risk_formula(self):
  r,a,i,t,c,t1,prices,*_=setup(role='core');i['floor']=D('8.5');J.LR.resize_core(i,a.current_nav,D(1))
  r.opening(a,t);closing(r,a,c);raw=D('10.985');prices[t1]=raw;a.fixture_state['price']=raw;a.market.raw['A'].loc[str(t1.date()),'open']=float(raw)
  p=raw*D('1.0005');self.assertGreater(J.LR.protection_risk(1000,p,D('8.5'),T.T.MINIMUM),D(2500))
  r.opening(a,t1);self.assertEqual(a.quantity('A'),900);self.assertLessEqual(next(iter(a.d1_orders.values()))['core_used_risk'],D(2500))
 def test_next_session_no_window_cancels_at_hard_deadline_without_credit(self):
  r,a,i,t,c,t1,prices,cap,unavailable=setup();r.opening(a,t);closing(r,a,c);unavailable.add(t1)
  a.fixture_state['price']=D(11);r.opening(a,t1);self.assertIn('A',a.buys)
  closing(r,a,P.next_cutoff(t1));self.assertNotIn('A',a.buys);self.assertEqual(a.quantity('A'),0)
  self.assertFalse(a.daily_delay_credit);self.assertFalse(a.add_credits);self.assertEqual(a.budget.resources()[2],0)
 def test_no_first_window_original_expiry_no_extension(self):
  r,a,i,t,c,t1,prices,cap,unavailable=setup();unavailable.add(t);r.opening(a,t)
  self.assertIsNone(next(iter(a.d1_orders.values()))['first_wait']);closing(r,a,c);self.assertNotIn('A',a.buys)
 def test_partial_next_day_fill_cancel_remainder_preserves_actual_shares(self):
  r,a,i,t,c,t1,prices,cap,unavailable=setup();r.opening(a,t);closing(r,a,c);cap[t1]=50
  a.fixture_state['price']=D(11);r.opening(a,t1);self.assertEqual(a.quantity('A'),50);self.assertIn('A',a.buys)
  closing(r,a,P.next_cutoff(t1));self.assertNotIn('A',a.buys);self.assertEqual(a.quantity('A'),50)
  self.assertEqual(a.budget.resources()[2],0);self.assertEqual(D(T.journal_bridge(a,P.next_cutoff(t1))['independent_NAV_difference']),0)
 def test_invalid_attempt_ACT_stock_protection_and_unknown_cancel(self):
  for why in ('attempt','ACT','stock','floor','unknown'):
   r,a,i,t,c,t1,*_=setup();r.opening(a,t)
   if why=='attempt':a.budget.sectors['S'].active=False
   if why=='ACT':a.risk_state['on']=False
   if why=='stock':a.facts.row=lambda *args:SimpleNamespace(i_target=False,close=D(10))
   if why=='floor':a.fixture_state['price']=D(9)
   if why=='unknown':a.facts.structure_lookup={}
   closing(r,a,c);self.assertNotIn('A',a.buys);self.assertEqual(a.quantity('A'),0)
 def test_pending_new_CP1_does_not_topup_or_extend_and_same_receipt_cannot_reissue(self):
  r,a,i,t,c,t1,*_=setup();r.opening(a,t);oid=a.buys['A'].order_id;deadline=a.d1_orders[oid]['expiry_day'];closing(r,a,c)
  new=T.intent(at=c,rid='other-current');new['clock']=replace(new['clock'],earliest_execution_at=t1);a.pending=[new]
  a.fixture_state['price']=D(11);r.opening(a,t1)
  self.assertEqual(len([x for x in a.journal if x['kind']=='real_reserve']),1);self.assertNotIn('other-current',a.budget.consumed)
  self.assertEqual(a.d1_orders[oid]['expiry_day'],deadline);self.assertIn('fresh-original',a.budget.consumed)
 def test_original_probe_upgrade_cancel_is_not_bypassed(self):
  r,a,i,t,c,t1,*_=setup();r.opening(a,t);T.progress(a,'S',c,'next-stage')
  bo=a.budget.orders[a.order_bridge[a.buys['A'].order_id]];self.assertEqual(bo.status,'cancel_pending')
  a.cancel_buy('A');a.sync(c);self.assertEqual(a.budget.resources()[2],0);self.assertEqual(a.quantity('A'),0)
 def test_price_below_frozen_line_cancels_without_native_fill(self):
  r,a,i,t,c,t1,prices,*_=setup();r.opening(a,t);closing(r,a,c)
  a.market.raw['A'].loc[str(t1.date()),'open']=9.;prices[t1]=D(9);a.fixture_state['price']=D(9)
  r.opening(a,t1);self.assertNotIn('A',a.buys);self.assertEqual(a.quantity('A'),0)
 def test_B3_risk_cap_not_removed_by_amend_and_diag_has_only_original_omission(self):
  for ref in ('B3','B_diag'):
   r,a,i,t,c,t1,*_=setup(ref=ref,late=True)
   a.d1_enabled=False;a.delay_events=0;T.legacy(a,'OLD','X',2900,pool='confirmed',floor='0');a.d1_enabled=True;a.delay_events=1
   r.opening(a,t);closing(r,a,c);a.fixture_state['price']=D(11);r.opening(a,t1)
   self.assertEqual(a.d1_account_cap,ref=='B3')
   self.assertIs(r.route.__func__,J.Runner.route if ref=='B3' else E.BASE.Runner.route)
   self.assertEqual(a.quantity('A')>0,ref=='B_diag')
   if ref=='B3':self.assertTrue(any('account_risk' in x.get('reason','') for x in a.d1_audit))
 def test_amendment_assertion_failure_rolls_back_without_any_native_fill(self):
  r,a,i,t,c,t1,*_=setup();r.opening(a,t);closing(r,a,c);o=a.buys['A'];bo=a.budget.orders[a.order_bridge[o.order_id]]
  old=(copy.deepcopy(o.__dict__),copy.deepcopy(bo.__dict__),a.available);original=a.sync;calls=[0]
  def inject(at,*args,**kw):
   calls[0]+=1
   if calls[0]==2:raise AssertionError('injected post-amend representation failure')
   return original(at,*args,**kw)
  a.sync=inject;a.fixture_state['price']=D(11)
  with self.assertRaisesRegex(AssertionError,'injected post-amend'):r.opening(a,t1)
  self.assertEqual((o.__dict__,bo.__dict__,a.available),old);self.assertEqual(a.quantity('A'),0)
 def test_pending_split_then_retry_keeps_units_quantity_and_cash_consistent(self):
  r,a,i,t,c,t1,prices,*_=setup();r.opening(a,t);o=a.buys['A'];oldq=o.remaining_shares;principal=o.remaining_budget_cny;closing(r,a,c)
  a.split(event_id='D1-pending-split',sid='A',ratio=D(2),at=t1-P.timedelta(hours=1),new_shares_sellable_at=t1)
  a.fixture_state.update(price=D('5.5'),factor=D(2));prices[t1]=D('5.5');a.market.raw['A'].loc[str(t1.date()),'open']=5.5
  a.sync(t1-P.timedelta(minutes=30));self.assertEqual(o.remaining_shares,oldq*2);self.assertEqual(o.remaining_budget_cny,principal)
  r.opening(a,t1);self.assertGreater(a.quantity('A'),0);self.assertLessEqual(a.quantity('A'),oldq*2)
  self.assertEqual(D(T.journal_bridge(a,t1)['independent_NAV_difference']),0)
 def test_real_pair_sell_delay_no_early_cash_or_risk_release_and_latched(self):
  r,a,i,t,c,t1,prices,cap,unavailable=setup();r.opening(a,t);closing(r,a,c);a.fixture_state['price']=D(11);r.opening(a,t1)
  decision=P.next_cutoff(t1);first=P.next_open(decision);second=P.next_open(P.next_cutoff(first));third=P.next_open(P.next_cutoff(second))
  a.pending=[];a.sell('A',T.T.admission.Clock(decision,first,decision.date()),T.T.quote(price=11),[x['id'] for x in a.live('A')],'D1_real_pair_exit')
  cash=a.available;qty=a.quantity('A');risk=a.budget.resources()[1];r.opening(a,first)
  self.assertEqual(a.available,cash);self.assertEqual(a.quantity('A'),qty);self.assertEqual(a.budget.resources()[1],risk)
  unavailable.add(second);r.opening(a,second);self.assertIn('A',a.exits);self.assertEqual(a.available,cash)
  cap[third]=50;r.opening(a,third);self.assertEqual(a.quantity('A'),qty-50);self.assertEqual(a.exits['A'].delay_remaining,0)
  fourth=P.next_open(P.next_cutoff(third));r.opening(a,fourth)
  self.assertEqual(a.quantity('A'),0);self.assertNotIn('A',a.exits);self.assertGreater(a.available,cash)
  self.assertEqual(D(T.journal_bridge(a,fourth)['independent_NAV_difference']),0)
 def test_checkpoint_restores_actual_D1_Pair_and_wrong_configuration_rejected(self):
  r,a,i,t,c,t1,*_=setup();r.opening(a,t);closing(r,a,c);root=Path(tempfile.mkdtemp(prefix='D1-real-pair-',dir='/tmp'))
  with IO.atomic_runner_outputs(r,E.L,root,canonicalize=J.W.canon):r.checkpoint(root,c)
  other,*_=setup();
  with IO.atomic_runner_outputs(other,E.L,root,canonicalize=J.W.canon):self.assertEqual(other.restore(root/'checkpoint.pkl'),c)
  self.assertEqual(other.accounts['B'].d1_orders,a.d1_orders)
  wrong,*_=setup(enabled=False)
  with self.assertRaisesRegex(AssertionError,'configuration changed'):
   with IO.atomic_runner_outputs(wrong,E.L,root,canonicalize=J.W.canon):wrong.restore(root/'checkpoint.pkl')

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 IO.write_json(E.O/'REAL_PAIR_GATE.json',J.W.canon(dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),details=DETAIL,historical_paths=0,source_sha256=hashlib.sha256(Path(E.__file__).read_bytes()).hexdigest())))
 raise SystemExit(not result.wasSuccessful())
