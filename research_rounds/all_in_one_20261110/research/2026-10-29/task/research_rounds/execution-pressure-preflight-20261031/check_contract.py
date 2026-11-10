"""Actual-ledger pressure semantics only; no historical account replay."""
from pathlib import Path
from datetime import timedelta
from dataclasses import replace
import sys,json,inspect,hashlib,difflib,unittest
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'account-risk-ablation-20261031'))
import adapter as BASE
import test_bridge as T
from initialization_guard import IO
J=BASE.J;D=J.D;DETAIL=[]
RULES=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json').read_text())
OPENS=[J.M.N.iso(x) for x in RULES['calendars']['A']];CUTOFFS=[J.M.N.iso(x) for x in RULES['decision_cutoffs']]
def next_open(at):return next(x for x in OPENS if x>at)
def next_cutoff(at):return next(x for x in CUTOFFS if x>at)
def account(delay=0):
 a=T.account();a.delay_events=delay;return a
def attempt(a,at,rid,kind='add'):
 i=T.intent(at=at,rid=rid)
 i['clock']=replace(i['clock'],earliest_execution_at=next_open(at))
 if kind=='core':
  i.update(kind='core',role='core',CP1_id=None,CP1_trace=None,budget=D(100000),cap=10000)
  J.LR.resize_core(i,a.current_nav,D(1))
 x,r,why=T.routed(a,i);assert why is None,(kind,why)
 T.reserve(a,i,x,r);o=a.buys['A'];before=o.delay_remaining
 f=a.fill_buy('A',T.win(i,x,eid='execution-'+rid));return i,x,o,before,f
class Tests(unittest.TestCase):
 def test_cost2_fees_rates_doubled_minimum_and_stamp_unchanged(self):
  rules=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json').read_text())
  raw=next(x['schedule'] for x in rules['fee_versions']['SSE_MAIN'] if x['from']=='2023-08-28');Component=type(T.T.MINIMUM.components[0]);Schedule=type(T.T.MINIMUM);s=Schedule(raw['schedule_id'],tuple(Component(**x) for x in raw['components']))
  results={}
  for side in ['buy','sell']:
   for mul in [1,2]:results[side+str(mul)]=s.incremental(side,D(1000),{}, {},mul,shares=100,par_value=D(1))
  self.assertEqual(results['buy1']['net_brokerage'],5);self.assertEqual(results['buy2']['net_brokerage'],5)
  for name in ['handling','regulatory','transfer']:self.assertEqual(results['buy2'][name],2*results['buy1'][name])
  self.assertEqual(results['sell1']['stamp_duty'],results['sell2']['stamp_duty']);DETAIL.append(dict(case='actual_fee_schedule',results=results))
 def test_hardcoded_normal_window_would_disagree_with_cost2_preview(self):
  a=account();a.cost_multiplier=2;J.C.activate(a);i=T.intent();x,why=J.LR.preview(i,D(10),D(1),T.T.RULE,T.T.MINIMUM);self.assertIsNone(why)
  self.assertEqual(x['price'],D('10.0100'));self.assertNotEqual(x['price'],D('10.0050'))
  source=inspect.getsource(J.Runner.opening);self.assertIn("self.market.window(sid,at,'buy',1)",source);self.assertIn("self.market.window(sid,at,'sell',1)",source)
  DETAIL.append(dict(case='cost2_window_adapter_required',preview=x['price'],hardcoded_cost1_window=D('10.0050')));a.cost_multiplier=1;J.C.activate(a)
 def test_flat_independent_mobile_wait_expire_fresh_mobile_waits_again(self):
  a=account(1);T.progress(a,'S',T.BASE,'confirm');at=next_cutoff(T.BASE);events=[]
  for k in range(3):
   i,x,o,before,f=attempt(a,at,'fresh-mobile-'+str(k));self.assertIsNone(f);self.assertEqual(before,1);self.assertEqual(o.delay_remaining,0)
   at=next_cutoff(i['clock'].earliest_execution_at);a.expire_day_buys(at);a.sync(at)
   self.assertEqual(a.quantity('A'),0);self.assertIn('A',a.daily_delay_credit);self.assertFalse(a.add_credits)
   events.append(dict(order=o.order_id,before=before,after_wait=o.delay_remaining,expiry=at,flat_initial_credit_created=True,ADD_credit_created=False,fill=False))
  self.assertFalse(a.add_enabled);DETAIL.append(dict(case='independent_flat_mobile_has_no_applicable_credit_consumption',events=events))
 def test_held_independent_mobile_has_neither_initial_nor_ADD_credit(self):
  a=account();T.progress(a,'S',T.BASE,'confirm');T.legacy(a,'A','S',100,pool='confirmed');a.delay_events=1
  at=next_cutoff(T.BASE+timedelta(days=1));i,x,o,before,f=attempt(a,at,'held-mobile');self.assertIsNone(f)
  at=next_cutoff(i['clock'].earliest_execution_at);a.expire_day_buys(at);a.sync(at)
  self.assertEqual(a.quantity('A'),100);self.assertNotIn('A',a.daily_delay_credit);self.assertFalse(a.add_credits)
  _,_,new,before,f=attempt(a,at,'held-mobile-new');self.assertIsNone(f);self.assertEqual(before,1);DETAIL.append(dict(case='held_mobile_not_covered_by_existing_wait_credit',held_shares=100,old_wait_spent=True,new_delay=before))
 def test_core_new_legal_intent_can_use_original_flat_credit(self):
  a=account(1);at=next_cutoff(T.BASE);i,x,o,before,f=attempt(a,at,'core0',kind='core');self.assertIsNone(f)
  at=next_cutoff(i['clock'].earliest_execution_at);a.expire_day_buys(at);a.sync(at)
  _,_,_,before,f=attempt(a,at,'core1',kind='core');self.assertIsNotNone(f);self.assertEqual(before,0);DETAIL.append(dict(case='original_core_credit_positive_control',actual_fill=f.shares))
 def test_sell_wait_latched_then_real_fill_and_cash_release(self):
  a=account();T.legacy(a,'A','S',100,pool='confirmed');a.delay_events=1;decision=next_cutoff(T.BASE+timedelta(days=1))
  clock=T.T.admission.Clock(decision,next_open(decision),decision.date());a.sell('A',clock,T.T.quote(price=10),[z['id'] for z in a.live('A')],'fixture_structure_exit')
  o=a.exits['A'];eid=o.event_id;cash=a.available;at=clock.earliest_execution_at;w=T.T.window(sid='A',price=10,at=at,fees=T.T.MINIMUM,eid='eligible-sell-1')
  self.assertIsNone(a.fill_exit('A',w));self.assertEqual(a.available,cash);self.assertEqual(a.quantity('A'),100);self.assertEqual(o.delay_remaining,0)
  self.assertIsNone(a.fill_exit('A',w));self.assertEqual(o.delay_remaining,0)
  repeated=next_cutoff(at);newclock=T.T.admission.Clock(repeated,next_open(repeated),repeated.date())
  a.sell('A',newclock,T.T.quote(price=10),[z['id'] for z in a.live('A')],'repeated_exit_decision');self.assertEqual(a.exits['A'].event_id,eid)
  nextat=next_open(repeated);f=a.fill_exit('A',T.T.window(sid='A',price=10,at=nextat,fees=T.T.MINIMUM,eid='eligible-sell-2',cash_due_at=nextat));self.assertIsNotNone(f);a.settle_due(nextat);a.sync(nextat)
  self.assertEqual(a.quantity('A'),0);self.assertGreater(a.available,cash);DETAIL.append(dict(case='sell_delay_original_latched_order',first_skipped_at=at,actual_fill_at=nextat,cash_before=cash,cash_after=a.available,repeat_did_not_reset_wait=True))
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 IO.write_json(O/'NATIVE_PROTOCOL_EVIDENCE.json',J.W.canon(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),evidence_tests_passed=r.wasSuccessful(),pressure_economic_gate_passed=False,blocker='independent mobile waiting-credit semantics are not covered by frozen core or held-core ADD implementations',details=DETAIL,historical_runs=0)))
 source=inspect.getsource(J.Runner.opening);fixed=source.replace("self.market.window(sid,at,'sell',1)","self.market.window(sid,at,'sell',a.cost_multiplier)").replace("self.market.window(sid,at,'buy',1)","self.market.window(sid,at,'buy',a.cost_multiplier)")
 IO.write_bytes(O/'COST_WINDOW_ADAPTER_PROPOSED.patch',''.join(difflib.unified_diff(source.splitlines(True),fixed.splitlines(True),fromfile='frozen_normal_opening',tofile='existing_cost_multiplier_window_adapter')).encode())
 raise SystemExit(not r.wasSuccessful())
