"""D1 lifecycle specification plus native-ledger probes, not a history runner."""
from pathlib import Path
import sys,json,copy,hashlib,unittest
from dataclasses import replace
from types import SimpleNamespace
from lifecycle import Book
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'execution-pressure-preflight-20261031'))
import check_contract as P
T=P.T;J=P.J;D=J.D;DETAIL=[]

def fresh(role='mobile_first'):
 b=Book();return b,b.place('A',role,'canonical-original',7,200)
def event(o,d,eid=None,eligible=True):return o.window(d,eligible=eligible,event_id=eid or 'window-'+str(d))

class Tests(unittest.TestCase):
 def test_all_four_roles_keep_same_order_receipt_one_wait(self):
  for role in ('core','mobile_first','mobile_add','mobile_reentry'):
   b,o=fresh(role);identity=(o.order_id,o.authorization,o.remaining)
   self.assertEqual(event(o,7),'deliberately_skipped')
   self.assertEqual(o.close(7),'retain_same_order_and_resources')
   self.assertEqual(event(o,8),'attempt_original_order');o.fill(8,200)
   self.assertEqual((o.order_id,o.authorization,200),identity);self.assertEqual(o.terminal,'filled')
   self.assertEqual(b.consumed,{'canonical-original'})
 def test_no_first_eligible_window_keeps_original_expiry(self):
  _,o=fresh();self.assertEqual(event(o,7,eligible=False),'no_eligible_window')
  self.assertEqual(o.close(7),'cancel_pending:lease_expired');self.assertIsNone(o.retry_session)
 def test_unavailable_next_session_is_not_indefinite_GTC(self):
  _,o=fresh();event(o,7);o.close(7)
  self.assertEqual(event(o,8,eligible=False),'no_eligible_window')
  self.assertEqual(o.close(8),'cancel_pending:lease_expired')
  self.assertEqual(event(o,9),'terminal')
 def test_same_session_or_duplicate_window_cannot_bypass_wait(self):
  _,o=fresh();event(o,7,'first')
  self.assertEqual(event(o,7,'first'),'duplicate_window')
  self.assertEqual(event(o,7,'different'),'not_before_next_market_session')
  self.assertEqual(event(o,8,'retry'),'attempt_original_order')
  self.assertEqual(event(o,8,'retry'),'duplicate_window')
 def test_ACT_structure_attempt_protection_and_original_cancel_priority(self):
  for why in ('ACT_pause','industry_attempt_changed','stock_E0_ended','protection_failed','required_input_unknown','original_probe_upgrade_cancel'):
   _,o=fresh();event(o,7)
   self.assertEqual(o.close(7,invalid_reason=why),'cancel_pending:'+why)
   self.assertEqual(event(o,8),'terminal')
 def test_no_token_transfer_reissue_or_release_before_cancel_ack(self):
  b,o=fresh();event(o,7)
  self.assertEqual(b.place('A','mobile_add','new-fresh',7,200),'buy_pending')
  o.close(7,invalid_reason='attempt_ended')
  self.assertEqual(b.place('A','mobile_reentry','new-fresh',8,200),'buy_pending')
  o.cancel_ack()
  self.assertEqual(b.place('A','mobile_reentry','canonical-original',8,200),'already_consumed')
  new=b.place('A','mobile_reentry','new-fresh',8,200)
  self.assertEqual(event(new,8),'deliberately_skipped');self.assertEqual(new.retry_session,9)
 def test_partial_fill_has_no_new_wait_and_deadline_cancels_remainder(self):
  _,o=fresh();event(o,7);o.close(7);event(o,8);o.fill(8,75)
  self.assertEqual(o.remaining,125);self.assertEqual(o.first_wait_session,7)
  self.assertEqual(o.close(8),'cancel_pending:lease_expired');o.cancel_ack();self.assertEqual(o.remaining,0)
 def test_quantity_cannot_increase_without_explicit_corporate_action_contract(self):
  _,o=fresh();event(o,7);o.close(7);event(o,8)
  with self.assertRaises(AssertionError):o.fill(8,201)
 def test_append_future_does_not_change_past_lifecycle(self):
  _,o=fresh();event(o,7);o.close(7);past=copy.deepcopy(o.audit)
  cut=copy.deepcopy(o);event(o,8);o.fill(8,100);o.close(8)
  self.assertEqual(o.audit[:len(past)],past);self.assertEqual(cut.audit,past)
 def test_native_core_and_mobile_same_price_retention_can_fill_once(self):
  for kind in ('core','add'):
   a=P.account(1);T.progress(a,'S',T.BASE,'confirm')
   i,x,order,before,f=P.attempt(a,P.next_cutoff(T.BASE),'D1-'+kind,kind=kind)
   self.assertIsNone(f);self.assertEqual(before,1);self.assertEqual(order.delay_remaining,0)
   close=P.next_cutoff(i['clock'].earliest_execution_at);retry=P.next_open(close)
   before_cash=a.available;before_reserve=a.budget.resources()[2];oid=order.order_id
   # Explicit proposed lease retention, not a call to existing day-expiry.
   a.sync(close);a.budget.orders[i['budget_order']].expiry_bar=J.ordinal(retry.date())
   self.assertEqual(a.available,before_cash);self.assertEqual(a.budget.resources()[2],before_reserve)
   f=a.fill_buy('A',T.win(i,x,at=retry,eid='D1-retry-'+kind));self.assertIsNotNone(f)
   self.assertEqual(a.order_bridge[oid],i['budget_order']);self.assertEqual(order.delay_remaining,0)
   self.assertEqual(D(T.journal_bridge(a,retry)['independent_NAV_difference']),0)
   DETAIL.append(dict(case='native same-price carry probe',role=kind,first_window=str(i['clock'].earliest_execution_at),retry=str(retry),same_native_order=oid,fill=f.shares,manual_retention_fixture_not_integrated_runner=True))
 def test_native_unamended_upgap_exposes_real_adapter_conflict(self):
  a=P.account(1);T.progress(a,'S',T.BASE,'confirm')
  i,x,order,_,f=P.attempt(a,P.next_cutoff(T.BASE),'gap-original')
  retry=P.next_open(P.next_cutoff(i['clock'].earliest_execution_at))
  limit=a.budget.orders[i['budget_order']].limit
  with self.assertRaises(AssertionError):a.fill_buy('A',T.win(i,x,at=retry,price=D(11),raw=11,eid='gap-retry'))
  self.assertGreater(a.quantity('A'),0)  # Native fill happened before old callback's price assertion.
  DETAIL.append(dict(case='unamended gap retry counterexample',old_authorized_unit_price=limit,new_price=11,native_quantity_mutated_before_callback_rejection=a.quantity('A'),integration_gate_passed=False,isolated_fixture_discarded=True))
 def test_native_sell_delay_remains_latched_after_unavailable_tplus1(self):
  a=P.account();T.legacy(a,'A','S',100,pool='confirmed');a.delay_events=1
  decision=P.next_cutoff(T.BASE+P.timedelta(days=1));first=P.next_open(decision)
  clock=T.T.admission.Clock(decision,first,decision.date())
  a.sell('A',clock,T.T.quote(price=10),[x['id'] for x in a.live('A')],'D1_fixture_exit')
  cash=a.available;self.assertIsNone(a.fill_exit('A',T.T.window(sid='A',price=10,at=first,fees=T.T.MINIMUM,eid='sell-t')))
  second=P.next_open(P.next_cutoff(first));third=P.next_open(P.next_cutoff(second))
  self.assertIsNone(a.fill_exit('A',replace(T.T.window(sid='A',price=10,at=second,fees=T.T.MINIMUM,eid='sell-t1'),market_open=False)))
  self.assertEqual(a.quantity('A'),100);self.assertEqual(a.available,cash);self.assertEqual(a.exits['A'].delay_remaining,0)
  f=a.fill_exit('A',T.T.window(sid='A',price=10,at=third,fees=T.T.MINIMUM,eid='sell-t2',cash_due_at=third));self.assertIsNotNone(f)
  a.settle_due(third);a.sync(third);self.assertEqual(a.quantity('A'),0);self.assertGreater(a.available,cash)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 payload=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),specification_checks_passed=result.wasSuccessful(),historical_paths=0,D1_real_runner_gate_passed=False,reason='lifecycle proposal only; requires real expiry/retry/reprice integration and review; native upgap conflict reproduced',details=DETAIL,sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (O/'CONTRACT.txt',O/'lifecycle.py',Path(__file__))})
 P.IO.write_json(O/'SYNTHETIC_RESULTS.json',payload)
 raise SystemExit(not result.wasSuccessful())
