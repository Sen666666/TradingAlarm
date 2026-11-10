import adapter as m
from types import SimpleNamespace
from datetime import timedelta
from dataclasses import replace
import pandas as pd
O=m.O;w=m.w;D=m.D;T=w.load('act_abc_real_ledger_fixture',w.RR/'rs-h1-execution-20261025/code/test_sector_account.py');A=w.K.A;L=w.K.L
root=O/'synthetic';root.mkdir(exist_ok=False);(root/'execution-rules-v2.json').write_bytes((w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json').read_bytes());R,E,_,_,_=m.setup('TECH',root,True);t0=T.T;res=[]
def clock(t):return A.Clock(t,t+timedelta(days=1),t.date())
def mk(policy='C',held=True,partial=False):
 a=R.Account(initial_cash=1000000);a.act_policy=policy;a.loss_b=None;a.mode='I';a.facts=SimpleNamespace(floor=lambda *_:D(1),factor=lambda *_:D(1),row=lambda *_:SimpleNamespace(e0_target=True));a.risk_state=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0)
 if held:
  assert a.reserve_budget(quote=T.quote(fees=T.MINIMUM),clock=clock(t0),gross_budget_cny=D(900000))[0];op=clock(t0).earliest_execution_at;a.fill_buy('A',T.window(at=op,fees=T.MINIMUM,capacity=10000 if partial else 10**8,cash_due_at=op,eid='start'));a.settle_due(op)
 return a
def state(a,t,price=10,br=True):
 a.current_nav=a.balance(t,T.marks(t,price=price))['nav'];rec=pd.DataFrame({'fast_on':[True],'breakout':[br]},index=[pd.Timestamp(t.date())]);m.controlled_step(a,t,'ACT20_BREAK',rec)
def stocks(t,fresh=True,up=True):
 f=lambda v:A.Fact(v,t,t,observed_at=t);return (A.Security('A',f('A'),f('G'),f(True),f(fresh),f(20e9),f(up),A.Rank(80,t,t)),),(A.Sector('G',f(True),A.Rank(70,t,t)),)
def commit(a,t,fresh=True,up=True,previous=()):
 ss,gg=stocks(t,fresh,up);ss=m.controlled_override(a,ss,clock(t),'ACT20_BREAK',A.Fact) if a.act_policy in ['B','C'] else ss
 factory=lambda **kw:A.decide(clock=clock(t),variant='S0',securities=ss,sectors=gg,**kw)
 return L.commit_cutoff(a,decision_factory=factory,clock=clock(t),quotes={'A':T.quote(fees=T.MINIMUM)},marks=T.marks(t),previous=previous,bootstrap=not previous)
def run(name,fn):fn();res.append(dict(name=name,passed=True));print(name,'PASS',flush=True)
def source_semantics():
 s=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0);z,dd,e=m.ORIGINAL_ADVANCE(s,D(750000),True,True,True,'ACT20_BREAK');assert not z['on'] and e=='pause';q,_,e=m.ORIGINAL_ADVANCE(z,D(750000),True,True,True,'ACT20_BREAK');assert q['on'] and e=='resume' and q['peak']==750000
run('original_A_if_else_single_transition_no_same_call_resume',source_semantics)
def nested():
 t=t0+timedelta(days=2,hours=6)
 for p in ['B','C']:
  a=mk(p);a.risk_state['on']=False;state(a,t,price=9);assert a.risk_state['on']==(p=='C');assert a.quantity('A')>0 and not a.buys and not a.exits
run('same_real_nonempty_no_order_market_B_waits_flat_C_resumes',nested)
def dd_and_market():
 a=mk();t=t0+timedelta(days=2,hours=6);state(a,t,price=7.7,br=True);assert not a.risk_state['on'];assert [x['event'] for x in a.audit_log if x['kind']=='act_checkpoint']==['pause'];commit(a,t);assert not a.exits and a.quantity('A')>0
run('drawdown_and_breakout_same_cutoff_pause_only_keeps_native_structure',dd_and_market)
def reset_and_repause():
 a=mk();a.risk_state['on']=False;t=t0+timedelta(days=2,hours=6);state(a,t,price=7.7);N=a.current_nav;assert a.risk_state['on'] and a.risk_state['peak']==N;state(a,t+timedelta(days=1),price=7.7);assert a.risk_state['on'];state(a,t+timedelta(days=2),price=5.5);assert not a.risk_state['on'] and a.risk_state['episode']==1
run('nonempty_resume_resets_own_NAV_no_immediate_repause_next_phase_can_pause',reset_and_repause)
def pending_sell():
 a=mk();t=t0+timedelta(days=2,hours=6);a.request_exit(T.quote(fees=T.MINIMUM),clock(t));a.risk_state['on']=False;state(a,t+timedelta(hours=1));assert not a.risk_state['on'];eid=a.exits['A'].event_id;commit(a,t+timedelta(hours=1));assert a.exits['A'].event_id==eid
run('pending_sell_blocks_resume_and_locked_sale_survives',pending_sell)
def missing_market():
 a=mk();a.risk_state['on']=False;t=t0+timedelta(days=2,hours=6);state(a,t,price=12,br=False);assert not a.risk_state['on'] and a.audit_log[-1]['waiting_primary']=='market'
run('no_market_breakout_no_NAV_self_recovery',missing_market)
def structure_first():
 a=mk();a.risk_state['on']=False;a.act_last_event=None;t=t0+timedelta(days=2,hours=6);commit(a,t,up=False);assert 'A' in a.exits and a.quantity('A')>0
run('original_structure_exit_still_requests_and_no_fake_flat',structure_first)
def partial_buy():
 a=mk(partial=True);qty=a.quantity('A');assert qty>0 and a.buys;a.risk_state['on']=False;t=t0+timedelta(days=2,hours=6);state(a,t);assert not a.risk_state['on'] and a.audit_log[-1]['waiting_primary']=='orders';commit(a,t);assert not a.buys and a.quantity('A')==qty and not a.exits;state(a,t+timedelta(days=1));assert a.risk_state['on'] and a.quantity('A')==qty
run('pause_cancels_real_partial_buy_preserves_inventory_then_C_can_resume',partial_buy)
def flat_and_fresh():
 a=mk('B',held=False);a.risk_state['on']=False;t=t0+timedelta(days=2,hours=6);state(a,t);assert a.risk_state['on'];ack=commit(a,t,fresh=False);assert not a.buys;state(a,t+timedelta(days=1));ack=commit(a,t+timedelta(days=1),fresh=True,previous=ack.memories);assert ack.accepted==('A',) and a.buys['A'].purpose=='initial'
run('B_real_flat_resume_opens_only_original_fresh_I_not_auto_buy',flat_and_fresh)
def duplicate():
 a=mk();t=t0+timedelta(days=2,hours=6);state(a,t)
 try:state(a,t)
 except AssertionError:return
 raise AssertionError('duplicate clock allowed')
run('duplicate_decision_clock_is_contract_failure_not_extra_transition',duplicate)
w.K.save(O/'SYNTHETIC.json',dict(passed=True,tests=res,real_original_account_ledger_admission=True,original_A_single_transition_confirmed=True));print('PASS',len(res))
