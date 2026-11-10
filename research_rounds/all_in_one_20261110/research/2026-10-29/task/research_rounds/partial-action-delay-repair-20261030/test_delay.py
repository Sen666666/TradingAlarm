import delay_patch as P
from pathlib import Path
from datetime import timedelta
from types import SimpleNamespace
from dataclasses import replace
import json,time,traceback
I=P.I;M=I.M;D=M.D;A=M.A;T=M.load('restore_delay_test_original',M.RR/'rs-h1-execution-20261025/code/test_sector_account.py');O=Path(__file__).resolve().parent
old=P.BASE_FACTORY(M.Parent,None);new=P.factory(M.Parent,None);results=[]
def clock(at):return A.Clock(at,at+timedelta(days=1),at.date())
def q():return T.quote(fees=T.MINIMUM)
def w(at,capacity=100000):return T.window(at=at,capacity=capacity,fees=T.MINIMUM,cash_due_at=at,eid='window|'+at.isoformat())
def start(cls=new,delay=1,enabled=True,cost=1):
 a=cls(initial_cash=40000,delay_events=delay,cost_multiplier=cost);a.roles_enabled=enabled;a.facts=SimpleNamespace(floor=lambda *_:D(8),factor=lambda *_:D(1));a.reserve_budget(quote=q(),clock=clock(T.T),gross_budget_cny=4000);op=T.T+timedelta(days=1)
 if delay:
  assert a.fill_buy('A',w(op)) is None;cl=op+timedelta(hours=6);a.expire_day_buys(cl);a.reserve_budget(quote=q(),clock=clock(cl),gross_budget_cny=4000);op=clock(cl).earliest_execution_at
 assert a.fill_buy('A',w(op)).shares==400;a.settle_due(op);return a,op

def trim(a,entry):
 warn=entry+timedelta(hours=6);a.close_risk('A',clock(warn),q(),10,negative_id='negative|'+warn.isoformat());cross=warn+timedelta(days=1);a.expire_day_buys(cross);a.close_risk('A',clock(cross),q(),9.5)
 op=clock(cross).earliest_execution_at
 if a.delay_events:assert a.fill_exit('A',w(op)) is None;op+=timedelta(days=1)
 assert a.fill_exit('A',w(op)).shares==200;a.settle_due(op);assert a.roles['A']['R']==0;return op

def commit(a,at,event='fresh',Q=True,known_at=None):
 f=lambda v:A.Fact(v,at,at,source_id='synthetic-known',observed_at=at);ss=(A.Security('A',f('A'),f('G'),f(True),f(Q),f(20e9),f(True),A.Rank(90,at,at)),);gs=(A.Sector('G',f(True),A.Rank(90,at,at)),);marks=T.marks(at);a.current_nav=a.balance(at,marks)['nav'];receipts={} if event is None else {'A':M.FreshI(event,'A',known_at or at)}
 return M.commit_roles(a,clock=clock(at),securities=ss,sectors=gs,quotes={'A':q()},marks=marks,receipts=receipts,bootstrap=True)
def pending(cls=new,withwindow=True):
 a,op=start(cls);sold=trim(a,op);cl=sold+timedelta(hours=6);assert commit(a,cl,'first').accepted==('A',);op=clock(cl).earliest_execution_at
 if withwindow:assert a.fill_buy('A',w(op)) is None
 expiry=op+timedelta(hours=6);a.expire_day_buys(expiry);return a,expiry

def record(name,fn):
 try:r=fn();results.append(dict(name=name,passed=True,actual=r));print(name,'PASS',r,flush=True)
 except Exception as ex:
  results.append(dict(name=name,passed=False,error=repr(ex),traceback=traceback.format_exc()));(O/'TEST_RESULTS.json').write_text(json.dumps(dict(passed=False,tests=results),indent=2,default=str));raise

def reproduce():
 a,cl=pending(old);assert not getattr(a,'_restore_delay_credit',{});commit(a,cl,'second');assert a.buys['A'].delay_remaining==1;assert a.fill_buy('A',w(clock(cl).earliest_execution_at)) is None;return dict(core=a.roles['A']['K'],restored=0,original_repeat_wait=True)
record('original_held_core_restore_expiry_reproduced',reproduce)
def positive():
 a,cl=pending();assert len(a._restore_delay_credit)==1;commit(a,cl,'second');assert a.buys['A'].delay_remaining==0;f=a.fill_buy('A',w(clock(cl).earliest_execution_at));a.settle_due(f.at);assert f.shares==200 and a.roles['A']['R']==200 and not a._restore_delay_credit;a.check_roles();assert a.balance(f.at,T.marks(f.at))['nav']==D(40000)+sum(a.group_cash.values(),D(0))+a.quantity('A')*10;return dict(actual_restore_shares=f.shares,core=200,full_fee_ledger=True)
record('fresh_I_Q_consumes_credit_actual_restore_fill',positive)
def nosignal():
 a,cl=pending();commit(a,cl,None);assert not a.buys;nxt=cl+timedelta(days=1);a.expire_day_buys(nxt);assert not a._restore_delay_credit;commit(a,nxt,'later');assert a.buys['A'].delay_remaining==1;return dict(no_order_without_fresh_I=True,next_cutoff_credit_expired=True)
record('no_fresh_I_no_revive_and_one_cutoff_expiry',nosignal)
def noq():
 a,cl=pending();assert not commit(a,cl,'q-false',Q=False).accepted and not a.buys;return dict(Q_still_required=True)
record('new_I_but_Q_false_no_order',noq)
def stale():
 a,cl=pending();assert not commit(a,cl,'stale',known_at=cl-timedelta(days=1)).accepted and not a.buys;assert a._restore_delay_credit;return dict(old_signal_never_revived=True)
record('stale_receipt_does_not_consume_or_order',stale)
def nowindow():
 a,cl=pending(withwindow=False);assert not a._restore_delay_credit;commit(a,cl,'second');assert a.buys['A'].delay_remaining==1;return dict(no_eligible_execution_no_credit=True)
record('no_window_no_credit',nowindow)
def partial():
 a,cl=pending();commit(a,cl,'second');op=clock(cl).earliest_execution_at;f=a.fill_buy('A',w(op,100));a.settle_due(op);assert f.shares==100;cl=op+timedelta(hours=6);a.expire_day_buys(cl);assert not a._restore_delay_credit;commit(a,cl,'third');assert a.buys['A'].delay_remaining==1 and a.buys['A'].target_shares==100 and a.roles['A']['R']==100;return dict(partial_real_shares=100,remaining_new_order_waits=True,no_over_cap=True)
record('partly_filled_order_no_zero_fill_credit',partial)
def cleanup():
 a,cl=pending();a.full_signals.add('A');a.request_exit(q(),clock(cl));assert not a._restore_delay_credit and 'A' in a.exits
 b,bc=pending();b.roles['A']['group']='A|different-structure';commit(b,bc,'different-epoch');assert b.buys['A'].delay_remaining==1
 return dict(full_exit_clears=True,structure_mismatch_never_inherits=True)
record('full_exit_and_new_structure_cannot_inherit',cleanup)
def untouched():
 checks=[]
 for cost in [1,2]:
  pairs=[]
  for cls in [old,new]:
   a,op=start(cls,delay=0,cost=cost);cl=trim(a,op)+timedelta(hours=6);commit(a,cl,'restore');a.fill_buy('A',w(clock(cl).earliest_execution_at));pairs.append(a)
  a,b=pairs;assert a.audit_log==b.audit_log and a.fills==b.fills and a.available==b.available;checks.append('normal' if cost==1 else 'cost2')
 for tag in ['A','L']:
  aa=[]
  for cls in [old,new]:
   a,op=start(cls,enabled=False);a.policy_tag=tag;a.expire_day_buys(op+timedelta(hours=6));aa.append(a)
  assert aa[0].audit_log==aa[1].audit_log and aa[0].fills==aa[1].fills;checks.append(tag+'-delay')
 return dict(exact_ledgers=checks)
record('normal_cost2_disabled_roles_delay_exact',untouched)
(O/'TEST_RESULTS.json').write_text(json.dumps(dict(passed=True,tests=results,real_ledger_admission=True,no_historical_returns=True),indent=2,default=str))
